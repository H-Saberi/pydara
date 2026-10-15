"""Pure, shared request plans for market watch, participant flows and indices."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime
import math
import pandas as pd
from pydara.tse._core.models import InstrumentRef, Market
from pydara.tse._core.exceptions import (InvalidArgumentError, UnknownInstrumentError,
    AmbiguousInstrumentError, UnsupportedCapabilityError, PointInTimeUnavailableError,
    DataQualityError)
from .dates import parse_date, parse_range
from .providers.public import instrument_plan, normalize_symbol
from .providers.market import (request_spec, parse_market_payload, market_value, flow_of,
    positive_int, code_text, sector_text, flag)
from .market_schemas import (market_frame, combine_frames, PARTICIPANT_COUNTS,
    PARTICIPANT_NUMBERS, finish_market)


def _table(packet,spec,namespace,numeric,*,include_jdate=False):
    """Process internal table data.
    
    Args:
        packet (Any): Response packet received from a provider.
        spec (Any): Request or schema specification.
        namespace (Any): Storage or frame metadata namespace.
        numeric (Any): Numeric conversion or output representation setting.
        include_jdate (Any): Input for the _table operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    parsed=parse_market_payload(packet,spec)
    frame=market_frame(parsed.rows,parsed.schema,packet=packet,namespace=namespace,numeric=numeric,
        include_jdate=include_jdate,extra_meta={'identical_duplicates_removed':parsed.identical_duplicates})
    return frame,parsed


def one_table_plan(endpoint,*,params=None,namespace='public',numeric='analysis',include_jdate=False):
    """Perform the one table plan operation.
    
    Args:
        endpoint (Any): Input for the one_table_plan operation.
        params (Any): Input for the one_table_plan operation.
        namespace (Any): Storage or frame metadata namespace.
        numeric (Any): Numeric conversion or output representation setting.
        include_jdate (Any): Input for the one_table_plan operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    spec=request_spec(endpoint,**(params or {}));packet=yield spec
    return _table(packet,spec,namespace,numeric,include_jdate=include_jdate)[0]


def _selected(frame,mask,**meta):
    """Process internal selected data.
    
    Args:
        frame (Any): DataFrame to convert, validate, process or store.
        mask (Any): Input for the _selected operation.
        meta: Additional arguments for this operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    out=frame.loc[mask].reset_index(drop=True).copy()
    out.attrs=deepcopy(frame.attrs)
    out.attrs['pydara'].update(returned_rows=len(out),**meta)
    return out


def _market_filter(frame,market):
    """Process internal market filter data.
    
    Args:
        frame (Any): DataFrame to convert, validate, process or store.
        market (Any): Market selection or filtering constraint.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        UnsupportedCapabilityError: When the corresponding validation or operation fails."""
    if market is None:
        return frame
    missing = int(frame['market'].isna().sum())
    mask = frame['market'].notna() & frame['market'].astype('string').eq(str(market))
    return _selected(frame, mask.fillna(False), requested_market=str(market),
                     unknown_market_rows_excluded=missing,
                     market_filter_incomplete=bool(missing))


