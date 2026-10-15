"""Reviewed public endpoint adapters for data, not analytics.

Unknown fields are retained in source_fields. Empty responses never certify coverage.
New paths are listed with evidence in docs/EXTENSION_SOURCES.md. No code from the
reference libraries is bundled. No network is performed by this module.
"""
from __future__ import annotations
from datetime import datetime, date, UTC
from decimal import Decimal
from html.parser import HTMLParser
import csv
import io
import json
from urllib.parse import quote, urlsplit, parse_qs
from zoneinfo import ZoneInfo

from pydara.tse._core.exceptions import SchemaMismatchError, DataQualityError
from ..transport import RequestSpec, decode
from ..dates import parse_date
from .public import identifier
from .market import num, text, source_fields, bound_code

ENDPOINTS = {
    'extra.futures': ('https://webgw.tse.ir/InstrumentProvider/api/v1/MarketWatch/MarketWatchFuture/fa', 'Items', 60, 'futures'),
    'extra.trades': ('Trade/GetTrade/{code}', 'trade', 5, 'trades'),
    'extra.trades.day': ('Trade/GetTradeHistory/{code}/{day}/true', 'tradeHistory', 3600, 'trades'),
    'extra.book': ('BestLimits/{code}', 'bestLimits', 5, 'order_book'),
    'extra.book.day': ('BestLimits/{code}/{day}', 'bestLimitsHistory', 3600, 'order_book'),
    'extra.states': ('MarketData/GetInstrumentState/{code}/{day}', 'instrumentState', 300, 'instrument_states'),
    'extra.thresholds': ('MarketData/GetStaticThreshold/{code}/{day}', 'staticThreshold', 300, 'thresholds'),
    'extra.shareholders': ('Shareholder/GetInstrumentShareHolderLast/{code}', 'shareHolder', 3600, 'shareholders'),
    'extra.shareholders.history': ('Shareholder/GetShareHolderHistory/{code}/{holder}/{days}', 'shareHolder', 3600, 'shareholders'),
    'extra.shares': ('Instrument/GetInstrumentShareChange/{code}', 'instrumentShareChange', 3600, 'share_capital'),
    'extra.adjustments': ('ClosingPrice/GetPriceAdjustList/{code}', 'priceAdjust', 3600, 'adjustments'),
    'extra.funds': ('Fund/GetFunds/{category}', 'funds', 3600, 'funds'),
    'extra.fund': ('Fund/GetFundInDetail/{registration}', 'fund', 3600, 'funds'),
    'extra.nav': ('Fund/GetFundInDetail/{registration}', 'fund', 3600, 'fund_nav'),
    'extra.disclosures': ('Codal/GetPreparedDataByInsCode/{limit}/{code}', 'preparedData', 300, 'disclosures'),
    'extra.messages': ('Msg/GetMsgByInsCode/{code}', 'msg', 60, 'messages'),
    'extra.options': ('Instrument/GetInstrumentOptionMarketWatch/0', 'instrumentOptMarketWatch', 30, 'options'),
    'extra.boards': ('https://members.tsetmc.com/Loader.aspx?ParTree=111C1913', '__text__', 86400, 'boards'),
    'extra.dividends': ('https://old.tsetmc.com/tsev2/data/DPSData.aspx?s={symbol}', '__text__', 3600, 'dividends'),
    'extra.adjusted': ('https://members.tsetmc.com/tsev2/chart/data/Financial.aspx?i={code}&t=ph&a=1', '__text__', 3600, 'adjusted_history'),
}

# Substitution values are validated by the operation planner, never caller URLs.
def endpoint(name, **params):
    """Perform the endpoint operation.
    
    Args:
        name (Any): Input for the endpoint operation.
        params: Additional arguments for this operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    path, root, age, _ = ENDPOINTS[name]
    return RequestSpec(name, path.format(**params), root, float(age))


def pick(row, *keys):
    """Select the requested value.
    
    Args:
        row (Any): Input for the pick operation.
        keys: Additional arguments for this operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return None


