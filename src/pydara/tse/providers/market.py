"""Reviewed public market/client-type/index routes; independent implementation.

Only the routes in ENDPOINTS are accepted. Original response bytes remain in the
existing bounded cache. Missing dates/units are never inferred from fetch time.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
from urllib.parse import urlencode
from pydara.tse._core.exceptions import (InvalidArgumentError, SchemaMismatchError,
    DataQualityError, UnsupportedCapabilityError)
from pydara.tse._core.models import Market
from ..transport import RequestSpec, decode, _unique_object
from .public import identifier, normalize_symbol, parse_source_time

ENDPOINTS = {
 'market.watch':('ClosingPrice/GetMarketWatch','marketwatch',0),
 'market.watch.legacy':('https://old.tsetmc.com/tsev2/data/MarketWatchInit.aspx?h=0&r=0','',0),
 'market.overview':('MarketData/GetMarketOverview/{flow}','marketOverview',0),
 'market.map':('ClosingPrice/GetMarketMap','',0),
 'market.sectors':('MarketData/GetSectorsSummary','sectorSummeries',3600),
 'market.related':('ClosingPrice/GetRelatedCompany/{sector}','relatedCompany',60),
 'market.statistics':('MarketData/GetInstValueAllInstAllParam','instValueAllInstAllParam',3600),
 'clients.latest':('ClientType/GetClientType/{code}/1/0','clientType',0),
 'clients.history':('ClientType/GetClientTypeHistory/{code}','clientType',3600),
 'clients.day':('ClientType/GetClientTypeHistory/{code}/{day}','clientType',3600),
 'clients.market':('ClientType/GetClientTypeAll','clientTypeAllDto',0),
 'indices.list':('Index/GetIndexB1LastAll/All/{flow}','indexB1',60),
 'indices.history':('Index/GetIndexB2History/{code}','indexB2',3600),
 'indices.intraday':('Index/GetIndexB1LastDay/{code}','indexB1',0),
 'indices.members':('ClosingPrice/GetIndexCompany/{code}','indexCompany',60),
 'indices.impact':('Index/GetInstEffect/0/{flow}/{top}','instEffect',0),
}

def market_value(value, *, allow_none=True):
    """Perform the market value operation.
    
    Args:
        value (Any): Input for the market_value operation.
        allow_none (Any): Input for the market_value operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails.
        UnsupportedCapabilityError: When the corresponding validation or operation fails."""
    if value is None and allow_none:return None
    if isinstance(value,Market):m=value
    elif isinstance(value,str):
        aliases={'tse':Market.TSE,'ifb':Market.IFB,'base':Market.BASE,
                 '\u0628\u0648\u0631\u0633':Market.TSE,'\u0641\u0631\u0627\u0628\u0648\u0631\u0633':Market.IFB}
        m=aliases.get(value.strip().lower())
        if m is None:raise InvalidArgumentError('market must be Market.TSE, Market.IFB, Market.BASE or a documented name.')
    else:raise InvalidArgumentError('market must be a Market or documented string.')
    if m not in (Market.TSE,Market.IFB,Market.BASE):
        raise UnsupportedCapabilityError('This release supports TSE/IFB market data, not all Market enum values.')
    return m

def flow_of(market):
    """Perform the flow of operation.
    
    Args:
        market (Any): Market selection or filtering constraint.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        UnsupportedCapabilityError: When the corresponding validation or operation fails."""
    m=market_value(market,allow_none=False)
    if m not in (Market.TSE,Market.IFB):
        raise UnsupportedCapabilityError('This endpoint supports TSE or IFB, not a separate BASE index/overview.')
    return '1' if m==Market.TSE else '2'

def positive_int(value,name,maximum=10000):
    """Require a positive value for int.
    
    Args:
        value (Any): Input for the positive_int operation.
        name (Any): Input for the positive_int operation.
        maximum (Any): Input for the positive_int operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails."""
    if isinstance(value,bool) or not isinstance(value,int) or not 1<=value<=maximum:
        raise InvalidArgumentError(f'{name} must be an integer in 1..{maximum}.')
    return value

def flag(value,name):
    """Perform the flag operation.
    
    Args:
        value (Any): Input for the flag operation.
        name (Any): Input for the flag operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails."""
    if not isinstance(value,bool):raise InvalidArgumentError(f'{name} must be bool.')
    return value

def code_text(value,name='identifier'):
    # Floats and booleans are never accepted for caller-supplied identifiers.
    """Perform the code text operation.
    
    Args:
        value (Any): Input for the code_text operation.
        name (Any): Input for the code_text operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails."""
    try:return identifier(value)
    except SchemaMismatchError as e:raise InvalidArgumentError(f'{name}: use positive digits as text or int, not float.') from e

def sector_text(value):
    """Perform the sector text operation.
    
    Args:
        value (Any): Input for the sector_text operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails."""
    if not isinstance(value,str) or not value.strip() or len(value.strip())>20:
        raise InvalidArgumentError('sector_code must be the exact short string returned by get_sectors().')
    x=value.strip()
    if not all(c.isascii() and c.isalnum() for c in x):raise InvalidArgumentError('Invalid sector code.')
    return x

def request_spec(endpoint, **params):
    """Perform the request spec operation.
    
    Args:
        endpoint (Any): Input for the request_spec operation.
        params: Additional arguments for this operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    path,root,age=ENDPOINTS[endpoint]
    if endpoint=='market.watch':
        # The provider's documented market watch selector is 0=all, 1=TSE,
        # 2=IFB. Do not synthesize BASE membership from this selector.
        requested = params.get('market')
        market_code = {None: 0, 'TSE': 1, 'IFB': 2}.get(requested)
        if market_code is None:
            raise InvalidArgumentError('Market-watch server selector supports TSE/IFB only.')
        query=[('market',market_code),('industrialGroup','')]+[(f'paperTypes[{i}]',i+1) for i in range(9)]
        query += [('showTraded','true' if params.get('traded',False) else 'false'),
                  ('withBestLimits','true' if params.get('books',False) else 'false'),('hEven',0),('RefID',0)]
        path+='?'+urlencode(query)
    elif endpoint=='market.map':
        path+='?'+urlencode({'market':0,'size':params['size'],'sector':params.get('sector') or 0,
                            'typeSelected':1,'hEven':0})
    else:path=path.format(**params)
    return RequestSpec(endpoint,path,root,float(age))

