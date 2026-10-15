"""Pure data plans for the optional families; same plans for both interfaces."""
from __future__ import annotations
from copy import deepcopy
from datetime import timedelta
from urllib.parse import quote
import pandas as pd
from pydara.tse._core.exceptions import InvalidArgumentError, UnsupportedCapabilityError, PointInTimeUnavailableError
from .dates import parse_date, parse_range
from .providers.public import instrument_plan, quote_spec, parse_quote
from .providers.extended import endpoint, parse_payload
from .providers.market import code_text, positive_int, flag
from .market_schemas import market_frame, combine_frames, SCHEMAS, META_STRINGS, META_TIMES, META_BOOLS

FUND_TYPES={'stock':'6','mixed':'7','fixed':'4','market_making':'11','vc':'12','reit':'14','project':'13','commodity':'5','private':'16','fund':'17'}


def table_plan(name, *, params=None, instrument=None, start=None, end=None, calendar='gregorian',
               include_jdate=False, namespace='public', numeric='analysis', schema_meta=None):
    """Perform the table plan operation.
    
    Args:
        name (Any): Input for the table_plan operation.
        params (Any): Input for the table_plan operation.
        instrument (Any): Instrument name or explicit instrument reference; ambiguity is not silently resolved.
        start (Any): Optional beginning of the requested date range.
        end (Any): Optional end of the requested date range.
        calendar (Any): Calendar used to parse or format dates.
        include_jdate (Any): Input for the table_plan operation.
        namespace (Any): Storage or frame metadata namespace.
        numeric (Any): Numeric conversion or output representation setting.
        schema_meta (Any): Input for the table_plan operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        UnsupportedCapabilityError: When the corresponding validation or operation fails."""
    flag(include_jdate,'include_jdate')
    lo,hi=parse_range(start,end,calendar=calendar)
    spec=endpoint(name,**(params or {}));packet=yield spec
    rows,schema=parse_payload(packet,spec)
    all_dates=[r.get('date') for r in rows if r.get('date') is not None]
    anchor=max(all_dates) if all_dates else None
    for row in rows:
        if instrument:
            row.update(symbol=instrument.symbol,ins_code=instrument.ins_code)
            for field in ('currency','quote_unit','quantity_unit'):
                if field in SCHEMAS[schema].strings:
                    row[field]=getattr(instrument,field)
            row['quality_flags']=tuple(dict.fromkeys((*row.get('quality_flags',()),*instrument.meta.quality_flags,
                       'identity_resolved_from_current_instrument_info')))
    if lo or hi:
        if any(r.get('date') is None for r in rows):
            raise UnsupportedCapabilityError('Cannot date-filter rows whose date was not reported.')
        rows=[r for r in rows if (lo is None or r['date']>=lo) and (hi is None or r['date']<=hi)]
    meta={'requested_range':{'start':str(lo) if lo else None,'end':str(hi) if hi else None},
          'identity_observation_id':instrument.meta.observation_id if instrument else None,
          'source_observed_range':{'start':str(min(all_dates)) if all_dates else None,'end':str(anchor) if anchor else None}}
    if schema=='adjusted_history':
        meta.update(adjustment='source',adjustment_method='tsetmc_chart_a1',anchor_date=str(anchor) if anchor else None,
                    raw_prices_overwritten=False,point_in_time=False,anchor_verified=False,
                    anchor_basis='last_date_in_source_response_not_server_certified')
    if schema_meta:meta.update(schema_meta)
    frame=market_frame(rows,schema,packet=packet,namespace=namespace,numeric=numeric,
                       include_jdate=include_jdate,extra_meta=meta)
    sort=[c for c in ('date','source_timestamp','source_position') if c in frame]
    if sort and len(frame):frame=frame.sort_values(sort,kind='stable').reset_index(drop=True)
    return frame