def watch_tables_plan(*,market=None,include_order_book=False,include_client_types=False,
                      show_traded=False,backend='auto',namespace='public',numeric='analysis'):
    """Perform the watch tables plan operation.
    
    Args:
        market (Any): Market selection or filtering constraint.
        include_order_book (Any): Input for the watch_tables_plan operation.
        include_client_types (Any): Input for the watch_tables_plan operation.
        show_traded (Any): Input for the watch_tables_plan operation.
        backend (Any): Input for the watch_tables_plan operation.
        namespace (Any): Storage or frame metadata namespace.
        numeric (Any): Numeric conversion or output representation setting.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails."""
    market=market_value(market)
    flag(include_order_book,'include_order_book');flag(include_client_types,'include_client_types');flag(show_traded,'show_traded')
    if not isinstance(backend,str) or backend not in ('auto','json','legacy'):
        raise InvalidArgumentError('backend must be auto, json or legacy.')
    ep='market.watch.legacy' if backend=='legacy' else 'market.watch'
    server_market = market.value if market is not None and backend != 'legacy' and market.value in ('TSE', 'IFB') else None
    spec=request_spec(ep,books=include_order_book,traded=show_traded,market=server_market);packet=yield spec
    frame,parsed=_table(packet,spec,namespace,numeric)
    if server_market is not None and not frame.empty:
        # The server-side market selector is evidence only if its own labeled
        # rows do not contradict it. On contradiction, use verified row labels
        # and leave unknowns unknown (never force them into a market).
        known = frame['market'].dropna().astype(str)
        conflicting = int((known != server_market).sum())
        filled = 0
        if not conflicting:
            missing = frame['market'].isna()
            filled = int(missing.sum())
            if filled:
                frame.loc[missing, 'market'] = server_market
                frame['quality_flags'] = [
                    tuple(dict.fromkeys((*flags, 'market_from_server_selector'))) if inferred else flags
                    for flags, inferred in zip(frame['quality_flags'], missing)
                ]
        frame.attrs['pydara'].update(
            market_selection_basis=('server_request_market_parameter' if not conflicting
                                    else 'reported_row_values_only'),
            market_labels_from_server_selector=filled,
            market_selector_conflicting_rows=conflicting,
        )
    first_meta=None
    if backend=='auto' and frame.empty:
        # Only a valid empty response causes fallback. Authentication/schema/HTTP
        # failures propagate; no hidden attempts to evade access restrictions.
        first_meta=deepcopy(frame.attrs['pydara'])
        spec=request_spec('market.watch.legacy');packet=yield spec
        frame,parsed=_table(packet,spec,namespace,numeric)
    if first_meta:
        frame.attrs['pydara'].update(fallback_reason='empty_json_response',attempted_components=[first_meta])
    frame=_market_filter(frame,market)
    if show_traded:
        frame=_selected(frame,frame['trade_count'].fillna(0)>0,show_traded=True)
    books=market_frame(parsed.books or [],'market_order_book',packet=packet,namespace=namespace,numeric=numeric)
    books=_selected(books,books['ins_code'].isin(frame['ins_code']))
    frame.attrs['pydara']['order_book_rows']=len(books)
    frame.attrs['pydara']['backend']='legacy' if spec.endpoint_id.endswith('.legacy') else 'json'
    if include_order_book:
        for depth in range(1,6):
            for col in ('bid_price','bid_volume','ask_price','ask_volume','bid_order_count','ask_order_count'):
                source=books.loc[books['depth']==depth,['ins_code',col]].set_index('ins_code')[col]
                frame[f'{col}_{depth}']=frame['ins_code'].map(source).astype(books[col].dtype)
        frame['order_book_fetched_at']=pd.Series([packet.fetched_at]*len(frame),dtype='datetime64[ns, UTC]')
        frame['order_book_source_timestamp']=pd.Series(pd.NaT,index=frame.index,dtype='datetime64[ns, UTC]')
        has=set(books['ins_code'])
        frame['quality_flags']=[tuple(dict.fromkeys((*fs,'order_book_source_timestamp_unknown',
                *(() if code in has else ('order_book_not_returned',))))) for code,fs in zip(frame['ins_code'],frame['quality_flags'])]
    if include_client_types:
        cs=request_spec('clients.market');cp=yield cs
        cframe,_=_table(cp,cs,namespace,numeric)
        frame=_join_clients(frame,cframe)
    return frame,books


def market_watch_plan(**kwargs):
    """Perform the market watch plan operation.
    
    Args:
        kwargs: Additional keyword arguments forwarded to the wrapped operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    frame,_=yield from watch_tables_plan(**kwargs)
    return frame


def market_order_book_plan(*,market=None,backend='auto',namespace='public',numeric='analysis'):
    """Perform the market order book plan operation.
    
    Args:
        market (Any): Market selection or filtering constraint.
        backend (Any): Input for the market_order_book_plan operation.
        namespace (Any): Storage or frame metadata namespace.
        numeric (Any): Numeric conversion or output representation setting.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    frame,books=yield from watch_tables_plan(market=market,include_order_book=True,backend=backend,namespace=namespace,numeric=numeric)
    books.attrs['pydara']['watch_component']=deepcopy(frame.attrs['pydara'])
    return books


