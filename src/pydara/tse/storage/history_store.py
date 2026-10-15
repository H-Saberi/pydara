"""Versioned daily-bar index alongside (not instead of) the response cache.

Economic rows are immutable versions; each successful fetch is an observation.
A repeated fetch does not create another economic version. A -> B -> A remains
three observations. Latest pointers never move backwards when writes arrive late.
All per-packet rows, observations and report/checkpoint commit in one transaction.
"""
from __future__ import annotations
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from hashlib import sha256
import sqlite3
import time

import pandas as pd
from pydara.tse._core.exceptions import (AmbiguousInstrumentError, InvalidArgumentError,
    OfflineDataUnavailableError, PointInTimeUnavailableError, StorageError)
from pydara.tse._core.models import InstrumentRef
from ..dates import parse_range, to_jalali
from ..transport import Packet
from .codec import dumps, loads, pack, unpack

HISTORY_VERSION=1
SCHEMA='''
CREATE TABLE IF NOT EXISTS dara_history_meta (id INTEGER PRIMARY KEY CHECK(id=1),version INTEGER NOT NULL);
INSERT OR IGNORE INTO dara_history_meta VALUES(1,1);
CREATE TABLE IF NOT EXISTS dara_history_batches (
 batch_id TEXT PRIMARY KEY, scope_id TEXT NOT NULL, ins_code TEXT NOT NULL, symbol TEXT,
 payload_hash TEXT NOT NULL, fetched_at TEXT NOT NULL, committed_at TEXT NOT NULL,
 requested_rows INTEGER NOT NULL, row_count INTEGER NOT NULL, meta_json TEXT NOT NULL,
 inserted_rows INTEGER NOT NULL, revised_rows INTEGER NOT NULL, unchanged_rows INTEGER NOT NULL,
 omitted_previous_rows INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS dara_history_batch_time ON dara_history_batches(scope_id,ins_code,fetched_at);
CREATE TABLE IF NOT EXISTS dara_daily_versions (
 scope_id TEXT NOT NULL,ins_code TEXT NOT NULL,trade_date TEXT NOT NULL,row_version_id TEXT NOT NULL,
 economic_json TEXT NOT NULL,first_observed_at TEXT NOT NULL,last_observed_at TEXT NOT NULL,
 PRIMARY KEY(scope_id,ins_code,trade_date,row_version_id)
);
CREATE TABLE IF NOT EXISTS dara_daily_observations (
 batch_id TEXT NOT NULL,scope_id TEXT NOT NULL,ins_code TEXT NOT NULL,trade_date TEXT NOT NULL,
 row_version_id TEXT NOT NULL,PRIMARY KEY(batch_id,trade_date)
);
CREATE INDEX IF NOT EXISTS dara_history_obs_day ON dara_daily_observations(scope_id,ins_code,trade_date);
CREATE TABLE IF NOT EXISTS dara_daily_latest (
 scope_id TEXT NOT NULL,ins_code TEXT NOT NULL,trade_date TEXT NOT NULL,
 row_version_id TEXT NOT NULL,batch_id TEXT NOT NULL,fetched_at TEXT NOT NULL,
 PRIMARY KEY(scope_id,ins_code,trade_date)
);
'''


