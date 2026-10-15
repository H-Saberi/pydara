"""Explicit local catalog, backups, resumable downloads and grouped exports.

No scheduling, hidden retries across proxies, SQL supplied by users, or pickles.
A download returns BatchFrames, never silently discards failed instruments.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import asdict
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
import json
import os
import sqlite3
import tempfile
import time

import pandas as pd
from pydara.tse._core.exceptions import PyDaraError, InvalidArgumentError, StorageError, BatchDataError
from pydara.tse._core.models import InstrumentRef
from .history_models import BatchFrames
from .services import validate_batch
from .friendly import friendly_range,select,concat
from .io import save,load,sync_file

DATASETS={
 'history':('get_history',True), 'client_types':('_get_client_type_history',True),
 'trades':('get_trades',True), 'order_book_history':('get_order_book_history',True),
 'adjustments':('get_adjustments',True), 'shares':('get_share_capital_history',True),
 'dividends':('get_dividends',True), 'disclosures':('get_disclosures',True),
 'messages':('get_messages',True), 'quotes':('get_quote_frame',False),
 'shareholders':('get_shareholders',False),
}


def _db_path(client):
    """Process internal db path data.
    
    Args:
        client (Any): Synchronous or asynchronous client supplying operations.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        StorageError: When the corresponding validation or operation fails."""
    client._core.check()
    if client._core.store is None:raise StorageError('Local storage is disabled.')
    return client._core.store.path


def datasets(client) -> pd.DataFrame:
    """Catalog locally cached response families; no server request. Empty DB => empty catalog."""
    path=_db_path(client);columns=['dataset','cached_requests','versions','latest_fetch','storage_kind']
    if not path.is_file():return pd.DataFrame(columns=columns)
    try:
        con=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=0.2)
        try:
            rows=con.execute('SELECT v.endpoint_id,COUNT(DISTINCT l.cache_key),COUNT(*),MAX(l.fetched_at) FROM response_versions v JOIN latest_response l ON v.cache_key=l.cache_key WHERE v.cache_key LIKE ? GROUP BY v.endpoint_id',(client._core.namespace+':%',)).fetchall()
        finally:con.close()
    except sqlite3.Error as exc:raise StorageError('Cannot read the local dataset catalog.') from exc
    return pd.DataFrame([(*r,'response_cache') for r in rows],columns=columns)


def storage_info(client) -> pd.DataFrame:
    """Storage health and local file sizes. This is explicit disk inspection."""
    status=asdict(client.storage_status());path=Path(status['path']) if status.get('path') else None
    sizes={}
    for suffix in ('','-wal','-shm'):
        p=Path(str(path)+suffix) if path else None
        try:sizes['database_bytes' if not suffix else suffix[1:]+'_bytes']=p.stat().st_size if p and p.exists() else 0
        except OSError:sizes['database_bytes' if not suffix else suffix[1:]+'_bytes']=None
    return pd.DataFrame([{**status,**sizes}])


def query(client,instrument, *, dataset='history',start=None,end=None,calendar='auto',include_jdate=False) -> pd.DataFrame:
    """Offline read only. History uses the normalized repository; other families require cached responses."""
    from .config import FetchPolicy
    lo,hi,_=friendly_range(start,end,calendar=calendar)
    if dataset=='history':return client.load_stored_history(instrument,start=lo,end=hi,include_jdate=include_jdate)
    if dataset not in DATASETS:raise InvalidArgumentError('Unknown dataset.')
    method,ranged=DATASETS[dataset]
    kwargs={'policy':FetchPolicy.offline(allow_stale=True)}
    if ranged:kwargs.update(start=lo,end=hi,include_jdate=include_jdate)
    elif lo or hi:raise InvalidArgumentError('This snapshot dataset has no range filter.')
    return getattr(client,method)(instrument,**kwargs)


def backup(client,path, *, overwrite=False,timeout=30.0,flush=True) -> dict:
    """Consistent SQLite online backup, including WAL contents; explicit and bounded.
    Never overwrite the active database. This is not a raw copy of an open .sqlite file.
    """
    from .config import positive
    positive('timeout',timeout)
    if not isinstance(overwrite,bool) or not isinstance(flush,bool):raise InvalidArgumentError('overwrite/flush must be bool.')
    source=_db_path(client).resolve();destination=Path(path).expanduser().absolute()
    if destination.resolve()==source:raise StorageError('Backup destination is the active database.')
    if destination.exists() and not overwrite:raise StorageError('Backup exists; pass overwrite=True explicitly.')
    if flush:client.flush(timeout=timeout,raise_on_error=True)
    if not source.is_file():raise StorageError('There is no local database to back up.')
    destination.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(prefix='.pydara-backup-',suffix='.sqlite',dir=destination.parent);os.close(fd)
    started=time.monotonic()
    def progress(status,remaining,total):
        """Perform the progress operation.
        
        Args:
            status (Any): Input for the progress operation.
            remaining (Any): Input for the progress operation.
            total (Any): Input for the progress operation.
        
        Raises:
            StorageError: When the corresponding validation or operation fails."""
        if time.monotonic()-started>timeout:raise StorageError('Backup exceeded timeout.')
    try:
        src=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True,timeout=0.2)
        dst=sqlite3.connect(temp)
        try:
            src.backup(dst,pages=128,progress=progress,sleep=0.05)
            if dst.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise StorageError('Backup integrity check failed.')
        finally:dst.close();src.close()
        sync_file(temp)
        if destination.exists() and not overwrite:raise StorageError('Destination appeared during backup.')
        os.replace(temp,destination)
    except (sqlite3.Error,OSError) as exc:raise StorageError('Backup did not complete.') from exc
    finally:Path(temp).unlink(missing_ok=True)
    return {'state':'persisted','path':str(destination),'bytes':destination.stat().st_size,'created_at':datetime.now(UTC).isoformat()}


def _label(item):
    """Process internal label data.
    
    Args:
        item (Any): Input for the _label operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    return item.value if isinstance(item,InstrumentRef) else item