def _join_clients(frame,clients):
    """Process internal join clients data.
    
    Args:
        frame (Any): DataFrame to convert, validate, process or store.
        clients (Any): Input for the _join_clients operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    metadata=deepcopy(frame.attrs['pydara'])
    frame=frame.copy()
    lookup=clients.set_index('ins_code')
    for col in (*PARTICIPANT_COUNTS,*PARTICIPANT_NUMBERS,'buy_ddd_count','buy_ddd_volume'):
        frame[col]=frame['ins_code'].map(lookup[col]).astype(clients[col].dtype)
    for col,dest in [('date','client_type_date'),('source_timestamp','client_type_source_timestamp'),
                     ('fetched_at','client_type_fetched_at'),('observation_id','client_type_observation_id'),
                     ('is_stale','client_type_is_stale'),('from_cache','client_type_from_cache')]:
        frame[dest]=frame['ins_code'].map(lookup[col]).astype(clients[col].dtype)
    flags=[]
    for _,row in frame.iterrows():
        fs=list(row['quality_flags'])
        if row['ins_code'] not in lookup.index:fs.append('client_types_not_returned')
        else:
            fs.extend(lookup.loc[row['ins_code'],'quality_flags'])
            fs.append('combined_responses_not_atomic')
            ct=lookup.loc[row['ins_code'],'date']
            if pd.notna(ct) and pd.notna(row['date']) and ct!=row['date']:fs.append('component_dates_differ')
        flags.append(tuple(dict.fromkeys(fs)))
    frame['quality_flags']=flags
    metadata.update(components=[metadata.copy(),deepcopy(clients.attrs['pydara'])],
        is_stale=metadata.get('is_stale',False) or clients.attrs['pydara'].get('is_stale',False),
        composite_snapshot=True,components_are_simultaneous=False)
    frame.attrs['pydara']=metadata
    return frame


def market_overview_plan(*,market=Market.TSE,namespace='public',numeric='analysis'):
    """Perform the market overview plan operation.
    
    Args:
        market (Any): Market selection or filtering constraint.
        namespace (Any): Storage or frame metadata namespace.
        numeric (Any): Numeric conversion or output representation setting.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    flow=flow_of(market)
    return (yield from one_table_plan('market.overview',params={'flow':flow},namespace=namespace,numeric=numeric))


def market_map_plan(*,sector_code=None,limit=9999,namespace='public',numeric='analysis'):
    """Perform the market map plan operation.
    
    Args:
        sector_code (Any): Input for the market_map_plan operation.
        limit (Any): Optional maximum result count, where supported.
        namespace (Any): Storage or frame metadata namespace.
        numeric (Any): Numeric conversion or output representation setting.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    sector=None if sector_code is None else sector_text(sector_code)
    positive_int(limit,'limit',10000)
    return (yield from one_table_plan('market.map',params={'size':limit,'sector':sector},namespace=namespace,numeric=numeric))


def sectors_plan(*,namespace='public',numeric='analysis'):
    """Perform the sectors plan operation.
    
    Args:
        namespace (Any): Storage or frame metadata namespace.
        numeric (Any): Numeric conversion or output representation setting.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    return (yield from one_table_plan('market.sectors',namespace=namespace,numeric=numeric))