def pick(row,*names,required=False):
    """Select the requested value.
    
    Args:
        row (Any): Input for the pick operation.
        required (Any): Input for the pick operation.
        names: Additional arguments for this operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        SchemaMismatchError: When the corresponding validation or operation fails."""
    for name in names:
        if name in row and row[name] is not None:return row[name]
    if required and not any(n in row for n in names):raise SchemaMismatchError(f'Missing required field {names[0]}.')
    return None

def num(value, name, *, signed=False, integer=False, blank=False):
    """Extract numeric data from the requested value.
    
    Args:
        value (Any): Input for the num operation.
        name (Any): Input for the num operation.
        signed (Any): Input for the num operation.
        integer (Any): Input for the num operation.
        blank (Any): Input for the num operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        DataQualityError: When the corresponding validation or operation fails.
        SchemaMismatchError: When the corresponding validation or operation fails."""
    if value is None:return None
    if blank and value in ('','-'):return None
    if isinstance(value,bool) or not isinstance(value,(str,int,Decimal)):
        raise SchemaMismatchError(f'{name}: expected a JSON number or numeric string.')
    try:d=Decimal(value)
    except (InvalidOperation,ValueError) as e:raise SchemaMismatchError(f'{name}: invalid number.') from e
    if not d.is_finite() or (not signed and d<0):raise DataQualityError(f'{name}: nonfinite or negative value.')
    if integer and d!=d.to_integral_value():raise DataQualityError(f'{name}: expected an integer.')
    if integer and abs(d)>2**63-1:raise DataQualityError(f'{name}: integer exceeds Int64.')
    return int(d) if integer else d

def text(value,field='text'):
    """Extract text from the requested value.
    
    Args:
        value (Any): Input for the text operation.
        field (Any): Requested data field.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        SchemaMismatchError: When the corresponding validation or operation fails."""
    if value is None:return None
    if not isinstance(value,(str,int)) or isinstance(value,bool):raise SchemaMismatchError(f'{field}: expected text.')
    return str(value)