def instrument_table_plan(instrument, *, name, start=None, end=None, calendar='gregorian',include_jdate=False,
                          holder_id=None,days=90,limit=20, namespace='public',numeric='analysis'):
    # Validate ALL inputs before instrument search or any network.
    """Perform the instrument table plan operation.
    
    Args:
        instrument (Any): Instrument name or explicit instrument reference; ambiguity is not silently resolved.
        name (Any): Input for the instrument_table_plan operation.
        start (Any): Optional beginning of the requested date range.
        end (Any): Optional end of the requested date range.
        calendar (Any): Calendar used to parse or format dates.
        include_jdate (Any): Input for the instrument_table_plan operation.
        holder_id (Any): Input for the instrument_table_plan operation.
        days (Any): Input for the instrument_table_plan operation.
        limit (Any): Optional maximum result count, where supported.
        namespace (Any): Storage or frame metadata namespace.
        numeric (Any): Numeric conversion or output representation setting.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    parse_range(start,end,calendar=calendar);flag(include_jdate,'include_jdate')
    params={}
    if name=='extra.shareholders.history':
        params.update(holder=code_text(holder_id,'holder_id'),days=positive_int(days,'days',3650))
    if name=='extra.disclosures':params['limit']=positive_int(limit,'limit',1000)
    record=yield from instrument_plan(instrument,namespace=namespace)
    params['code']=record.ins_code
    if name=='extra.dividends':
        params['symbol']=quote(record.symbol.translate(str.maketrans({'\u06cc':'\u064a','\u06a9':'\u0643'})),safe='')
    return (yield from table_plan(name,params=params,instrument=record,start=start,end=end,calendar=calendar,
                 include_jdate=include_jdate,namespace=namespace,numeric=numeric))


def intraday_plan(instrument, *, kind, day=None,start=None,end=None,calendar='gregorian',
                  include_jdate=False,max_days=31,cancellation='as_reported',namespace='public',numeric='analysis'):
    """Perform the intraday plan operation.
    
    Args:
        instrument (Any): Instrument name or explicit instrument reference; ambiguity is not silently resolved.
        kind (Any): Input for the intraday_plan operation.
        day (Any): Input for the intraday_plan operation.
        start (Any): Optional beginning of the requested date range.
        end (Any): Optional end of the requested date range.
        calendar (Any): Calendar used to parse or format dates.
        include_jdate (Any): Input for the intraday_plan operation.
        max_days (Any): Input for the intraday_plan operation.
        cancellation (Any): Input for the intraday_plan operation.
        namespace (Any): Storage or frame metadata namespace.
        numeric (Any): Numeric conversion or output representation setting.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails.
        UnsupportedCapabilityError: When the corresponding validation or operation fails."""
    positive_int(max_days,'max_days',366);flag(include_jdate,'include_jdate')
    if cancellation!='as_reported':raise UnsupportedCapabilityError('Verified cancellation filtering is unavailable; as_reported preserves every row.')
    chosen=parse_date(day,calendar=calendar,name='day');lo,hi=parse_range(start,end,calendar=calendar)
    if chosen and (lo or hi):raise InvalidArgumentError('Use day OR start/end, not both.')
    if (lo is None)!=(hi is None):
        if lo is None:raise InvalidArgumentError('start is required when end is supplied.')
        hi=lo
    if chosen:lo=hi=chosen
    if lo and (hi-lo).days+1>max_days:raise InvalidArgumentError('Requested range exceeds max_days; split the range explicitly.')
    record=yield from instrument_plan(instrument,namespace=namespace)
    if lo is None and kind in ('states','thresholds'):
        # Latest available trading date is a reported date, not the computer date.
        spec=quote_spec(record.ins_code);packet=yield spec
        q=parse_quote(packet,spec,namespace,record)
        lo=hi=q.trade_date
        if lo is None:raise UnsupportedCapabilityError('The source has not reported a trading date.')
    if lo is None:
        return (yield from table_plan('extra.'+kind,params={'code':record.ins_code},instrument=record,
                     include_jdate=include_jdate,namespace=namespace,numeric=numeric))
    frames=[]
    for n in range((hi-lo).days+1):
        date=lo+timedelta(days=n)
        name='extra.'+kind+('.day' if kind in ('trades','book') else '')
        frame=yield from table_plan(name,params={'code':record.ins_code,'day':date.strftime('%Y%m%d')},instrument=record,
            namespace=namespace,numeric=numeric,include_jdate=include_jdate)
        frames.append(frame)
    schema={'trades':'trades','book':'order_book','states':'instrument_states','thresholds':'thresholds'}[kind]
    result=combine_frames(frames,schema,numeric)
    result.attrs['pydara'].update(requested_range={'start':str(lo),'end':str(hi)},
        requests_for_calendar_days=True,empty_days_not_classified=True)
    return result


def funds_plan(category='stock', *, namespace='public',numeric='analysis'):
    """Perform the funds plan operation.
    
    Args:
        category (Any): Input for the funds_plan operation.
        namespace (Any): Storage or frame metadata namespace.
        numeric (Any): Numeric conversion or output representation setting.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails."""
    if category is None:cats=list(FUND_TYPES)
    elif isinstance(category,str) and category.lower() in FUND_TYPES:cats=[category.lower()]
    elif str(category) in FUND_TYPES.values():cats=[k for k,v in FUND_TYPES.items() if v==str(category)]
    else:raise InvalidArgumentError(f'category must be one of {tuple(FUND_TYPES)}, its code, or None.')
    frames=[]
    for cat in cats:
        frame=yield from table_plan('extra.funds',params={'category':FUND_TYPES[cat]},namespace=namespace,numeric=numeric)
        frame['category']=pd.Series([cat]*len(frame),dtype='string')
        frames.append(frame)
    return combine_frames(frames,'funds',numeric)


def fund_plan(registration_no, *, history=False,start=None,end=None,calendar='gregorian',include_jdate=False,namespace='public',numeric='analysis'):
    """Perform the fund plan operation.
    
    Args:
        registration_no (Any): Input for the fund_plan operation.
        history (Any): Input for the fund_plan operation.
        start (Any): Optional beginning of the requested date range.
        end (Any): Optional end of the requested date range.
        calendar (Any): Calendar used to parse or format dates.
        include_jdate (Any): Input for the fund_plan operation.
        namespace (Any): Storage or frame metadata namespace.
        numeric (Any): Numeric conversion or output representation setting.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    reg=code_text(registration_no,'registration_no')
    return (yield from table_plan('extra.nav' if history else 'extra.fund',params={'registration':reg},
        start=start,end=end,calendar=calendar,include_jdate=include_jdate,namespace=namespace,numeric=numeric))