def sector_instruments_plan(sector_code,*,namespace='public',numeric='analysis'):
    """Perform the sector instruments plan operation.
    
    Args:
        sector_code (Any): Input for the sector_instruments_plan operation.
        namespace (Any): Storage or frame metadata namespace.
        numeric (Any): Numeric conversion or output representation setting.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    return (yield from one_table_plan('market.related',params={'sector':sector_text(sector_code)},namespace=namespace,numeric=numeric))


def key_statistics_plan(*,ins_code=None,namespace='public',numeric='analysis'):
    """Perform the key statistics plan operation.
    
    Args:
        ins_code (Any): Input for the key_statistics_plan operation.
        namespace (Any): Storage or frame metadata namespace.
        numeric (Any): Numeric conversion or output representation setting.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    code=None if ins_code is None else code_text(ins_code,'ins_code')
    frame=yield from one_table_plan('market.statistics',namespace=namespace,numeric=numeric)
    if code:frame=_selected(frame,frame['ins_code']==code,filter_applied_locally=True)
    return frame


def participant_plan(instrument,*,day=None,calendar='gregorian',include_jdate=False,
                     history=False,start=None,end=None,namespace='public',numeric='analysis'):
    """Perform the participant plan operation.
    
    Args:
        instrument (Any): Instrument name or explicit instrument reference; ambiguity is not silently resolved.
        day (Any): Input for the participant_plan operation.
        calendar (Any): Calendar used to parse or format dates.
        include_jdate (Any): Input for the participant_plan operation.
        history (Any): Input for the participant_plan operation.
        start (Any): Optional beginning of the requested date range.
        end (Any): Optional end of the requested date range.
        namespace (Any): Storage or frame metadata namespace.
        numeric (Any): Numeric conversion or output representation setting.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    flag(include_jdate,'include_jdate')
    lo,hi=parse_range(start,end,calendar=calendar)
    selected=parse_date(day,calendar=calendar,name='day')
    record=yield from instrument_plan(instrument,namespace=namespace)
    if history:ep='clients.history';params={'code':record.ins_code}
    elif selected:ep='clients.day';params={'code':record.ins_code,'day':selected.strftime('%Y%m%d')}
    else:ep='clients.latest';params={'code':record.ins_code}
    spec=request_spec(ep,**params);packet=yield spec
    parsed=parse_market_payload(packet,spec)
    observed_dates=[r['date'] for r in parsed.rows if r['date'] is not None]
    rows=[]
    for original in parsed.rows:
        r=dict(original)
        if (lo and r['date'] is not None and r['date']<lo) or (hi and r['date'] is not None and r['date']>hi):continue
        r.update(symbol=record.symbol,market=record.market,currency=record.currency,
                 quote_unit=record.quote_unit,quantity_unit=record.quantity_unit)
        r['quality_flags']=tuple(dict.fromkeys((*r['quality_flags'],*record.meta.quality_flags,
                 'identity_resolved_from_current_instrument_info',*(('stale_identity_response',) if record.meta.is_stale else ()))))
        rows.append(r)
    frame=market_frame(rows,'client_types',packet=packet,namespace=namespace,numeric=numeric,include_jdate=include_jdate,
        extra_meta={'requested_range':{'start':str(lo) if lo else None,'end':str(hi) if hi else None},
                    'identity_observation_id':record.meta.observation_id,
                    'identity_fetched_at':record.meta.retrieved_at.isoformat(),
                    'source_observed_range':{'start':str(min(observed_dates)) if observed_dates else None,
                                             'end':str(max(observed_dates)) if observed_dates else None},
                    'retrieval_strategy':'full_history_then_local_filter' if history else 'single_endpoint'})
    if record.meta.is_stale:frame.attrs['pydara']['is_stale']=True
    return frame


def market_clients_plan(*,market=None,backend='auto',namespace='public',numeric='analysis'):
    """Perform the market clients plan operation.
    
    Args:
        market (Any): Market selection or filtering constraint.
        backend (Any): Input for the market_clients_plan operation.
        namespace (Any): Storage or frame metadata namespace.
        numeric (Any): Numeric conversion or output representation setting.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    selected=market_value(market)
    frame=yield from one_table_plan('clients.market',namespace=namespace,numeric=numeric)
    if selected is not None:
        watch=yield from market_watch_plan(market=selected,backend=backend,namespace=namespace,numeric=numeric)
        frame=_selected(frame,frame['ins_code'].isin(watch['ins_code']),
            filtered_by_current_watch=True,identity_component=deepcopy(watch.attrs['pydara']))
        frame['market']=pd.Series(str(selected),index=frame.index,dtype='string')
        lookup=watch.set_index('ins_code')['symbol']
        frame['symbol']=frame['ins_code'].map(lookup).astype('string')
        frame.attrs['pydara']['is_stale'] |= watch.attrs['pydara']['is_stale']
    return frame