def _write_json(path,value):
    """Write json.
    
    Args:
        path (Any): Local file or database path.
        value (Any): Input for the _write_json operation."""
    fd,tmp=tempfile.mkstemp(prefix='.pydara-job-',dir=path.parent);os.close(fd)
    try:
        Path(tmp).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf8')
        sync_file(tmp);os.replace(tmp,path)
    finally:Path(tmp).unlink(missing_ok=True)


def _download_plan(client,symbols, *, dataset='history',start=None,end=None,calendar='auto',update=True,
             store=None,on_error='collect',checkpoint_dir=None,resume=True,resume_max_age=3600.0,
             include_jdate=False,progress=None,policy=None) -> BatchFrames:
    """One ordered/resumable job, with explicit partial-result and storage reports.
    history/update/store uses sync_history + local selection; disabled storage fetches
    directly. Checkpoints are opt-in and store typed SQLite frame archives. Resume
    never means new data: resumed rows are labeled; resume=False forces processing.
    The existing per-client network budget remains enforced. No background scheduling.
    """
    from .config import positive,coerce_policy
    client._core.check()
    if isinstance(symbols,(str,InstrumentRef)):symbols=[symbols]
    items=validate_batch(symbols,on_error);policy=coerce_policy(policy)
    if dataset not in DATASETS:raise InvalidArgumentError(f'Unknown dataset; choose {tuple(DATASETS)}.')
    for key,v in [('update',update),('resume',resume),('include_jdate',include_jdate)]:
        if not isinstance(v,bool):raise InvalidArgumentError(f'{key} must be bool.')
    if store is not None and (not isinstance(store,bool) or store!=client.config.storage.enabled):
        raise InvalidArgumentError('For a Client, store must match its storage setting. Construct Client(storage=False) to disable writes.')
    if checkpoint_dir is not None and not client.config.storage.enabled:raise InvalidArgumentError('Checkpoints write to disk; enable storage or omit checkpoint_dir.')
    positive('resume_max_age',resume_max_age,zero=True)
    if progress is not None and not callable(progress):raise InvalidArgumentError('progress must be callable.')
    lo,hi,cal=friendly_range(start,end,calendar=calendar)
    method,ranged=DATASETS[dataset]
    if not ranged and (lo or hi):raise InvalidArgumentError('Snapshot datasets have no date range.')
    # Fail unsupported full-date intraday requests before contacting any server.
    if dataset in ('trades','order_book_history') and (lo is None or hi is None):
        raise InvalidArgumentError('Explicit start/end required for batch intraday datasets.')
    signature={'dataset':dataset,'items':[{'kind':x.kind,'value':x.value,'market':str(x.market) if x.market else None} if isinstance(x,InstrumentRef) else x for x in items],
        'start':str(lo),'end':str(hi),'calendar':cal,'numeric':client.config.numeric,'namespace':client._core.namespace,
        'include_jdate':include_jdate,'policy':repr(policy),'update':update,'schema_version':1}
    digest=sha256(json.dumps(signature,sort_keys=True,default=str).encode()).hexdigest()
    root=Path(checkpoint_dir).expanduser().absolute()/digest if checkpoint_dir is not None else None
    journal={};checkpoint_error=None
    if root:
        try:
            journal = yield ('local', _prepare_checkpoint, (root, signature, resume), {})
        except (OSError,ValueError):
            checkpoint_error='checkpoint_directory_unavailable'
            root=None
    frames=[];reports=[];errors=[];components=[]
    for index,item in enumerate(items):
        report={'request_index':index,'input_symbol':_label(item),'status':'error','row_count':0,'error_code':None,'error_message':None,'storage_state':None,'checkpoint_state':None,'resumed':False}
        try:
            frame=None
            if root and resume and not (policy and policy.freshness and policy.freshness.max_age is not None and policy.freshness.max_age.total_seconds()==0):
                ent=journal['items'].get(str(index),{})
                if isinstance(ent,dict) and ent.get('state')=='persisted':
                    frame = yield ('local', _resume_frame, (root, index, ent, resume_max_age), {})
                    if frame is not None:
                        report.update(resumed=True,storage_state='checkpoint',checkpoint_state='loaded')
                        frame.attrs.setdefault('pydara',{}).update(resumed_from_checkpoint=True,not_refreshed_during_resume=True,from_cache=True,is_stale=True)
                        if 'from_cache' in frame:frame['from_cache']=pd.Series(True,index=frame.index,dtype='boolean')
                        if 'is_stale' in frame:frame['is_stale']=pd.Series(True,index=frame.index,dtype='boolean')
                        if 'quality_flags' in frame:frame['quality_flags']=frame['quality_flags'].apply(lambda v:tuple(dict.fromkeys((*v,'resumed_checkpoint_not_refreshed'))))
            if frame is None:
                if dataset=='history' and update and client.config.storage.enabled and (policy.mode if policy and policy.mode else client.config.mode)!='offline':
                    result=yield ('client','sync_history',(item,),dict(wait=True,on_storage_error='report'))
                    report['storage_state']=result.summary.get('state')
                    if result.summary.get('state')=='persisted':frame=yield ('client','load_stored_history',(item,),dict(start=lo,end=hi,include_jdate=include_jdate))
                    else:
                        # A tail fetch is not the whole requested history. Fetch the full
                        # response without relying on a failed normalized repository.
                        frame=yield ('client','get_history',(item,),dict(start=lo,end=hi,include_jdate=include_jdate,policy=policy))
                        frame.attrs.setdefault('pydara',{})['storage_failure_report']=result.summary
                else:
                    kwargs={'policy':policy}
                    if ranged:kwargs.update(start=lo,end=hi,include_jdate=include_jdate)
                    frame=yield ('client',method,(item,),kwargs)
                    report['storage_state']='queued_or_cached' if client.config.storage.enabled else 'disabled'
                if root:
                    try:
                        receipt=yield ('local',save,(frame,root/(str(index)+'.sqlite')),dict(overwrite=True))
                        journal['items'][str(index)]={'state':'persisted','saved_at':datetime.now(UTC).isoformat(),'rows':len(frame)}
                        yield ('local',_write_json,(root/'job.json',journal),{})
                        report['checkpoint_state']='persisted'
                    except (PyDaraError,OSError) as exc:
                        report['checkpoint_state']='failed';report['checkpoint_error']=type(exc).__name__
            if checkpoint_error:report['checkpoint_state']='failed';report['checkpoint_error']=checkpoint_error
            components.append(deepcopy(frame.attrs.get('pydara',{})))
            f=frame.copy(deep=True);f.attrs={};f['request_index']=pd.Series(index,index=f.index,dtype='Int64');f['input_symbol']=pd.Series(_label(item),index=f.index,dtype='string')
            frames.append(f);report.update(status='ok',row_count=len(f))
        except PyDaraError as exc:
            report.update(error_code=type(exc).__name__,error_message=str(exc));errors.append(report.copy())
            if on_error=='raise':
                reports.append(report)
                raise BatchDataError('Download item failed; partial_result is available.',partial_result=_result(frames,reports,errors,components,signature)) from exc
        reports.append(report)
        if progress:progress(dict(report,completed=index+1,total=len(items)))
    return _result(frames,reports,errors,components,signature)