def source_fields(row):
    # Preserve unknown source fields as JSON text, without inventing field meanings.
    """Perform the source fields operation.
    
    Args:
        row (Any): Input for the source_fields operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    return json.dumps(row,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)

def bound_code(value, expected, flags):
    """A single-instrument route may return a zero placeholder; never apply to a list."""
    if value is None or value=='' or (not isinstance(value,bool) and value in (0,'0',Decimal(0))):
        flags.append('response_identifier_missing_or_zero');return expected
    if isinstance(value,Decimal):
        if not value.is_finite() or value!=value.to_integral_value():raise SchemaMismatchError('Nonintegral identifier.')
        value=str(int(value));flags.append('response_identifier_decimal_not_original_text')
    actual=identifier(value)
    if actual!=expected:raise DataQualityError('Response belongs to a different instrument/index.')
    return expected

def dates(row, flags, *, requested=None, required=False):
    """Perform the dates operation.
    
    Args:
        row (Any): Input for the dates operation.
        flags (Any): Input for the dates operation.
        requested (Any): Input for the dates operation.
        required (Any): Input for the dates operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        DataQualityError: When the corresponding validation or operation fails.
        SchemaMismatchError: When the corresponding validation or operation fails."""
    d=pick(row,'dEven','recDate')
    # Integral Decimal dates are safe (YYYYMMDD fits exact integers).
    if isinstance(d,Decimal) and d.is_finite() and d==d.to_integral_value():d=int(d)
    t=row.get('hEven')
    if isinstance(t,Decimal) and t.is_finite() and t==t.to_integral_value():t=int(t)
    day,stamp=parse_source_time({'dEven':d,'hEven':t})
    if day is None and requested is not None:
        day=datetime.strptime(requested,'%Y%m%d').date();flags.append('date_from_requested_endpoint')
    if required and day is None:raise SchemaMismatchError('Historical row has no valid date.')
    if requested and day and day.strftime('%Y%m%d')!=requested:raise DataQualityError('Response date differs from requested day.')
    if day is None:flags.append('source_date_unknown')
    if stamp is None:flags.append('source_timestamp_unknown')
    return day,stamp

def mapping(row):
    """Perform the mapping operation.
    
    Args:
        row (Any): Input for the mapping operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        SchemaMismatchError: When the corresponding validation or operation fails."""
    if not isinstance(row,dict):raise SchemaMismatchError('Expected a row object.')
    return row

def list_rows(data):
    """List rows.
    
    Args:
        data (Any): Input for the list_rows operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        SchemaMismatchError: When the corresponding validation or operation fails."""
    if not isinstance(data,list):raise SchemaMismatchError('Expected a JSON array (including for an empty response).')
    for r in data:mapping(r)
    return data

def _read(packet,spec):
    """Read the requested value.
    
    Args:
        packet (Any): Response packet received from a provider.
        spec (Any): Request or schema specification.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        SchemaMismatchError: When the corresponding validation or operation fails."""
    if spec.root:return decode(packet,spec)
    try:
        return json.loads(packet.content,parse_float=Decimal,object_pairs_hook=_unique_object,
                          parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
    except (ValueError,UnicodeError) as e:raise SchemaMismatchError('Expected valid JSON, not an HTML page.') from e

def _units(row):
    """Process internal units data.
    
    Args:
        row (Any): Input for the _units operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    kind=text(pick(row,'yVal','instrument_type'))
    verified=kind in {'300','303','309'}
    return {'currency':'IRR' if verified else None,'quote_unit':'PRICE' if verified else 'UNKNOWN',
            'quantity_unit':'SHARE' if verified else 'UNKNOWN'}