def indices_plan(*,market=Market.TSE,namespace='public',numeric='analysis'):
    """Perform the indices plan operation.
    
    Args:
        market (Any): Market selection or filtering constraint.
        namespace (Any): Storage or frame metadata namespace.
        numeric (Any): Numeric conversion or output representation setting.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        DataQualityError: When the corresponding validation or operation fails."""
    m=market_value(market)
    flows=('1','2') if m is None else (flow_of(m),)
    frames=[]
    for flow in flows:
        f=yield from one_table_plan('indices.list',params={'flow':flow},namespace=namespace,numeric=numeric)
        frames.append(f)
    frame=combine_frames(frames,'indices',numeric)
    frame=frame.sort_values(['market','index_code'],kind='stable').reset_index(drop=True)
    if frame['index_code'].duplicated().any():raise DataQualityError('Index identifier appears in several market catalogs.')
    return frame


def _index_query(index):
    """Process internal index query data.
    
    Args:
        index (Any): Input for the _index_query operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails."""
    if isinstance(index,InstrumentRef):
        if index.kind!='ins_code':raise InvalidArgumentError('For an index reference use InstrumentRef.by_ins_code().')
        return index.value,True
    if isinstance(index,bool) or not isinstance(index,(str,int)):raise InvalidArgumentError('index must be a name or an exact string/int code.')
    if isinstance(index,int):return code_text(index,'index'),True
    clean=normalize_symbol(index)
    return (code_text(clean,'index'),True) if clean.isascii() and clean.isdigit() else (clean,False)


def resolve_index_plan(index,*,market=Market.TSE,namespace='public',numeric='analysis'):
    """Resolve index plan.
    
    Args:
        index (Any): Input for the resolve_index_plan operation.
        market (Any): Market selection or filtering constraint.
        namespace (Any): Storage or frame metadata namespace.
        numeric (Any): Numeric conversion or output representation setting.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        AmbiguousInstrumentError: When the corresponding validation or operation fails.
        UnknownInstrumentError: When the corresponding validation or operation fails."""
    query,is_code=_index_query(index)
    frame=yield from indices_plan(market=market,namespace=namespace,numeric=numeric)
    normalized=frame['name'].fillna('').map(lambda x:normalize_symbol(x) if x else '')
    matched=_selected(frame,frame['index_code']==query if is_code else normalized==query)
    if matched.empty:raise UnknownInstrumentError('Index not found in the selected current catalog. Use get_indices(market=None) to inspect codes/names.')
    if len(matched)>1:raise AmbiguousInstrumentError('Index name is ambiguous; pass index_code.',candidates=tuple(matched['index_code']))
    return matched