def _prepare_checkpoint(root,signature,resume):
    """Prepare checkpoint.
    
    Args:
        root (Any): Input for the _prepare_checkpoint operation.
        signature (Any): Input for the _prepare_checkpoint operation.
        resume (Any): Input for the _prepare_checkpoint operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    root.mkdir(parents=True,exist_ok=True)
    journal={}
    if resume and (root/'job.json').is_file():
        try:
            journal=json.loads((root/'job.json').read_text(encoding='utf8'))
            if not isinstance(journal,dict) or journal.get('signature')!=signature or not isinstance(journal.get('items'),dict):
                journal={}
        except (OSError,ValueError):journal={}
    journal.setdefault('signature',signature);journal.setdefault('items',{})
    return journal


def _resume_frame(root,index,ent,max_age):
    """Process internal resume frame data.
    
    Args:
        root (Any): Input for the _resume_frame operation.
        index (Any): Input for the _resume_frame operation.
        ent (Any): Input for the _resume_frame operation.
        max_age (Any): Input for the _resume_frame operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    try:
        age=(datetime.now(UTC)-datetime.fromisoformat(ent['saved_at'])).total_seconds()
        path=root/(str(index)+'.sqlite')
        if 0<=age<=max_age and path.is_file():return load(path)
    except (PyDaraError,KeyError,ValueError,TypeError,OSError):pass
    return None


