"""Stable Pandas tables for market, participant and index data (no I/O)."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from copy import deepcopy
import warnings
import pandas as pd
from pydara import __version__
from pydara.tse._core.exceptions import CoverageError, StaleDataError, StaleDataWarning
from .frames import cast_frame
from .dates import to_jalali
from .config import coerce_policy

META_STRINGS = ('source', 'endpoint_id', 'scope_id', 'row_id', 'observation_id',
                'payload_hash', 'raw_reference', 'availability_basis', 'storage_receipt_id')
META_TIMES = ('source_timestamp', 'fetched_at', 'first_observed_at', 'available_at')
META_BOOLS = ('from_cache', 'is_stale')
PARTICIPANT_COUNTS = tuple(f'{p}_{s}_count' for p in ('individual', 'institutional') for s in ('buy', 'sell'))
PARTICIPANT_NUMBERS = tuple(f'{p}_{s}_{n}' for p in ('individual', 'institutional')
                            for s in ('buy', 'sell') for n in ('volume', 'value'))
PRICE_NUMBERS = ('open_price', 'high_price', 'low_price', 'last_price', 'closing_price',
                 'previous_reference_price', 'volume', 'turnover')

@dataclass(frozen=True)
class FrameSpec:
    """Define a normalized DataFrame schema and column types.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    strings: tuple[str, ...] = ()
    numbers: tuple[str, ...] = ()
    integers: tuple[str, ...] = ()
    dates: tuple[str, ...] = ('date',)
    times: tuple[str, ...] = ()
    bools: tuple[str, ...] = ()
    key: tuple[str, ...] = ()
    display: tuple[str, ...] = ()

SCHEMAS = {
    'market_watch': FrameSpec(
        strings=('ins_code','symbol','name','market','raw_flow','sector_code','instrument_id',
                 'instrument_type','currency','quote_unit','quantity_unit','timestamp_kind'),
        numbers=PRICE_NUMBERS+('base_volume','shares_outstanding','eps','pe','min_allowed_price','max_allowed_price'),
        integers=('trade_count',), key=('ins_code',),
        display=('ins_code','symbol','name','date','last_price','closing_price','volume','turnover','trade_count')),
    'market_order_book': FrameSpec(
        strings=('ins_code','symbol','reference_id','currency','quote_unit','quantity_unit','timestamp_kind'),
        numbers=('bid_price','ask_price','bid_volume','ask_volume'),
        integers=('depth','bid_order_count','ask_order_count'), key=('ins_code','depth'),
        display=('ins_code','symbol','depth','bid_price','bid_volume','ask_price','ask_volume')),
    'market_overview': FrameSpec(
        strings=('market','state','raw_state','currency','index_unit'),
        numbers=('market_value','market_value_base','volume','turnover','index_value','index_change',
                 'equal_weight_index_value','equal_weight_index_change'), integers=('trade_count',),
        dates=('date','data_date'), times=('data_timestamp',), key=('market',),
        display=('market','date','state','index_value','index_change','turnover','volume','trade_count')),
    'client_types': FrameSpec(
        strings=('ins_code','symbol','market','currency','quote_unit','quantity_unit','timestamp_kind'),
        numbers=PARTICIPANT_NUMBERS+('buy_ddd_volume',), integers=PARTICIPANT_COUNTS+('buy_ddd_count',),
        key=('ins_code','date'), display=('ins_code','symbol','date',*PARTICIPANT_COUNTS,*PARTICIPANT_NUMBERS)),
    'indices': FrameSpec(strings=('index_code','name','market','unit','timestamp_kind'),
        numbers=('value','high','low','change','change_percent'),
        integers=('source_c1','source_c2','source_c3','source_c4'), key=('index_code',),
        display=('index_code','name','market','date','value','change','change_percent')),
    'index_history': FrameSpec(strings=('index_code','name','market','unit'),
        numbers=('value','high','low'), key=('index_code','date'),
        display=('index_code','name','date','value','high','low')),
    'index_intraday': FrameSpec(strings=('index_code','name','market','unit','timestamp_kind'),
        numbers=('value','high','low','change','change_percent'), integers=('source_position',),
        key=(), display=('index_code','name','date','source_timestamp','value','high','low')),
    'index_members': FrameSpec(strings=('index_code','ins_code','symbol','name','market','raw_flow','currency',
                 'quote_unit','quantity_unit','timestamp_kind','membership_basis'),
        numbers=PRICE_NUMBERS+('shares_outstanding',), integers=('trade_count',), key=('index_code','ins_code'),
        display=('index_code','ins_code','symbol','name','date','last_price','closing_price','volume')),
    'index_impact': FrameSpec(strings=('market','ins_code','symbol','name','impact_field','unit'),
        numbers=('impact_points',), integers=('source_position',), key=(),
        display=('market','ins_code','symbol','impact_points','impact_field')),
    'sector_summary': FrameSpec(strings=('sector_code','name'),
        integers=('source_c1','source_c2','source_c3','source_c4'), dates=(), key=('sector_code',),
        display=('sector_code','name','source_c1','source_c2','source_c3','source_c4')),
    'sector_instruments': FrameSpec(strings=('sector_code','ins_code','symbol','name','market','raw_flow',
                    'currency','quote_unit','quantity_unit','timestamp_kind'),
        numbers=PRICE_NUMBERS, integers=('trade_count',), key=('sector_code','ins_code'),
        display=('sector_code','ins_code','symbol','name','date','last_price','closing_price')),
    'key_statistics': FrameSpec(strings=('ins_code','parameter_code','reported_value','unit'),
        numbers=(), dates=('date',), key=('ins_code','parameter_code','date'),
        display=('ins_code','parameter_code','date','reported_value','unit')),
    'market_map': FrameSpec(strings=('ins_code','symbol','name','sector_name','currency','quote_unit','quantity_unit','timestamp_kind'),
        numbers=PRICE_NUMBERS+('market_cap','price_change_percent','source_percent'), integers=('trade_count',),
        key=('ins_code',),display=('ins_code','symbol','name','date','last_price','closing_price','market_cap','price_change_percent')),
}