def stamp(value):
    """Timestamp the requested value.
    
    Args:
        value (Any): Input for the stamp operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails."""
    if not isinstance(value,datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise InvalidArgumentError('Timestamp must be timezone-aware.')
    return value.astimezone(UTC).isoformat(timespec='microseconds')


def has_schema(con):
    """Determine whether schema.
    
    Args:
        con (Any): Input for the has_schema operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    return con.execute("SELECT 1 FROM sqlite_master WHERE name='dara_history_meta' AND type='table'").fetchone() is not None


def ensure_schema(con):
    """Ensure schema.
    
    Args:
        con (Any): Input for the ensure_schema operation.
    
    Raises:
        StorageError: When the corresponding validation or operation fails."""
    if has_schema(con) and con.execute('SELECT version FROM dara_history_meta WHERE id=1').fetchone()!=(HISTORY_VERSION,):
        raise StorageError('Unsupported normalized history schema; refusing automatic downgrade.')
    con.executescript(SCHEMA)


def packet_identity(con, code, scope):
    """Perform the packet identity operation.
    
    Args:
        con (Any): Input for the packet_identity operation.
        code (Any): Input for the packet_identity operation.
        scope (Any): Input for the packet_identity operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    from ..providers.public import info_spec, parse_info
    spec=info_spec(code)
    row=con.execute('''SELECT v.payload,v.first_observed_at,l.fetched_at,l.request_id,l.payload_hash
      FROM latest_response l JOIN response_versions v ON v.cache_key=l.cache_key AND v.payload_hash=l.payload_hash
      WHERE l.cache_key=?''',(spec.key(scope),)).fetchone()
    if row is None:
        return {'symbol':None,'raw_symbol':None,'instrument_id':None,'company_cisin':None,
                'currency':None,'quote_unit':'UNKNOWN','quantity_unit':'UNKNOWN',
                'identity_fetched_at':None,'identity_quality':['identity_metadata_unavailable']}
    content,first,fetched,rid,digest=row
    packet=Packet(spec.key(scope),spec.endpoint_id,content,datetime.fromisoformat(fetched),
                  datetime.fromisoformat(first),rid,digest)
    record=parse_info(packet,spec,scope)
    return {'symbol':record.symbol,'raw_symbol':record.raw_symbol,'instrument_id':record.instrument_id,
            'company_cisin':record.company_cisin,'currency':record.currency,
            'quote_unit':str(record.quote_unit),'quantity_unit':str(record.quantity_unit),
            'identity_fetched_at':fetched,'identity_quality':list(record.meta.quality_flags)}


def persist_packet(con, packet, committed):
    """Called ONLY on the existing storage writer, inside its transaction."""
    if packet.endpoint_id!='history.daily': return None
    prior=con.execute('SELECT batch_id FROM dara_history_batches WHERE batch_id=?',(packet.request_id,)).fetchone()
    if prior: return None
    from ..providers.history import history_spec,parse_history_rows
    scope,_,path=packet.cache_key.split(':',2)
    code,n=path.rsplit('/',2)[1:];n=int(n)
    spec=history_spec(code,n=n)
    parsed=parse_history_rows(packet,spec)
    identity=packet_identity(con,code,scope)
    fetched=stamp(packet.fetched_at);commit=stamp(committed)
    old={r[0]:(r[1],r[2]) for r in con.execute('SELECT trade_date,row_version_id,fetched_at FROM dara_daily_latest '
                                                 'WHERE scope_id=? AND ins_code=?',(scope,code))}
    inserted=revised=unchanged=0
    for row in parsed.rows:
        day=row['date'].isoformat();version=row['row_version_id']
        previous=old.get(day)
        if previous is None:inserted+=1
        elif previous[0]==version:unchanged+=1
        else:revised+=1
        if previous and previous[1]==fetched and previous[0]!=version:
            raise StorageError('Conflicting versions with the same observation timestamp.')
        con.execute('''INSERT INTO dara_daily_versions VALUES(?,?,?,?,?,?,?)
          ON CONFLICT(scope_id,ins_code,trade_date,row_version_id) DO UPDATE SET
          first_observed_at=min(first_observed_at,excluded.first_observed_at),
          last_observed_at=max(last_observed_at,excluded.last_observed_at)''',
          (scope,code,day,version,dumps(pack(row)),fetched,fetched))
        con.execute('INSERT INTO dara_daily_observations VALUES(?,?,?,?,?)',
                    (packet.request_id,scope,code,day,version))
        con.execute('''INSERT INTO dara_daily_latest VALUES(?,?,?,?,?,?)
          ON CONFLICT(scope_id,ins_code,trade_date) DO UPDATE SET
          row_version_id=excluded.row_version_id,batch_id=excluded.batch_id,fetched_at=excluded.fetched_at
          WHERE excluded.fetched_at>dara_daily_latest.fetched_at''',
          (scope,code,day,version,packet.request_id,fetched))
    present={r['date'].isoformat() for r in parsed.rows}
    # Omission is not a deletion event. Retain previous data and report the uncertainty.
    omitted=len(set(old)-present) if n==0 else 0
    meta={'identity':identity,'source_row_count':parsed.source_row_count,
          'identical_duplicates_removed':parsed.identical_duplicates,
          'range_start':min(present) if present else None,'range_end':max(present) if present else None,
          'coverage_status':'unknown','absence_is_not_deletion':True}
    con.execute('INSERT INTO dara_history_batches VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (packet.request_id,scope,code,identity['symbol'],packet.payload_hash,fetched,commit,n,
                 len(parsed.rows),dumps(meta),inserted,revised,unchanged,omitted))
    return {'inserted_rows':inserted,'revised_rows':revised,'unchanged_rows':unchanged}