def execute_plan(client,plan):
    """Shared orchestration yields explicit local/client operations, not coroutines."""
    try:
        action=next(plan)
        while True:
            kind,target,args,kwargs=action
            try:
                value=(getattr(client,target) if kind=='client' else target)(*args,**kwargs)
            except Exception as exc:action=plan.throw(exc)
            else:action=plan.send(value)
    except StopIteration as done:return done.value
    finally:plan.close()


async def aexecute_plan(client,plan):
    """Perform the aexecute plan operation.
    
    Args:
        client (Any): Synchronous or asynchronous client supplying operations.
        plan (Any): Input for the aexecute_plan operation.
    
    Notes:
        This coroutine must be awaited.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    import asyncio
    import inspect
    try:
        action=next(plan)
        while True:
            kind,target,args,kwargs=action
            try:
                if kind=='client':
                    value=getattr(client,target)(*args,**kwargs)
                    if inspect.isawaitable(value):value=await value
                else:value=await asyncio.to_thread(target,*args,**kwargs)
            except Exception as exc:action=plan.throw(exc)
            else:action=plan.send(value)
    except StopIteration as done:return done.value
    finally:plan.close()


def download(client,symbols,**kwargs):
    """Ordered data job with reports and opt-in disk checkpoints. Uses existing bounded network budget; partial success is explicit.
    
    Args:
        client (Any): Synchronous or asynchronous client supplying operations.
        symbols (Any): Input for the download operation.
        kwargs: Additional keyword arguments forwarded to the wrapped operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    return execute_plan(client,_download_plan(client,symbols,**kwargs))