def watch_row(raw, *, index_code=None, sector=None):
    """Perform the watch row operation.
    
    Args:
        raw (Any): Input for the watch_row operation.
        index_code (Any): Input for the watch_row operation.
        sector (Any): Input for the watch_row operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        DataQualityError: When the corresponding validation or operation fails."""
    raw=mapping(raw)
    nested=raw.get('instrument') or {}
    mapping(nested)
    row={**nested,**raw}
    # A nested instrument is the identity in GetIndexCompany; outer ID can be 0.
    nc=nested.get('insCode'); outer=raw.get('insCode')
    if nc not in (None,'',0,'0'):
        code=identifier(nc)
        if outer not in (None,'',0,'0') and identifier(outer)!=code:
            raise DataQualityError('Nested and outer instrument identifiers conflict.')
    else:code=identifier(pick(row,'insCode',required=True))
    flags=[]
    symbol=text(pick(row,'lVal18AFC','lva'))
    if symbol is not None:symbol=normalize_symbol(symbol)
    if not symbol:flags.append('symbol_not_reported')
    day,stamp=dates(row,flags)
    flow=text(row.get('flow'))
    kind=text(row.get('yVal'))
    market='BASE' if kind=='309' else {'1':'TSE','2':'IFB'}.get(flow)
    fields={
        'open_price':('priceFirst','pf'),'high_price':('priceMax','pmx'),
        'low_price':('priceMin','pmn'),'last_price':('pDrCotVal','pdv'),
        'closing_price':('pClosing','pc'),'previous_reference_price':('priceYesterday','py'),
        'volume':('qTotTran5J','qtj'),'turnover':('qTotCap','qtc'),
        'base_volume':('baseVol','bv'),'shares_outstanding':('zTitad','ztd'),
        'min_allowed_price':('psGelStaMin','pMin'),'max_allowed_price':('psGelStaMax','pMax'),
    }
    values={k:num(pick(row,*names,required=k in ('last_price','closing_price')),k) for k,names in fields.items()}
    if values['low_price'] is not None and values['high_price'] is not None and values['high_price']>0 and values['low_price']>values['high_price']:
        raise DataQualityError('Daily low exceeds high.')
    units=_units(row)
    if units['quote_unit']=='UNKNOWN':flags.append('instrument_unit_not_verified')
    out=dict(ins_code=code,symbol=symbol,name=text(pick(row,'lVal30','lvc')),
        market=market,raw_flow=flow,sector_code=text(pick(row,'cSecVal','csv')),
        instrument_id=text(pick(row,'instrumentID','insID')),instrument_type=kind,
        date=day,source_timestamp=stamp,timestamp_kind='source_hEven_semantics_unverified',
        trade_count=num(pick(row,'zTotTran','ztt'),'trade_count',integer=True),
        eps=num(row.get('eps') if not isinstance(row.get('eps'),dict) else row['eps'].get('estimatedEPS'),'eps',signed=True,blank=True),
        pe=num(row.get('pe'),'pe',signed=True,blank=True),**values,**units,
        source_fields=source_fields(raw),quality_flags=tuple(flags))
    if index_code is not None:
        out.update(index_code=index_code,membership_basis='current_endpoint_not_historical_membership')
        out['quality_flags']+=('historical_membership_not_available',)
    if sector is not None:out['sector_code']=sector
    return out

def book_rows(raw, parent):
    """Perform the book rows operation.
    
    Args:
        raw (Any): Input for the book_rows operation.
        parent (Any): Input for the book_rows operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        DataQualityError: When the corresponding validation or operation fails."""
    books=pick(raw,'blDs','bestLimits')
    if books is None:return []
    list_rows(books)
    out=[];seen=set()
    for b in books:
        depth=num(pick(b,'n','number',required=True),'depth',integer=True)
        if depth is None or not 1<=depth<=5 or depth in seen:raise DataQualityError('Invalid or duplicate best-limit depth.')
        seen.add(depth)
        vals={}
        for name,keys in {'bid_price':('pmd','pMeDem'),'ask_price':('pmo','pMeOf'),
            'bid_volume':('qmd','qTitMeDem'),'ask_volume':('qmo','qTitMeOf'),
            'bid_order_count':('zmd','zOrdMeDem'),'ask_order_count':('zmo','zOrdMeOf')}.items():
            vals[name]=num(pick(b,*keys),name,integer=name.endswith('count'))
        out.append(dict(ins_code=parent['ins_code'],symbol=parent['symbol'],depth=depth,**vals,
            date=None,source_timestamp=None,timestamp_kind='unknown',
            reference_id=text(pick(b,'rid','refID')),currency=parent['currency'],
            quote_unit=parent['quote_unit'],quantity_unit=parent['quantity_unit'],
            source_fields=source_fields(b),quality_flags=('order_book_timestamp_not_reported',)))
    return out