def empty_market_frame(schema: str, numeric='analysis', include_jdate=False) -> pd.DataFrame:
    """Create an empty market frame.
    
    Args:
        schema (str): Input for the empty_market_frame operation.
        numeric (Any): Numeric conversion or output representation setting.
        include_jdate (Any): Input for the empty_market_frame operation.
    
    Returns:
        pd.DataFrame: Result of the empty_market_frame operation; refer to its public API contract for schema details."""
    return market_frame([],schema,numeric=numeric,include_jdate=include_jdate)


def market_frame(rows, schema, *, packet=None, namespace='public', numeric='analysis',
                 include_jdate=False, extra_meta=None):
    """Perform the market frame operation.
    
    Args:
        rows (Any): Input for the market_frame operation.
        schema (Any): Input for the market_frame operation.
        packet (Any): Response packet received from a provider.
        namespace (Any): Storage or frame metadata namespace.
        numeric (Any): Numeric conversion or output representation setting.
        include_jdate (Any): Input for the market_frame operation.
        extra_meta (Any): Input for the market_frame operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    spec=SCHEMAS[schema]
    content=[]
    for pos, original in enumerate(rows):
        r=dict(original)
        flags=list(r.get('quality_flags',()))
        if packet is not None:
            if packet.is_stale: flags.append('stale_cached_response')
            if namespace.startswith('sample'): flags.append('synthetic_sample_not_market_data')
            flags.append('publication_time_unknown')
            key=':'.join(str(r.get(k,'')) for k in spec.key) if spec.key else str(pos)
            r.update(source='public',endpoint_id=packet.endpoint_id,scope_id=namespace,
                row_id=sha256(f'{namespace}:{schema}:{key}'.encode()).hexdigest(),
                observation_id=packet.request_id,payload_hash=packet.payload_hash,raw_reference=packet.payload_hash,
                availability_basis='observed_response',storage_receipt_id=packet.receipt_id,
                fetched_at=packet.fetched_at,first_observed_at=packet.first_observed_at,
                available_at=packet.fetched_at,from_cache=packet.from_cache,is_stale=packet.is_stale)
            if numeric=='analysis' and any(r.get(k) is not None and abs(r[k])>2**53 for k in spec.numbers):
                flags.append('large_numeric_value_use_exact_profile')
        r['quality_flags']=tuple(dict.fromkeys(flags))
        content.append(r)
    frame=cast_frame(content,[*spec.strings,*META_STRINGS,'source_fields'],[*spec.times,*META_TIMES],
        [*spec.bools,*META_BOOLS],spec.numbers,spec.integers,numeric,extra=[*spec.dates,'quality_flags'])
    for col in spec.dates:
        frame[col]=pd.to_datetime(frame[col]).astype('datetime64[ns]')
    if include_jdate and 'date' in frame:
        frame['jdate']=pd.Series([None if pd.isna(x) else to_jalali(x.date()) for x in frame['date']],dtype='string')
    frame=frame[[*spec.display,*[x for x in frame if x not in spec.display]]]
    frame.attrs['pydara']={
        'schema_id':schema,'schema_version':'1','package_version':__version__, 'numeric':numeric,
        'coverage_status':'unknown','returned_rows':len(frame),'from_cache':packet.from_cache if packet else False,
        'is_stale':packet.is_stale if packet else False,'synthetic':namespace.startswith('sample'),
        'source':'public','endpoint_id':packet.endpoint_id if packet else None,'scope_id':namespace,
        'fetched_at':packet.fetched_at.isoformat() if packet else None,
        'available_at':packet.fetched_at.isoformat() if packet else None,
        'raw_reference':packet.payload_hash if packet else None,
        'storage_receipt_id':packet.receipt_id if packet else None,
        'warnings':['coverage_not_certified','not_a_point_in_time_dataset'],
        'empty_means':'no_records_returned_not_proof_of_no_activity',
    }
    if extra_meta:frame.attrs['pydara'].update(deepcopy(extra_meta))
    return frame


def finish_market(frame, policy=None):
    """Finalize market.
    
    Args:
        frame (Any): DataFrame to convert, validate, process or store.
        policy (Any): Fetch policy controlling network and cached/offline behavior.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        CoverageError: When the corresponding validation or operation fails.
        StaleDataError: When the corresponding validation or operation fails."""
    policy=coerce_policy(policy)
    m=frame.attrs.get('pydara',{})
    if policy and policy.coverage=='raise' and m.get('coverage_status')!='complete':
        raise CoverageError('This public service does not certify full coverage.',report=deepcopy(m))
    fp=policy.freshness if policy else None
    if fp and fp.max_source_age is not None:
        stamps=frame['source_timestamp'] if 'source_timestamp' in frame else pd.Series([],dtype='datetime64[ns, UTC]')
        ages=pd.Timestamp.now(tz='UTC')-stamps
        if frame.empty or stamps.isna().any() or (ages< -pd.Timedelta(minutes=5)).any() or (ages>fp.max_source_age).any():
            raise StaleDataError('Source timestamps are absent or exceed max_source_age.')
        # Compound replies have their own source clocks. A fresh price cannot
        # certify the age of client-type or order-book data without a timestamp.
        for col in ('client_type_source_timestamp', 'order_book_source_timestamp'):
            if col in frame:
                other_age=pd.Timestamp.now(tz='UTC')-frame[col]
                if frame[col].isna().any() or (other_age< -pd.Timedelta(minutes=5)).any() or (other_age>fp.max_source_age).any():
                    raise StaleDataError(f'{col} is missing or exceeds max_source_age.')
    if m.get('is_stale'):
        try:warnings.warn('Returning explicitly permitted cached market data; this is not live data.',StaleDataWarning,stacklevel=3)
        except StaleDataWarning:pass
    return frame


def combine_frames(frames, schema, numeric='analysis'):
    """Perform the combine frames operation.
    
    Args:
        frames (Any): Input for the combine_frames operation.
        schema (Any): Input for the combine_frames operation.
        numeric (Any): Numeric conversion or output representation setting.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    if not frames:return empty_market_frame(schema,numeric)
    meta=deepcopy(frames[0].attrs.get('pydara',{}))
    bare=[]
    for f in frames:
        c=f.copy();c.attrs={};bare.append(c)
    out=pd.concat(bare,ignore_index=True)
    meta.update(components=[deepcopy(f.attrs.get('pydara',{})) for f in frames],
        returned_rows=len(out),is_stale=any(f.attrs.get('pydara',{}).get('is_stale') for f in frames),
        from_cache=all(f.attrs.get('pydara',{}).get('from_cache') for f in frames))
    out.attrs['pydara']=meta
    return out


from .extension_schemas import register as _register_extensions
_register_extensions(SCHEMAS, FrameSpec)