async def adownload(client,symbols,**kwargs):
    """Perform the adownload operation.
    
    Args:
        client (Any): Synchronous or asynchronous client supplying operations.
        symbols (Any): Input for the adownload operation.
        kwargs: Additional keyword arguments forwarded to the wrapped operation.
    
    Notes:
        This coroutine must be awaited.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    return await aexecute_plan(client,_download_plan(client,symbols,**kwargs))


def _result(frames,reports,errors,components,signature):
    """Process internal result data.
    
    Args:
        frames (Any): Input for the _result operation.
        reports (Any): Input for the _result operation.
        errors (Any): Input for the _result operation.
        components (Any): Input for the _result operation.
        signature (Any): Input for the _result operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    data=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
    meta={'dataset':signature['dataset'],'request':signature,'components':components,'coverage_status':'unknown',
          'failed_items':len(errors),'requested_items':len(signature['items']),'processed_items':len(reports)}
    data.attrs['pydara']=deepcopy(meta)
    return BatchFrames(data=data,requests=pd.DataFrame(reports),errors=pd.DataFrame(errors,columns=['request_index','input_symbol','status','row_count','error_code','error_message','storage_state','checkpoint_state','resumed']),manifest=meta)


def export_many(value, directory, *, formats=('csv',), group_by='symbol',overwrite=False,on_error='collect') -> pd.DataFrame:
    """Export separate files with safe deterministic filenames; no path traversal.
    Returns one receipt/error row per group and format. Does not delete other files.
    """
    from collections.abc import Mapping
    if isinstance(formats,str):formats=[formats]
    formats=list(formats)
    if not formats or any(x not in ('csv','excel','xlsx','parquet','sqlite') for x in formats):raise InvalidArgumentError('Unknown export format.')
    if on_error not in ('raise','collect'):raise InvalidArgumentError('Invalid error policy.')
    if isinstance(value,BatchFrames):value=value.data
    if isinstance(value,pd.DataFrame):
        groups=list(value.groupby(group_by,dropna=False,sort=False)) if group_by in value else [('data',value)]
    elif isinstance(value,Mapping):groups=list(value.items())
    else:raise InvalidArgumentError('Use a DataFrame, BatchFrames, or mapping of DataFrames.')
    root=Path(directory).expanduser().absolute();reports=[]
    for name,frame in groups:
        if not isinstance(frame,pd.DataFrame):raise InvalidArgumentError('Each export group must be a DataFrame.')
        token=sha256(str(name).encode()).hexdigest()[:16]
        label=''.join(ch for ch in str(name) if ch.isalnum() or ch in ('_','-'))[:40] or 'data'
        for fmt in formats:
            ext='xlsx' if fmt in ('xlsx','excel') else fmt;path=root/f'{label}-{token}.{ext}'
            try:
                receipt=save(frame.reset_index(drop=True),path,overwrite=overwrite)
                reports.append(dict(group=str(name),format=ext,path=str(path),state=receipt.state,error=None))
            except PyDaraError as exc:
                reports.append(dict(group=str(name),format=ext,path=str(path),state='failed',error=str(exc)))
                if on_error=='raise':raise
    return pd.DataFrame(reports,columns=['group','format','path','state','error'])