def optional_id(value):
    """Perform the optional id operation.
    
    Args:
        value (Any): Input for the optional_id operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    if value is None or value == '':
        return None
    if type(value) in (str, int) and value in (0, '0'):
        return None
    return identifier(value)


def date_value(value, *, calendar='gregorian'):
    """Perform the date value operation.
    
    Args:
        value (Any): Input for the date_value operation.
        calendar (Any): Calendar used to parse or format dates.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        SchemaMismatchError: When the corresponding validation or operation fails."""
    if value is None or value in ('', 0, '0'):
        return None
    if isinstance(value, bool):
        raise SchemaMismatchError('Boolean is not a date.')
    s=str(value).strip().replace('/', '-')
    if len(s)==8 and s.isdigit():s=s[:4]+'-'+s[4:6]+'-'+s[6:]
    try:return parse_date(s, calendar=calendar, name='source date')
    except Exception as exc:raise SchemaMismatchError(f'Unrecognized source date {s!r}.') from exc


def iso_date(value):
    """Record date, not a publication timestamp. No timezone inference here."""
    if value is None or value=='':return None
    try:return datetime.fromisoformat(str(value)).date()
    except ValueError:return date_value(value)


def source_time(day, value):
    """Perform the source time operation.
    
    Args:
        day (Any): Input for the source_time operation.
        value (Any): Input for the source_time operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        SchemaMismatchError: When the corresponding validation or operation fails."""
    if day is None or value is None or value in ('',0,'0'):return None
    s=str(value).zfill(6)
    if not s.isascii() or not s.isdigit() or len(s)!=6:
        raise SchemaMismatchError('Invalid source hEven.')
    try:
        return datetime.combine(day,datetime.strptime(s,'%H%M%S').time(),ZoneInfo('Asia/Tehran')).astimezone(UTC)
    except ValueError as exc:raise SchemaMismatchError('Invalid source hEven.') from exc


class _Tables(HTMLParser):
    """Encapsulate _ tables behavior in the TSE module.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    def __init__(self):
        """Initialize the instance and its configured state."""
        super().__init__(convert_charrefs=True);self.rows=[];self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        """Perform the handle starttag operation.
        
        Args:
            tag (Any): Input for the handle_starttag operation.
            attrs (Any): Input for the handle_starttag operation."""
        if tag=='tr':self.row=[]
        if tag in ('td','th') and self.row is not None:self.cell=[]
    def handle_data(self,data):
        """Perform the handle data operation.
        
        Args:
            data (Any): Input for the handle_data operation."""
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        """Perform the handle endtag operation.
        
        Args:
            tag (Any): Input for the handle_endtag operation."""
        if tag in ('td','th') and self.cell is not None:
            self.row.append(''.join(self.cell).strip());self.cell=None
        if tag=='tr' and self.row is not None:
            self.rows.append(self.row);self.row=None


def _text_rows(packet,spec):
    """Extract text from rows.
    
    Args:
        packet (Any): Response packet received from a provider.
        spec (Any): Request or schema specification.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        SchemaMismatchError: When the corresponding validation or operation fails."""
    try:content=packet.content.decode('utf-8-sig').strip()
    except UnicodeError as exc:raise SchemaMismatchError('Source text is not UTF-8.') from exc
    if spec.endpoint_id=='extra.boards':
        parser=_Tables();parser.feed(content)
        rows=[{'board_code':x[0], 'name':x[1]} for x in parser.rows if len(x)==2 and x[0].isascii() and x[0].isdigit()]
        if not rows:raise SchemaMismatchError('No recognizable board-code table was returned.')
        return rows
    if '<html' in content.lower() or '<!doctype' in content.lower():
        raise SchemaMismatchError('The data route returned an HTML page, not data.')
    if not content:return []
    out=[]
    for row in csv.reader(io.StringIO(content.replace(';','\n')),delimiter='@' if spec.endpoint_id=='extra.dividends' else ','):
        if not row:continue
        if len(row)!=7:raise SchemaMismatchError('Expected seven chart/dividend source fields.')
        if spec.endpoint_id=='extra.dividends':
            keys=('publish','meeting','year','profit','distributable','accumulated','dps')
        else:keys=('day','high','low','open','last','volume','closing')
        out.append(dict(zip(keys,row)))
    return out