def legacy_rows(packet):
    """Perform the legacy rows operation.
    
    Args:
        packet (Any): Response packet received from a provider.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        SchemaMismatchError: When the corresponding validation or operation fails."""
    try:s=packet.content.decode('utf-8-sig')
    except UnicodeError as e:raise SchemaMismatchError('Legacy response is not UTF-8.') from e
    if s.lstrip().startswith('<'):raise SchemaMismatchError('Legacy endpoint returned HTML.')
    parts=s.split('@')
    if len(parts)!=5:raise SchemaMismatchError('Legacy MarketWatchInit must have five @ sections.')
    prices=[]
    fields=['insCode','instrumentID','lVal18AFC','lVal30','hEven','priceFirst','pClosing','pDrCotVal',
        'zTotTran','qTotTran5J','qTotCap','priceMin','priceMax','priceYesterday','eps','baseVol',
        'visitCount','flow','cSecVal','psGelStaMax','psGelStaMin','zTitad','yVal']
    by_code={}
    for line in parts[2].split(';'):
        if not line.strip():continue
        values=line.split(',')
        if len(values) not in (23,26):raise SchemaMismatchError('Unsupported legacy market row width.')
        row=dict(zip(fields,values[:23]))
        row={k:(None if v=='' else v) for k,v in row.items()}
        row['blDs']=[]
        by_code[row['insCode']]=row;prices.append(row)
    for line in parts[3].split(';'):
        if not line.strip():continue
        cols=line.split(',')
        if len(cols)!=8:raise SchemaMismatchError('Unsupported legacy order-book row width.')
        code,n,zo,zd,pd,po,qd,qo=cols
        if code in by_code:by_code[code]['blDs'].append(dict(n=n,zmo=zo,zmd=zd,pmd=pd,pmo=po,qmd=qd,qmo=qo))
    return prices

def participant(raw, expected=None, requested=None, historical=False):
    """Perform the participant operation.
    
    Args:
        raw (Any): Input for the participant operation.
        expected (Any): Input for the participant operation.
        requested (Any): Input for the participant operation.
        historical (Any): Input for the participant operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        SchemaMismatchError: When the corresponding validation or operation fails."""
    row=mapping(raw);flags=[]
    code=bound_code(row.get('insCode'),expected,flags) if expected else identifier(pick(row,'insCode',required=True))
    day,stamp=dates(row,flags,requested=requested,required=historical)
    vals={};present=False
    for p,tag in [('individual','I'),('institutional','N')]:
        for side in ('buy','sell'):
            for suffix,api in [('count','Count'),('volume','Volume'),('value','Value')]:
                keys=(f'{side}_{api}{tag}',f'{side}_{tag}_{api}') if suffix=='count' else (f'{side}_{tag}_{api}',)
                present=present or any(k in row for k in keys)
                name=f'{p}_{side}_{suffix}'
                vals[name]=num(pick(row,*keys),name,integer=suffix=='count')
    if not present:raise SchemaMismatchError('No recognized client-type fields.')
    vals['buy_ddd_count']=num(row.get('buy_CountDDD'),'buy_CountDDD',integer=True)
    vals['buy_ddd_volume']=num(row.get('buy_DDD_Volume'),'buy_DDD_Volume')
    if any(vals[k] is None for k in vals if k.endswith('_value')):flags.append('client_value_not_reported')
    flags.append('ddd_category_semantics_unverified') if any(vals[k] is not None for k in ('buy_ddd_count','buy_ddd_volume')) else None
    return dict(ins_code=code,symbol=None,market=None,date=day,source_timestamp=stamp,
        currency=None,quote_unit='UNKNOWN',quantity_unit='UNKNOWN',timestamp_kind='source_hEven_semantics_unverified',
        **vals,quality_flags=tuple(flags),source_fields=source_fields(raw))

def index_row(raw,expected=None,flow=None,historical=False,intraday=False,pos=0):
    """Perform the index row operation.
    
    Args:
        raw (Any): Input for the index_row operation.
        expected (Any): Input for the index_row operation.
        flow (Any): Input for the index_row operation.
        historical (Any): Input for the index_row operation.
        intraday (Any): Input for the index_row operation.
        pos (Any): Input for the index_row operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        DataQualityError: When the corresponding validation or operation fails."""
    row=mapping(raw);flags=[]
    code=bound_code(row.get('insCode'),expected,flags) if expected else identifier(pick(row,'insCode',required=True))
    day,stamp=dates(row,flags,required=historical or intraday)
    value_key='xNivInuClMresIbs' if historical else 'xDrNivJIdx004'
    lo_key='xNivInuPbMresIbs' if historical else 'xPbNivJIdx004'
    hi_key='xNivInuPhMresIbs' if historical else 'xPhNivJIdx004'
    value=num(pick(row,value_key,required=True),'index_value')
    low=num(row.get(lo_key),'index_low');high=num(row.get(hi_key),'index_high')
    if low is not None and high is not None and high>0 and low>high:raise DataQualityError('Index low exceeds high.')
    return dict(index_code=code,name=text(row.get('lVal30')),market={'1':'TSE','2':'IFB'}.get(flow),
        unit='point',date=day,source_timestamp=stamp,timestamp_kind='source_hEven_semantics_unverified',
        value=value,low=low,high=high,change=num(row.get('indexChange'),'indexChange',signed=True),
        change_percent=num(row.get('xVarIdxJRfV'),'xVarIdxJRfV',signed=True),source_position=pos if intraday else None,
        **{f'source_c{i}':num(row.get(f'c{i}'),f'c{i}',integer=True) for i in range(1,5)},
        quality_flags=tuple(flags),source_fields=source_fields(raw))