def short_history(client,instrument,*,start=None,end=None,calendar='auto',adjustment='none',include_jdate=False,policy=None):
    """Perform the short history operation.
    
    Args:
        client (Any): Synchronous or asynchronous client supplying operations.
        instrument (Any): Instrument name or explicit instrument reference; ambiguity is not silently resolved.
        start (Any): Optional beginning of the requested date range.
        end (Any): Optional end of the requested date range.
        calendar (Any): Calendar used to parse or format dates.
        adjustment (Any): Input for the short_history operation.
        include_jdate (Any): Input for the short_history operation.
        policy (Any): Fetch policy controlling network and cached/offline behavior.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    lo,hi,cal=friendly_range(start,end,calendar=calendar)
    f=client.get_history(instrument,start=lo,end=hi,adjustment=adjustment,include_jdate=include_jdate,policy=policy)
    f.attrs.setdefault('pydara',{})['input_calendar']=cal
    return f


def short_market(client,**kwargs):
    """Perform the short market operation.
    
    Args:
        client (Any): Synchronous or asynchronous client supplying operations.
        kwargs: Additional keyword arguments forwarded to the wrapped operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    return client.get_market_watch(**kwargs)


def short_index_history(client,index,*,start=None,end=None,calendar='auto',include_jdate=False,market=None,policy=None):
    """Perform the short index history operation.
    
    Args:
        client (Any): Synchronous or asynchronous client supplying operations.
        index (Any): Input for the short_index_history operation.
        start (Any): Optional beginning of the requested date range.
        end (Any): Optional end of the requested date range.
        calendar (Any): Calendar used to parse or format dates.
        include_jdate (Any): Input for the short_index_history operation.
        market (Any): Market selection or filtering constraint.
        policy (Any): Fetch policy controlling network and cached/offline behavior.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    lo,hi,cal=friendly_range(start,end,calendar=calendar)
    if index=='\u0634\u0627\u062e\u0635 \u06a9\u0644':
        from pydara.tse._core.models import Market
        if market in (Market.TSE,'TSE'):index='32097828799138957'
    f=client.get_index_history(index,start=lo,end=hi,include_jdate=include_jdate,market=market,policy=policy)
    f.attrs.setdefault('pydara',{})['input_calendar']=cal
    return f


def update(client,symbols,**kwargs):
    """Update raw histories with overlap/correction handling. Default resume=False checks anew rather than reusing a job snapshot.
    
    Args:
        client (Any): Synchronous or asynchronous client supplying operations.
        symbols (Any): Input for the update operation.
        kwargs: Additional keyword arguments forwarded to the wrapped operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    return download(client,symbols,dataset='history',update=True,**kwargs)


def download_market(client,*,dataset='history',market=None,limit=100,start=None,end=None,calendar='auto',dry_run=True,on_error='collect',checkpoint_dir=None):
    """Plan bounded downloads for the current watch universe. dry_run=True performs only watch retrieval; historical universe is not reconstructed.
    
    Args:
        client (Any): Synchronous or asynchronous client supplying operations.
        dataset (Any): Input for the download_market operation.
        market (Any): Market selection or filtering constraint.
        limit (Any): Optional maximum result count, where supported.
        start (Any): Optional beginning of the requested date range.
        end (Any): Optional end of the requested date range.
        calendar (Any): Calendar used to parse or format dates.
        dry_run (Any): Input for the download_market operation.
        on_error (Any): Policy for handling errors in multi-item requests.
        checkpoint_dir (Any): Input for the download_market operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails."""
    from .providers.market import positive_int
    positive_int(limit,'limit',10000)
    if not isinstance(dry_run,bool):raise InvalidArgumentError('dry_run must be bool.')
    if dataset not in DATASETS:raise InvalidArgumentError('Unknown dataset.')
    friendly_range(start,end,calendar=calendar)
    watch=client.get_market_watch(market=market)
    selected=watch[['ins_code','symbol']].head(limit).copy()
    selected['dataset']=dataset;selected['planned']=True
    selected.attrs['pydara']={'universe':'current_observed_watch','not_historical_universe':True,'limit':limit,'truncated':len(watch)>limit}
    if dry_run:return selected
    return download(client,[InstrumentRef.by_ins_code(str(v)) for v in selected.ins_code],dataset=dataset,start=start,end=end,calendar=calendar,on_error=on_error,checkpoint_dir=checkpoint_dir)