def options_plan(underlying=None, *, namespace='public',numeric='analysis'):
    """Perform the options plan operation.
    
    Args:
        underlying (Any): Input for the options_plan operation.
        namespace (Any): Storage or frame metadata namespace.
        numeric (Any): Numeric conversion or output representation setting.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    record=(yield from instrument_plan(underlying,namespace=namespace)) if underlying is not None else None
    frame=yield from table_plan('extra.options',namespace=namespace,numeric=numeric)
    if record is not None:
        frame=frame.loc[frame['underlying_ins_code']==record.ins_code].reset_index(drop=True)
        frame.attrs['pydara'].update(underlying_ins_code=record.ins_code,filter_applied_locally=True)
    return frame


def instruments_plan(*,market=None,include_inactive=False,changed_since=None,backend='auto',namespace='public',numeric='analysis'):
    """Perform the instruments plan operation.
    
    Args:
        market (Any): Market selection or filtering constraint.
        include_inactive (Any): Whether inactive instruments should be retained.
        changed_since (Any): Input for the instruments_plan operation.
        backend (Any): Input for the instruments_plan operation.
        namespace (Any): Storage or frame metadata namespace.
        numeric (Any): Numeric conversion or output representation setting.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        UnsupportedCapabilityError: When the corresponding validation or operation fails."""
    flag(include_inactive,'include_inactive')
    if include_inactive or changed_since is not None:
        raise UnsupportedCapabilityError('The public watch is a current observed universe, not an inactive/historical instrument registry.')
    from .market import market_watch_plan
    frame=yield from market_watch_plan(market=market,backend=backend,namespace=namespace,numeric=numeric)
    columns=['ins_code','symbol','name','market','raw_flow','sector_code','instrument_id','instrument_type',*META_STRINGS,*META_TIMES,*META_BOOLS,'quality_flags','source_fields']
    out=frame.loc[:,columns].copy();out.attrs=deepcopy(frame.attrs)
    out.attrs['pydara'].update(schema_id='observed_instruments',universe='current_market_watch_only',complete_instrument_registry=False,projection=columns)
    return out


def futures_plan(*,source='tse_exchange',namespace='public',numeric='analysis'):
    """Perform the futures plan operation.
    
    Args:
        source (Any): Input for the futures_plan operation.
        namespace (Any): Storage or frame metadata namespace.
        numeric (Any): Numeric conversion or output representation setting.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        UnsupportedCapabilityError: When the corresponding validation or operation fails."""
    if source!='tse_exchange':
        raise UnsupportedCapabilityError('No verified public TSETMC futures feed is configured; select source="tse_exchange" explicitly.')
    frame=yield from table_plan('extra.futures',namespace=namespace,numeric=numeric)
    frame['source']=pd.Series(['tse_exchange']*len(frame),dtype='string')
    frame.attrs['pydara'].update(source='tse_exchange',source_host='webgw.tse.ir',gateway='separate_from_tsetmc')
    return frame