@dataclass
class ParsedMarket:
    """Encapsulate parsed market behavior in the TSE module.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    schema: str
    rows: list[dict]
    books: list[dict] | None = None
    identical_duplicates: int = 0


def _dedup(result,key):
    """Process internal dedup data.
    
    Args:
        result (Any): Input for the _dedup operation.
        key (Any): Input for the _dedup operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        DataQualityError: When the corresponding validation or operation fails."""
    seen={};out=[]
    for row in result.rows:
        k=tuple(row.get(c) for c in key)
        if k in seen:
            # Raw row equality matters: never silently pick one conflicting revision.
            if row!=seen[k]:raise DataQualityError(f'Conflicting duplicate key in {result.schema}: {k}.')
            result.identical_duplicates+=1;continue
        seen[k]=row;out.append(row)
    result.rows=out
    return result


def parse_market_payload(packet,spec):
    """Parse market payload.
    
    Args:
        packet (Any): Response packet received from a provider.
        spec (Any): Request or schema specification.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        SchemaMismatchError: When the corresponding validation or operation fails.
        UnsupportedCapabilityError: When the corresponding validation or operation fails."""
    ep=spec.endpoint_id
    if ep not in ENDPOINTS:raise UnsupportedCapabilityError(f'No market parser for {ep}.')
    data=legacy_rows(packet) if ep=='market.watch.legacy' else _read(packet,spec)
    if ep in ('market.watch','market.watch.legacy','market.related','indices.members','market.map'):
        rows=[];books=[]
        for raw in list_rows(data):
            row=watch_row(raw,index_code=spec.path.rsplit('/',1)[1] if ep=='indices.members' else None,
                sector=spec.path.rsplit('/',1)[1] if ep=='market.related' else None)
            if ep=='market.map':
                row.update(sector_name=text(raw.get('lSecVal')),market_cap=num(raw.get('marketCap'),'marketCap'),
                    price_change_percent=num(raw.get('priceChangePercent'),'priceChangePercent',signed=True),
                    source_percent=num(raw.get('percent'),'percent',signed=True))
            rows.append(row)
            # The JSON market-watch endpoint can return best-limit placeholders
            # even when withBestLimits=false. Only validate them if the caller
            # explicitly requests order-book data. Never let an optional, unused
            # component invalidate an otherwise valid market-watch response.
            parse_books = not (ep == 'market.watch' and 'withBestLimits=false' in spec.path)
            if parse_books:
                books.extend(book_rows(raw,row))
        schema={'market.related':'sector_instruments','indices.members':'index_members','market.map':'market_map'}.get(ep,'market_watch')
        result=_dedup(ParsedMarket(schema,rows,books),('ins_code',))
        # Book duplicates/conflicts are checked independently.
        result.books=_dedup(ParsedMarket('market_order_book',books),('ins_code','depth')).rows
        return result
    if ep.startswith('clients.'):
        expected=spec.path.split('/')[2] if ep!='clients.market' else None
        requested=spec.path.rsplit('/',1)[1] if ep=='clients.day' else None
        if ep in ('clients.latest','clients.day'):
            arr=[] if data is None else data if isinstance(data,list) else [mapping(data)]
            if len(arr)>1:raise SchemaMismatchError('Single-day client endpoint returned multiple rows.')
        else:arr=list_rows(data)
        rows=[participant(r,expected,requested,historical=ep=='clients.history') for r in arr]
        if ep=='clients.history':rows.sort(key=lambda r:r['date'])
        return _dedup(ParsedMarket('client_types',rows),('ins_code','date'))
    if ep in ('indices.list','indices.history','indices.intraday'):
        expected=spec.path.rsplit('/',1)[1] if ep!='indices.list' else None
        flow=spec.path.rsplit('/',1)[1] if ep=='indices.list' else None
        schema={'indices.list':'indices','indices.history':'index_history','indices.intraday':'index_intraday'}[ep]
        rows=[index_row(r,expected,flow,ep=='indices.history',ep=='indices.intraday',pos) for pos,r in enumerate(list_rows(data))]
        if ep=='indices.history':rows.sort(key=lambda r:r['date'])
        if ep=='indices.intraday':rows.sort(key=lambda r:(r['date'],r['source_timestamp'].isoformat() if r['source_timestamp'] else '',r['source_position']))
        result=ParsedMarket(schema,rows)
        return result if ep=='indices.intraday' else _dedup(result,('index_code','date') if ep=='indices.history' else ('index_code',))
    if ep=='market.overview':
        row=mapping(data);flags=[]
        if not any(k in row for k in ('marketValue','indexLastValue','marketState')):raise SchemaMismatchError('No market overview fields.')
        day,stamp=dates({'dEven':row.get('marketActivityDEven'),'hEven':row.get('marketActivityHEven')},flags)
        dd,dt=dates({'dEven':row.get('lastDataDEven'),'hEven':row.get('lastDataHEven')},flags)
        fields={'market_value':'marketValue','market_value_base':'marketValueBase','volume':'marketActivityQTotTran',
                'turnover':'marketActivityQTotCap','index_value':'indexLastValue','index_change':'indexChange',
                'equal_weight_index_value':'indexEqualWeightedLastValue','equal_weight_index_change':'indexEqualWeightedChange'}
        vals={k:num(row.get(v),v,signed=k.endswith('change')) for k,v in fields.items()}
        return ParsedMarket('market_overview',[dict(market={'1':'TSE','2':'IFB'}[spec.path.rsplit('/',1)[1]],
            state=text(row.get('marketStateTitle')),raw_state=text(row.get('marketState')),currency='IRR',index_unit='point',
            date=day,source_timestamp=stamp,data_date=dd,data_timestamp=dt,**vals,
            trade_count=num(row.get('marketActivityZTotTran'),'marketActivityZTotTran',integer=True),
            source_fields=source_fields(row),quality_flags=tuple(flags))])
    if ep=='market.sectors':
        rows=[]
        for r in list_rows(data):
            sector=text(pick(r,'cSecVal',required=True))
            if not sector or not sector.strip():raise SchemaMismatchError('Missing sector code.')
            rows.append(dict(sector_code=sector.strip(),name=text(pick(r,'lSecVal',required=True)),
                **{f'source_c{i}':num(r.get(f'c{i}'),f'c{i}',integer=True) for i in range(1,5)},
                source_fields=source_fields(r),quality_flags=('sector_counters_semantics_unverified',)))
        return _dedup(ParsedMarket('sector_summary',rows),('sector_code',))
    if ep=='market.statistics':
        rows=[]
        for r in list_rows(data):
            flags=[];day,stamp=dates(r,flags)
            rows.append(dict(ins_code=identifier(pick(r,'insCode',required=True)),
                parameter_code=text(pick(r,'dataType',required=True)),
                reported_value=text(pick(r,'dataValue',required=True)),unit=None,date=day,source_timestamp=stamp,
                source_fields=source_fields(r),quality_flags=tuple(flags)+('parameter_semantics_unverified',)))
        return _dedup(ParsedMarket('key_statistics',rows),('ins_code','parameter_code','date'))
    if ep=='indices.impact':
        rows=[];flow=spec.path.split('/')[-2]
        for pos,r in enumerate(list_rows(data)):
            nested=r.get('instrument') or {};mapping(nested)
            code=pick(r,'insCode') or nested.get('insCode')
            # Preserve all source fields; no invented formula or economic mapping.
            # instEffect is exposed as a reported candidate, clearly marked unverified.
            candidate='instEffect' if 'instEffect' in r and not isinstance(r['instEffect'],(dict,list)) else None
            flags=['impact_field_mapping_requires_live_verification']
            day,stamp=dates(r,flags)
            rows.append(dict(ins_code=identifier(code),symbol=text(pick(r,'lVal18AFC') or nested.get('lVal18AFC')),
                name=text(pick(r,'lVal30') or nested.get('lVal30')),market={'1':'TSE','2':'IFB'}[flow],
                impact_points=None,impact_field=candidate,unit=None,date=day,source_timestamp=stamp,
                source_position=pos,source_fields=source_fields(r),quality_flags=tuple(flags)))
        return ParsedMarket('index_impact',rows)
    raise UnsupportedCapabilityError(ep)