class HistoryStore:
    """Local, read-only query facade. No network and no implicit database creation.

    Existing v0.2 raw history can be indexed explicitly with reindex().
    ``as_of`` selects only observations BOTH fetched and locally committed by
    that time; it is not an exchange-publication-time backtest guarantee.
    """
    def __init__(self,path: str | Path,*,namespace='public',numeric='analysis',timeout=5.0):
        """Initialize the instance and its configured state.
        
        Args:
            path (str | Path): Local file or database path.
            namespace (Any): Storage or frame metadata namespace.
            numeric (Any): Numeric conversion or output representation setting.
            timeout (Any): Maximum wait time in seconds.
        
        Raises:
            InvalidArgumentError: When the corresponding validation or operation fails."""
        from ..config import positive
        if namespace not in ('public','sample'):raise InvalidArgumentError('Unknown cache namespace.')
        if numeric not in ('analysis','exact'):raise InvalidArgumentError('Invalid numeric profile.')
        positive('timeout',timeout)
        self.path=Path(path).absolute();self.namespace=namespace;self.numeric=numeric;self.timeout=timeout

    def _connect(self,*,write=False):
        """Process internal connect data.
        
        Args:
            write (Any): Input for the _connect operation.
        
        Returns:
            Implementation-defined result or generator output; see the calling API.
        
        Raises:
            OfflineDataUnavailableError: When the corresponding validation or operation fails.
            StorageError: When the corresponding validation or operation fails."""
        if not self.path.is_file():raise OfflineDataUnavailableError('No local database exists for this path.')
        con=sqlite3.connect(self.path.as_uri()+('?mode=rw' if write else '?mode=ro'),uri=True,
                            timeout=min(self.timeout,1.0))
        deadline=time.monotonic()+self.timeout
        con.set_progress_handler(lambda:int(time.monotonic()>deadline),1000)
        if con.execute('PRAGMA user_version').fetchone()[0]!=1:
            con.close();raise StorageError('Not a supported PyDara response database.')
        if has_schema(con) and con.execute('SELECT version FROM dara_history_meta WHERE id=1').fetchone()!=(HISTORY_VERSION,):
            con.close();raise StorageError('Unsupported history schema version.')
        return con

    def _resolve(self,con,instrument,as_of=None):
        """Resolve the requested value.
        
        Args:
            con (Any): Input for the _resolve operation.
            instrument (Any): Instrument name or explicit instrument reference; ambiguity is not silently resolved.
            as_of (Any): Requested economic effective date; check endpoint support.
        
        Returns:
            Implementation-defined result or generator output; see the calling API.
        
        Raises:
            AmbiguousInstrumentError: When the corresponding validation or operation fails.
            InvalidArgumentError: When the corresponding validation or operation fails.
            OfflineDataUnavailableError: When the corresponding validation or operation fails."""
        from ..providers.public import normalize_symbol
        if isinstance(instrument,InstrumentRef):
            if instrument.kind=='ins_code':return instrument.value
            if instrument.kind!='symbol':raise InvalidArgumentError('Use a symbol or ins_code.')
            value=instrument.value
        elif isinstance(instrument,str):value=instrument
        else:raise InvalidArgumentError('Use a symbol or InstrumentRef.')
        query='SELECT DISTINCT ins_code FROM dara_history_batches WHERE scope_id=? AND symbol=?'
        params=[self.namespace,normalize_symbol(value)]
        if as_of:
            query+=' AND fetched_at<=? AND committed_at<=?';params.extend([as_of,as_of])
        matches=[r[0] for r in con.execute(query,params)]
        if not matches:raise OfflineDataUnavailableError('Symbol is not present in the local history index.')
        if len(matches)>1:raise AmbiguousInstrumentError('Stored symbol is ambiguous; specify ins_code.',candidates=tuple(matches))
        return matches[0]

    def status(self) -> pd.DataFrame:
        """Return status for the requested value.
        
        Returns:
            pd.DataFrame: Result of the status operation; refer to its public API contract for schema details.
        
        Raises:
            StorageError: When the corresponding validation or operation fails."""
        columns=['scope_id','ins_code','symbol','rows','versions','batches','first_date','last_date',
                 'last_fetched_at','last_committed_at','last_full_fetch_at']
        if not self.path.is_file():return pd.DataFrame(columns=columns)
        con=self._connect()
        try:
            if not has_schema(con):return pd.DataFrame(columns=columns)
            query='''SELECT b.scope_id,b.ins_code,
              (SELECT symbol FROM dara_history_batches s WHERE s.scope_id=b.scope_id AND s.ins_code=b.ins_code
               ORDER BY fetched_at DESC,committed_at DESC LIMIT 1),
              (SELECT count(*) FROM dara_daily_latest l WHERE l.scope_id=b.scope_id AND l.ins_code=b.ins_code),
              (SELECT count(*) FROM dara_daily_versions v WHERE v.scope_id=b.scope_id AND v.ins_code=b.ins_code),
              count(*),
              (SELECT min(trade_date) FROM dara_daily_latest l WHERE l.scope_id=b.scope_id AND l.ins_code=b.ins_code),
              (SELECT max(trade_date) FROM dara_daily_latest l WHERE l.scope_id=b.scope_id AND l.ins_code=b.ins_code),
              max(b.fetched_at),max(b.committed_at),max(CASE WHEN requested_rows=0 THEN fetched_at END)
              FROM dara_history_batches b WHERE scope_id=? GROUP BY scope_id,ins_code'''
            return pd.DataFrame(con.execute(query,(self.namespace,)).fetchall(),columns=columns)
        except sqlite3.Error as exc:raise StorageError('Could not read history status.') from exc
        finally:con.close()

    def read(self,instrument,*,start=None,end=None,calendar='gregorian',include_jdate=False,as_of=None) -> pd.DataFrame:
        """Read the requested value.
        
        Args:
            instrument (Any): Instrument name or explicit instrument reference; ambiguity is not silently resolved.
            start (Any): Optional beginning of the requested date range.
            end (Any): Optional end of the requested date range.
            calendar (Any): Calendar used to parse or format dates.
            include_jdate (Any): Input for the read operation.
            as_of (Any): Requested economic effective date; check endpoint support.
        
        Returns:
            pd.DataFrame: Result of the read operation; refer to its public API contract for schema details.
        
        Raises:
            InvalidArgumentError: When the corresponding validation or operation fails.
            OfflineDataUnavailableError: When the corresponding validation or operation fails.
            StorageError: When the corresponding validation or operation fails.
            cls: When the corresponding validation or operation fails."""
        lo,hi=parse_range(start,end,calendar=calendar)
        cutoff=stamp(as_of) if as_of is not None else None
        if not isinstance(include_jdate,bool):raise InvalidArgumentError('include_jdate must be bool.')
        con=self._connect()
        try:
            if not has_schema(con):raise OfflineDataUnavailableError('History not indexed yet; run reindex_history() or sync_history().')
            code=self._resolve(con,instrument,cutoff)
            where='o.scope_id=? AND o.ins_code=?';params=[self.namespace,code]
            if lo:where+=' AND o.trade_date>=?';params.append(lo.isoformat())
            if hi:where+=' AND o.trade_date<=?';params.append(hi.isoformat())
            if cutoff:where+=' AND b.fetched_at<=? AND b.committed_at<=?';params.extend([cutoff,cutoff])
            q=f'''WITH chosen AS (
              SELECT o.*,b.fetched_at,b.committed_at,b.payload_hash,b.meta_json,
              row_number() OVER(PARTITION BY o.trade_date ORDER BY b.fetched_at DESC,b.committed_at DESC,b.batch_id DESC) AS rn
              FROM dara_daily_observations o JOIN dara_history_batches b ON b.batch_id=o.batch_id WHERE {where})
              SELECT c.trade_date,c.row_version_id,c.batch_id,c.fetched_at,c.committed_at,c.payload_hash,c.meta_json,
                     v.economic_json
              FROM chosen c JOIN dara_daily_versions v ON v.scope_id=c.scope_id AND v.ins_code=c.ins_code
              AND v.trade_date=c.trade_date AND v.row_version_id=c.row_version_id WHERE c.rn=1 ORDER BY c.trade_date'''
            found=con.execute(q,params).fetchall()
            # Distinguish empty requested range from no observations at all.
            availability=con.execute('SELECT count(*) FROM dara_history_batches WHERE scope_id=? AND ins_code=?'+
              (' AND fetched_at<=? AND committed_at<=?' if cutoff else ''),
              [self.namespace,code]+([cutoff,cutoff] if cutoff else [])).fetchone()[0]
            if not availability:
                cls=PointInTimeUnavailableError if cutoff else OfflineDataUnavailableError
                raise cls('No locally committed observations satisfy this selection.')
            fullq='SELECT batch_id,omitted_previous_rows,fetched_at FROM dara_history_batches WHERE scope_id=? AND ins_code=? AND requested_rows=0'
            args=[self.namespace,code]
            if cutoff:fullq+=' AND fetched_at<=? AND committed_at<=?';args += [cutoff,cutoff]
            full=con.execute(fullq+' ORDER BY fetched_at DESC,committed_at DESC LIMIT 1',args).fetchone()
            full_dates={r[0] for r in con.execute('SELECT trade_date FROM dara_daily_observations WHERE batch_id=?',
                        (full[0],))} if full else None
            rows=[]
            for day,version,bid,fetched,committed,payload,meta,raw in found:
                row=unpack(loads(raw)); identity=loads(meta)['identity']
                flags=list(row['quality_flags'])+identity['identity_quality']+[
                    'stored_history_not_live','publication_time_unknown','identity_resolved_from_current_instrument_info']
                if self.namespace=='sample':flags.append('synthetic_sample_not_market_data')
                if full_dates is not None and day not in full_dates and fetched<=full[2]:
                    flags.append('absent_from_last_full_snapshot_retained')
                # Never borrow first-observation metadata from an observation after the requested cutoff.
                first_query='''SELECT min(b.fetched_at) FROM dara_daily_observations o JOIN dara_history_batches b
                  ON b.batch_id=o.batch_id WHERE o.scope_id=? AND o.ins_code=? AND o.trade_date=? AND o.row_version_id=?'''
                fa=[self.namespace,code,day,version]
                if cutoff:first_query+=' AND b.fetched_at<=? AND b.committed_at<=?';fa += [cutoff,cutoff]
                first=con.execute(first_query,fa).fetchone()[0]
                row.update({k:v for k,v in identity.items() if k not in ('identity_quality',)})
                row.update(adjustment='none',series='listing',source='public',endpoint_id='history.daily',
                    scope_id=self.namespace,row_id=sha256(f'{self.namespace}:daily:{code}:{day}'.encode()).hexdigest(),observation_id=bid,
                    payload_hash=payload,raw_reference=payload,availability_basis='local_fetch_and_commit',
                    first_observed_at=first,fetched_at=fetched,available_at=max(fetched,committed),
                    committed_at=committed,storage_receipt_id=None,from_cache=True,is_stale=True,
                    timestamp_kind='source_hEven_semantics_unverified',quality_flags=tuple(dict.fromkeys(flags)))
                rows.append(row)
            from ..history import STRINGS,TIMES,BOOLS,DISPLAY_COLUMNS
            from ..providers.history import NUMERIC_FIELDS
            from ..frames import cast_frame
            frame=cast_frame(rows,STRINGS,[*TIMES,'committed_at'],BOOLS,list(NUMERIC_FIELDS),['trade_count'],
                             numeric=self.numeric,extra=['date','quality_flags'])
            frame['date']=pd.to_datetime(frame['date']).astype('datetime64[ns]')
            if include_jdate:frame['jdate']=pd.Series([to_jalali(r['date']) for r in rows],dtype='string')
            frame=frame[[*DISPLAY_COLUMNS,*[c for c in frame if c not in DISPLAY_COLUMNS]]]
            frame.attrs['pydara']={'schema_id':'daily_bars','schema_version':'1','scope_id':self.namespace,
                'source':'local_history','from_cache':True,'is_stale':True,'coverage_status':'unknown',
                'snapshot_as_of':cutoff,'availability_basis':'local_fetch_and_commit','numeric':self.numeric,
                'adjustment':'none','series':'listing','returned_rows':len(frame),
                'warnings':['stored_history_not_live','not_an_exchange_publication_time_dataset'],
                'last_full_snapshot_omissions':full[1] if full else None}
            return frame
        except sqlite3.Error as exc:raise StorageError('Local history query failed or timed out.') from exc
        finally:con.close()

    def revisions(self,instrument,*,start=None,end=None,calendar='gregorian') -> pd.DataFrame:
        """Perform the revisions operation.
        
        Args:
            instrument (Any): Instrument name or explicit instrument reference; ambiguity is not silently resolved.
            start (Any): Optional beginning of the requested date range.
            end (Any): Optional end of the requested date range.
            calendar (Any): Calendar used to parse or format dates.
        
        Returns:
            pd.DataFrame: Result of the revisions operation; refer to its public API contract for schema details.
        
        Raises:
            OfflineDataUnavailableError: When the corresponding validation or operation fails."""
        lo,hi=parse_range(start,end,calendar=calendar)
        con=self._connect()
        try:
            if not has_schema(con):raise OfflineDataUnavailableError('No normalized history index.')
            code=self._resolve(con,instrument)
            q='SELECT trade_date,row_version_id,first_observed_at,last_observed_at,economic_json FROM dara_daily_versions WHERE scope_id=? AND ins_code=?'
            args=[self.namespace,code]
            if lo:q+=' AND trade_date>=?';args.append(lo.isoformat())
            if hi:q+=' AND trade_date<=?';args.append(hi.isoformat())
            rows=[]
            for d,v,first,last,raw in con.execute(q+' ORDER BY trade_date,first_observed_at',args):
                r=unpack(loads(raw));rows.append({'ins_code':code,'date':d,'row_version_id':v,
                    'first_observed_at':first,'last_observed_at':last,
                    'last_price':r['last_price'],'closing_price':r['closing_price'],'volume':r['volume']})
            return pd.DataFrame(rows,columns=['ins_code','date','row_version_id','first_observed_at',
                                               'last_observed_at','last_price','closing_price','volume'])
        finally:con.close()

    def batch_report(self,request_id):
        """Perform the batch report operation.
        
        Args:
            request_id (Any): Input for the batch_report operation.
        
        Returns:
            Implementation-defined result or generator output; see the calling API."""
        con=self._connect()
        try:
            if not has_schema(con):return None
            cursor=con.execute('SELECT * FROM dara_history_batches WHERE batch_id=? AND scope_id=?',
                               (request_id,self.namespace));row=cursor.fetchone()
            return dict(zip([x[0] for x in cursor.description],row)) if row else None
        finally:con.close()

    def reindex(self) -> dict:
        """Index existing raw observations without HTTP. Commits one packet at a time.

        Resumable/idempotent on batch_id. The local-commit time is NOW, not an
        invented earlier availability date. Existing response cache is retained.
        """
        con=self._connect(write=True)
        indexed=0;examined=0
        try:
            ensure_schema(con)
            entries=con.execute('''SELECT o.cache_key,v.endpoint_id,v.payload,o.fetched_at,
              v.first_observed_at,o.request_id,o.payload_hash FROM observations o JOIN response_versions v
              ON o.cache_key=v.cache_key AND o.payload_hash=v.payload_hash
              WHERE v.endpoint_id='history.daily' AND o.cache_key LIKE ?
              ORDER BY o.fetched_at''',(self.namespace+':%',))
            for key,endpoint,content,fetched,first,rid,digest in entries:
                examined+=1
                if con.execute('SELECT 1 FROM dara_history_batches WHERE batch_id=?',(rid,)).fetchone():continue
                from hashlib import sha256
                if sha256(content).hexdigest()!=digest:raise StorageError('Raw history checksum mismatch.')
                packet=Packet(key,endpoint,content,datetime.fromisoformat(fetched),datetime.fromisoformat(first),rid,digest)
                with con:persist_packet(con,packet,datetime.now(UTC))
                indexed+=1
            return {'indexed_batches':indexed,'examined_batches':examined,'network_requests':0}
        except sqlite3.Error as exc:raise StorageError('Reindex failed; already committed batches are preserved.') from exc
        finally:con.close()