def parse_payload(packet, spec):
    """Return (rows, schema); validate economically essential shape before caching."""
    ep=spec.endpoint_id;schema=ENDPOINTS[ep][3]
    parts=urlsplit(spec.path).path.split('/')
    day=None;code=None;registration=None
    if ep in ('extra.trades.day','extra.book.day','extra.states','extra.thresholds'):
        code=parts[-3] if ep=='extra.trades.day' else parts[-2]
        day=date_value(parts[-2] if ep=='extra.trades.day' else parts[-1])
    elif ep=='extra.shareholders.history':code=parts[-3]
    elif ep in ('extra.trades','extra.book','extra.shareholders','extra.shares','extra.adjustments','extra.disclosures','extra.messages'):
        code=parts[-1]
    elif ep in ('extra.fund','extra.nav'):registration=parts[-1]
    elif ep=='extra.adjusted':code=parse_qs(urlsplit(spec.path).query)['i'][0]
    if ep=='extra.futures':
        from dataclasses import replace
        try:raw=decode(packet,spec)
        except SchemaMismatchError:
            raw=decode(packet,replace(spec,root='items'))
    else:raw=_text_rows(packet,spec) if spec.root=='__text__' else decode(packet,spec)
    if ep=='extra.nav':
        if not isinstance(raw,dict) or not isinstance(raw.get('stats'),list):
            raise SchemaMismatchError('Fund detail must include a stats list.')
        raw=raw['stats']
    elif ep=='extra.fund':
        if not isinstance(raw,dict):raise SchemaMismatchError('fund must be an object.')
        raw=[{k:v for k,v in raw.items() if k!='stats'}]
    if not isinstance(raw,list):raise SchemaMismatchError(f'{ep} must return a list, including when empty.')
    out=[]
    for pos,row in enumerate(raw):
        if not isinstance(row,dict):raise SchemaMismatchError(f'{ep} has a non-object row.')
        required = {
            'extra.thresholds': ('psGelStaMin','psGelStaMax'),
            'extra.shareholders': ('numberOfShares','perOfShares'),
            'extra.shareholders.history': ('numberOfShares',),
            'extra.shares': ('numberOfShareOld','numberOfShareNew'),
            'extra.adjustments': ('pClosingNotAdjusted','pClosing'),
            'extra.nav': ('recordDate',),
            'extra.disclosures': ('tracingNo','title'),
            'extra.messages': ('tseMsgIdn','tseTitle','tseDesc'),
        }.get(ep, ())
        if any(field not in row for field in required):
            raise SchemaMismatchError(f'{ep} is missing mandatory fields: {required}.')
        flags=[];r={'source_position':pos,'source_fields':source_fields(row)}
        if code:r['ins_code']=bound_code(row.get('insCode'),code,flags)
        d=date_value(pick(row,'dEven','deven')) or day
        r.update(date=d,source_timestamp=source_time(d,row.get('hEven')))
        if ep.startswith('extra.trades'):
            if 'pTran' not in row or 'qTitTran' not in row:
                raise SchemaMismatchError('Trade requires pTran and qTitTran.')
            r.update(trade_id=text(pick(row,'nTran','tradeId','id')),sequence=text(pick(row,'nTran','sequence')),
                     price=num(row.get('pTran'),'pTran'),quantity=num(row.get('qTitTran'),'qTitTran'),cancellation_state='unknown')
            if r['price'] is None or r['quantity'] is None:raise DataQualityError('A trade requires a non-null price and quantity.')
            flags.append('cancellation_semantics_not_verified')
        elif ep.startswith('extra.book'):
            depth=num(row.get('number'),'number',integer=True)
            if depth is None or not 1<=depth<=5:raise DataQualityError('Best-limit depth must be 1..5.')
            r.update(depth=depth,reference_id=text(pick(row,'refID','refId')))
            for dest,src in [('bid_price','pMeDem'),('ask_price','pMeOf'),('bid_volume','qTitMeDem'),('ask_volume','qTitMeOf'),('bid_order_count','zOrdMeDem'),('ask_order_count','zOrdMeOf')]:
                r[dest]=num(row.get(src),src,integer=dest.endswith('count'))
            flags.append('reported_levels_not_full_order_book')
            if ep.endswith('.day'):flags.append('updates_not_reconstructed_snapshots')
        elif ep=='extra.states':
            if 'cEtaval' not in row:raise SchemaMismatchError('Missing state code.')
            r.update(raw_state=text(row['cEtaval']),state=text(row.get('cEtavalTitle')),event_id=text(row.get('idn')))
        elif ep=='extra.thresholds':
            r.update(min_price=num(row.get('psGelStaMin'),'psGelStaMin'),max_price=num(row.get('psGelStaMax'),'psGelStaMax'))
        elif ep.startswith('extra.shareholders'):
            r.update(shareholder_id=optional_id(row.get('shareHolderID')),holding_ref=optional_id(row.get('shareHolderShareID')),
                shareholder_name=text(row.get('shareHolderName')),company_cisin=text(row.get('cIsin')),
                quantity=num(row.get('numberOfShares'),'numberOfShares'),ownership_percent=num(row.get('perOfShares'),'perOfShares'),
                change_quantity=num(row.get('changeAmount'),'changeAmount',signed=True))
            if r['ownership_percent'] is not None and r['ownership_percent']>100:raise DataQualityError('Ownership percent exceeds 100.')
        elif ep=='extra.shares':
            if d is None:raise SchemaMismatchError('Share change requires a date.')
            r.update(event_id=text(pick(row,'id','idn')),old_shares=num(row.get('numberOfShareOld'),'numberOfShareOld'),new_shares=num(row.get('numberOfShareNew'),'numberOfShareNew'))
            flags.append('share_count_update_not_legal_event_classification')
        elif ep=='extra.adjustments':
            if d is None:raise SchemaMismatchError('Adjustment requires a date.')
            before=num(row.get('pClosingNotAdjusted'),'pClosingNotAdjusted');after=num(row.get('pClosing'),'pClosing')
            if before == 0:flags.append('zero_before_price_factor_unavailable')
            r.update(price_before=before,price_after=after,factor=after/before if before and after is not None else None,
                     method='reported_price_pair',reason=None)
            flags.append('adjustment_reason_and_completeness_not_verified')
        elif ep in ('extra.funds','extra.fund'):
            reg=pick(row,'regNo','registrationNo')
            if isinstance(reg,Decimal) and reg==reg.to_integral_value():reg=str(int(reg))
            reg=optional_id(reg) or registration
            if reg is None:raise SchemaMismatchError('Fund registration number is missing.')
            if registration and reg!=registration:raise DataQualityError('Different fund registration number.')
            r.update(registration_no=reg,name=text(pick(row,'name','fundName')),ins_code=optional_id(row.get('insCode')),
                     category=text(pick(row,'type','fundType')),date=iso_date(row.get('recordDate')),inception_date=iso_date(row.get('initiationDate')))
        elif ep=='extra.nav':
            r.update(registration_no=registration,date=iso_date(row.get('recordDate')),currency=None)
            for dest,src in [('subscription_nav','navSub'),('redemption_nav','navRed'),('statistical_nav','navStat'),('net_assets','netAsset')]:r[dest]=num(row.get(src),src)
            flags.append('nav_unit_not_verified')
        elif ep=='extra.dividends':
            r.update(date=date_value(row['publish'],calendar='jalali'),meeting_date=date_value(row['meeting'],calendar='jalali'),fiscal_year_end=date_value(row['year'],calendar='jalali'),currency=None)
            for dest,src in [('cash_dividend_per_share','dps'),('profit_after_tax','profit'),('distributable_profit','distributable'),('accumulated_profit','accumulated')]:r[dest]=num(row[src] or None,src,signed=True)
            flags.append('payment_and_ex_date_not_provided')
        elif ep=='extra.disclosures':
            r.update(tracking_no=text(row.get('tracingNo')),title=text(row.get('title')),
                     published_at_raw=text(row.get('publishDateTime_Gregorian')),sent_at_raw=text(row.get('sentDateTime_Gregorian')),
                     date=date_value(row.get('publishDateTime_DEven')))
            for dest,src in [('has_html','hasHtmlReport'),('has_excel','hasExcelReport'),('has_pdf','hasPDFReport'),('has_xml','hasXMLReport')]:r[dest]=num(row.get(src),src,integer=True)
            flags.append('publication_timezone_unknown_raw_text_preserved')
        elif ep=='extra.messages':
            r.update(message_id=text(row.get('tseMsgIdn')),title=text(row.get('tseTitle')),text=text(row.get('tseDesc')),raw_flow=text(row.get('flow')))
        elif ep=='extra.boards':r.update(row)
        elif ep=='extra.options':
            # Source rows pair put/call contracts. Emit one row per actual contract.
            if 'insCode_P' not in row and 'insCode_C' not in row:raise SchemaMismatchError('Option pair has no identifiers.')
            for side,kind in [('P','put'),('C','call')]:
                ins=optional_id(row.get('insCode_'+side))
                if ins is None:continue
                opt=dict(r,ins_code=ins,symbol=text(row.get('lVal18AFC_'+side)),name=text(row.get('lVal30_'+side)),
                    underlying_ins_code=optional_id(row.get('uaInsCode')),underlying_name=text(row.get('lval30_UA')),option_type=kind,
                    expiry_date=date_value(row.get('endDate')),strike_price=num(row.get('strikePrice'),'strikePrice'),contract_size=num(row.get('contractSize'),'contractSize'),
                    closing_price=num(row.get('pClosing_'+side),'pClosing'),last_price=num(row.get('pDrCotVal_'+side),'pDrCotVal'),
                    open_interest=None,quantity_unit='CONTRACT',quote_unit='UNKNOWN',currency=None,
                    quality_flags=('source_option_pair_expanded','option_price_unit_not_verified'))
                out.append(opt)
            continue
        elif ep=='extra.futures':
            iid=text(pick(row,'instrumentId','InstrumentId'))
            if not iid:raise SchemaMismatchError('Futures instrumentId is missing.')
            r.update(instrument_id=iid,symbol=text(pick(row,'instrumentName','InstrumentName')),name=text(pick(row,'companyNamePersian','CompanyNamePersian')),
                     currency=None,quote_unit='UNKNOWN',quantity_unit='CONTRACT')
            for dest,src in [('last_price','lastPrice'),('closing_price','closingPrice'),('volume','tradeVolume'),('turnover','tradeValue'),('trade_count','tradeCount')]:r[dest]=num(row.get(src),src,integer=dest=='trade_count')
            flags.append('secondary_exchange_gateway_not_tsetmc')
        elif ep=='extra.adjusted':
            r.update(date=date_value(row['day']),adjustment='source',adjustment_method='tsetmc_chart_a1',series='listing')
            for dest,src in [('high_price','high'),('low_price','low'),('open_price','open'),('last_price','last'),('volume','volume'),('closing_price','closing')]:r[dest]=num(row[src],src)
            if r['high_price'] is not None and r['low_price'] is not None and r['high_price'] < r['low_price']:raise DataQualityError('Chart high is below low.')
            flags+=['source_adjustment_method_not_total_return_guarantee','not_point_in_time_adjusted_series']
        r['quality_flags']=tuple(dict.fromkeys(flags));out.append(r)
    if schema=='order_book' and ep=='extra.book':
        depths=[r['depth'] for r in out]
        if len(depths)!=len(set(depths)):raise DataQualityError('Duplicate current best-limit depth.')
    if schema in ('adjustments','adjusted_history'):
        seen={};unique=[]
        for r in out:
            k=(r.get('ins_code'),r.get('date'));compare={a:b for a,b in r.items() if a not in ('source_position','source_fields')}
            if k in seen:
                if seen[k]!=compare:raise DataQualityError(f'Conflicting duplicate date in {schema}.')
            else:seen[k]=compare;unique.append(r)
        out=unique
    return out,schema