def search_indices_plan(query,*,market=Market.TSE,limit=None,namespace='public',numeric='analysis'):
    """Search indices plan.
    
    Args:
        query (Any): Instrument or market search text.
        market (Any): Market selection or filtering constraint.
        limit (Any): Optional maximum result count, where supported.
        namespace (Any): Storage or frame metadata namespace.
        numeric (Any): Numeric conversion or output representation setting.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    q=normalize_symbol(query)
    if limit is not None:positive_int(limit,'limit')
    frame=yield from indices_plan(market=market,namespace=namespace,numeric=numeric)
    mask=frame['name'].fillna('').map(lambda x:q in normalize_symbol(x) if x else False)
    frame=_selected(frame,mask)
    if limit is not None:frame=_selected(frame,frame.index<limit)
    return frame


def index_data_plan(index,*,kind='history',market=Market.TSE,start=None,end=None,
                    calendar='gregorian',include_jdate=False,day=None,as_of=None,
                    namespace='public',numeric='analysis'):
    """Perform the index data plan operation.
    
    Args:
        index (Any): Input for the index_data_plan operation.
        kind (Any): Input for the index_data_plan operation.
        market (Any): Market selection or filtering constraint.
        start (Any): Optional beginning of the requested date range.
        end (Any): Optional end of the requested date range.
        calendar (Any): Calendar used to parse or format dates.
        include_jdate (Any): Input for the index_data_plan operation.
        day (Any): Input for the index_data_plan operation.
        as_of (Any): Requested economic effective date; check endpoint support.
        namespace (Any): Storage or frame metadata namespace.
        numeric (Any): Numeric conversion or output representation setting.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        PointInTimeUnavailableError: When the corresponding validation or operation fails.
        UnsupportedCapabilityError: When the corresponding validation or operation fails."""
    lo,hi=parse_range(start,end,calendar=calendar);flag(include_jdate,'include_jdate')
    if as_of is not None:raise PointInTimeUnavailableError('Historical index membership is not provided by this endpoint.')
    if day is not None:raise UnsupportedCapabilityError('The public index intraday endpoint provides only the latest available session; day cannot be selected.')
    identity=yield from resolve_index_plan(index,market=market,namespace=namespace,numeric=numeric)
    item=identity.iloc[0];code=item['index_code']
    ep={'history':'indices.history','intraday':'indices.intraday','members':'indices.members'}[kind]
    spec=request_spec(ep,code=code);packet=yield spec
    parsed=parse_market_payload(packet,spec)
    rows=[]
    for r in parsed.rows:
        r=dict(r)
        if kind=='history' and ((lo and r['date']<lo) or (hi and r['date']>hi)):continue
        if kind!='members':r.update(name=item['name'],market=item['market'])
        r['quality_flags']=tuple(dict.fromkeys((*r.get('quality_flags',()),'index_identity_from_current_catalog',
             *(('stale_identity_response',) if identity.attrs.get('pydara',{}).get('is_stale') else ()))))
        rows.append(r)
    frame=market_frame(rows,parsed.schema,packet=packet,namespace=namespace,numeric=numeric,
        include_jdate=include_jdate,extra_meta={
            'identity_component':deepcopy(identity.attrs.get('pydara',{})),
            'requested_range':{'start':str(lo) if lo else None,'end':str(hi) if hi else None},
            'identical_duplicates_removed':parsed.identical_duplicates})
    if identity.attrs.get('pydara',{}).get('is_stale'):frame.attrs['pydara']['is_stale']=True
    return frame


def index_impact_plan(*,market=Market.TSE,limit=7,namespace='public',numeric='analysis'):
    """Perform the index impact plan operation.
    
    Args:
        market (Any): Market selection or filtering constraint.
        limit (Any): Optional maximum result count, where supported.
        namespace (Any): Storage or frame metadata namespace.
        numeric (Any): Numeric conversion or output representation setting.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    flow=flow_of(market);positive_int(limit,'limit',1000)
    frame=yield from one_table_plan('indices.impact',params={'flow':flow,'top':limit},namespace=namespace,numeric=numeric)
    frame.attrs['pydara'].update(mapping_status='experimental_source_fields_only',
        note='source_fields preserves the full response; impact_points is intentionally unknown until the live field semantics are verified.')
    return frame


def poll_options(interval,max_updates):
    """Perform the poll options operation.
    
    Args:
        interval (Any): Input for the poll_options operation.
        max_updates (Any): Input for the poll_options operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails."""
    if isinstance(interval,bool) or not isinstance(interval,(int,float)) or not math.isfinite(interval) or interval<1:
        raise InvalidArgumentError('interval must be a finite number of at least 1 second; this is a local safeguard, not an official service limit.')
    if max_updates is not None:positive_int(max_updates,'max_updates',1000000)
    return interval,max_updates
