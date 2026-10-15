"""Explicit local DataFrame tools: no network, database, fill, or hidden aggregation.

These helpers verify a structural contract, not the economic truth of the source.
All transformations return caller-owned frames; the input is never mutated.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import math
import numbers

import numpy as np
import pandas as pd
from pandas.api.types import is_datetime64_any_dtype

from pydara.tse._core.exceptions import InvalidArgumentError, DataQualityError
from .dates import Calendar, parse_date
from .frames import instrument_frame, quote_frame
from .history import empty_history_frame, DISPLAY_COLUMNS
from .providers.public import normalize_symbol

from .market_schemas import SCHEMAS as _MARKET_SCHEMAS, empty_market_frame

_SCHEMAS = ('daily_bars', 'quote', 'quotes.batch', 'instruments', *_MARKET_SCHEMAS)
_DIGITS = str.maketrans('\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669', '01234567890123456789')
_PRICE_COLUMNS = ('open_price', 'high_price', 'low_price', 'last_price',
                  'closing_price', 'previous_reference_price')
_IDENTIFIERS = {'ins_code', 'instrument_id', 'company_cisin', 'raw_ins_code',
                'source_record_id', 'observation_id', 'row_id', 'row_version_id'}
_REQUIRED = {
    'daily_bars': tuple(DISPLAY_COLUMNS),
    'quote': ('ins_code', 'symbol', 'date', 'last_price', 'closing_price'),
    'quotes.batch': ('request_index', 'input_symbol', 'status', 'ins_code', 'last_price',
                     'error_code', 'error_message'),
    'instruments': ('ins_code', 'symbol', 'raw_symbol', 'name'),
}
_REQUIRED.update({name: spec.display for name, spec in _MARKET_SCHEMAS.items()})
_IDENTIFIERS.update({'index_code', 'reference_id', 'parameter_code'})
_SIGNED_FIELDS = {'change','change_percent','index_change','equal_weight_index_change','price_change_percent','source_percent','eps','pe','impact_points','change_quantity','profit_after_tax','distributable_profit','accumulated_profit','cash_dividend_per_share'}

_DESCRIPTIONS = {
    'ins_code': 'Exact instrument identifier stored as text, not a floating-point number.',
    'symbol': 'Normalized symbol; different tickers are never fuzzy-merged.',
    'date': 'Gregorian trading date, without time or timezone.',
    'last_price': 'Last reported trade price, not the official daily closing price.',
    'closing_price': 'Closing price reported by the source; not automatically adjusted.',
    'previous_reference_price': 'Previous reference reported by the source; not a guaranteed prior-row close.',
    'volume': 'Reported quantity; consult quantity_unit.',
    'turnover': 'Reported turnover; consult currency.',
    'trade_count': 'Number of transactions; nullable integer.',
    'fetched_at': 'When this response was fetched, as an aware UTC timestamp.',
    'available_at': 'Local availability evidence; not an invented historical publication time.',
    'quality_flags': 'Tuple of recorded caveats; these are not errors by themselves.',
}

_DESCRIPTIONS.update({'ins_code': 'شناسه دقیق ابزار؛ رشته است و نباید به float تبدیل شود.', 'symbol': 'نماد عادی\u200cشده؛ نمادهای مشابه به هم تبدیل نمی\u200cشوند.', 'date': 'تاریخ روز معاملاتی میلادی، بدون زمان و منطقه زمانی.', 'jdate': 'نمایش تاریخ شمسی؛ فقط در صورت درخواست اضافه می\u200cشود.', 'open_price': 'قیمت نخستین معامله گزارش\u200cشده.', 'high_price': 'بیشترین قیمت روز گزارش\u200cشده.', 'low_price': 'کمترین قیمت روز گزارش\u200cشده.', 'last_price': 'قیمت آخرین معامله؛ جدا از قیمت پایانی.', 'closing_price': 'قیمت پایانی منبع؛ نام این ستون به\u200cتنهایی به معنی تعدیل نیست.', 'previous_reference_price': 'قیمت مرجع روز قبل در پاسخ منبع؛ الزاماً برابر پایانی سطر قبل نیست.', 'volume': 'مقدار معاملات؛ واحد را از quantity_unit بخوانید.', 'turnover': 'ارزش معاملات؛ ارز را از currency بخوانید.', 'trade_count': 'تعداد معاملات؛ عدد صحیح nullable.', 'fetched_at': 'زمان دریافت پاسخ توسط کتابخانه؛ timestamp دارای UTC.', 'first_observed_at': 'نخستین مشاهده ثبت\u200cشده نسخه؛ نه زمان انتشار عمومیِ استنباط\u200cشده.', 'available_at': 'زمان دسترسی مبتنی بر شواهد ثبت\u200cشده؛ نه تاریخ رویداد فرضی.', 'source_timestamp': 'زمان اعلام\u200cشده منبع؛ نوع معنایی آن را timestamp_kind توضیح می\u200cدهد.', 'identity_fetched_at': 'زمان دریافت اطلاعات هویتی که برای تفسیر این ردیف استفاده شد.', 'committed_at': 'زمان ثبت موفق در مخزن محلی.', 'quality_flags': 'هشدارهای کیفیت و محدودیت\u200cها؛ خود این فهرست لزوماً خطا نیست.', 'raw_symbol': 'نام نماد در پاسخ اصلی پیش از عادی\u200cسازی.', 'name': 'نام ابزار/شرکت مطابق خروجی منبع.', 'instrument_id': 'شناسه ابزار؛ با company_cisin یکی فرض نشود.', 'company_cisin': 'شناسه CIsin؛ جدا از شناسه داخلی ابزار.', 'market': 'بازار معنایی تأییدشده؛ مقادیر نامعلوم حفظ می\u200cشوند.', 'raw_flow': 'کد بازار به همان صورت منبع.', 'instrument_type': 'کد نوع ابزار در منبع؛ نه طبقه\u200cبندی حدسی.', 'currency': 'ارز تأییدشده؛ مقدار نامعلوم به ریال فرضی تبدیل نمی\u200cشود.', 'quote_unit': 'واحد قیمت تأییدشده یا UNKNOWN.', 'quantity_unit': 'واحد مقدار: سهم، قرارداد یا واحد تأییدشده دیگر.', 'is_active': 'اعتبار هویتی ابزار؛ با مجازبودن معامله یکی نیست.', 'state': 'وضعیت گزارش\u200cشده نماد.', 'raw_state': 'کد وضعیت خام منبع.', 'timestamp_kind': 'معنای timestamp؛ در نبود مدرک unknown/تأییدنشده است.', 'source': 'نام Provider دریافت\u200cکننده؛ دلیل استقلال منابع نیست.', 'endpoint_id': 'شناسه سرویس استفاده\u200cشده.', 'row_id': 'شناسه ردیف منطقی؛ نه شماره معامله ساختگی.', 'row_version_id': 'شناسه نسخه اقتصادی روزانه.', 'observation_id': 'شناسه مشاهده/درخواست برای ردیابی.', 'payload_hash': 'اثر انگشت پاسخ خام؛ امضای اصالت ناشر نیست.', 'availability_basis': 'مبنای تعیین زمان در دسترس بودن.', 'scope_id': 'فضای داده عمومی یا نمونه؛ نمونه با داده واقعی مخلوط نمی\u200cشود.', 'storage_receipt_id': 'شناسه رسید ذخیره؛ queued به معنی persisted نیست.', 'from_cache': 'آیا پاسخ از حافظه یا مخزن محلی آمده است.', 'is_stale': 'آیا پاسخ با اجازه صریح خارج از مهلت تازگی استفاده شده است.', 'adjustment': 'حالت تعدیل؛ در این نسخه تاریخچه خام none است.', 'series': 'دامنه سری؛ در این نسخه فقط یک listing.', 'raw_reference': 'ارجاع/اثر انگشت پاسخ خام.', 'raw_ins_code': 'شناسه خام پاسخ قبل از تفسیر کنترل\u200cشده.', 'source_record_id': 'شناسه رکورد اعلام\u200cشده منبع؛ با کد نماد متفاوت است.', 'request_index': 'موقعیت ورودی در درخواست گروهی؛ تکرار ورودی حفظ می\u200cشود.', 'input_symbol': 'نماد یا شناسه صریح ورودی همان عضو درخواست گروهی.', 'status': 'وضعیت همان عضو درخواست گروهی.', 'error_code': 'نوع خطای عضو ناموفق؛ نبود آن به معنی تضمین صحت اقتصادی نیست.', 'error_message': 'شرح خطای عضو ناموفق.'})


def _schema_frame(schema: str, numeric: str = 'analysis') -> pd.DataFrame:
    """Process internal schema frame data.
    
    Args:
        schema (str): Input for the _schema_frame operation.
        numeric (str): Numeric conversion or output representation setting.
    
    Returns:
        pd.DataFrame: Result of the _schema_frame operation; refer to its public API contract for schema details.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails."""
    if not isinstance(schema, str) or schema not in _SCHEMAS:
        raise InvalidArgumentError(f"Unknown schema {schema!r}; choose one of {_SCHEMAS}.")
    if not isinstance(numeric, str) or numeric not in ('analysis', 'exact'):
        raise InvalidArgumentError("numeric must be 'analysis' or 'exact'.")
    if schema in _MARKET_SCHEMAS:
        return empty_market_frame(schema, numeric=numeric, include_jdate=True)
    if schema == 'daily_bars':
        frame = empty_history_frame(numeric=numeric, include_jdate=True)
    elif schema == 'instruments':
        frame = instrument_frame([])
    else:
        frame = quote_frame([], numeric=numeric, batch_rows=[] if schema == 'quotes.batch' else None)
    return frame


def schema_info(schema: str = 'daily_bars', *, numeric: str = 'analysis') -> pd.DataFrame:
    """Return column names, expected dtypes and meanings for an implemented schema.

    Parameters
    ----------
    schema : str, default 'daily_bars'
        One of daily_bars, quote, quotes.batch, instruments.
    numeric : {'analysis', 'exact'}, default 'analysis'
        Floating nullable columns or Decimal object columns for prices/quantities.

    Returns
    -------
    pandas.DataFrame
        column, dtype, required, description. It is a description, not market data.
    """
    template = _schema_frame(schema, numeric)
    rows = [{'column': c, 'dtype': str(template[c].dtype), 'required': c in _REQUIRED[schema],
             'description': _DESCRIPTIONS.get(c, 'See the detailed data dictionary in the package documentation.')}
            for c in template]
    out = pd.DataFrame(rows).astype({'column':'string', 'dtype':'string',
                                    'required':'boolean', 'description':'string'})
    out.attrs['pydara'] = {'schema_description_for':schema, 'numeric':numeric}
    return out


def _frame(df):
    """Process internal frame data.
    
    Args:
        df (Any): Input for the _frame operation.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails."""
    if not isinstance(df, pd.DataFrame):
        raise InvalidArgumentError('df must be a pandas.DataFrame.')
    if isinstance(df.columns, pd.MultiIndex) or not df.columns.is_unique:
        raise InvalidArgumentError('Use unique flat column names, not duplicate labels or MultiIndex columns.')
    if not all(isinstance(c, str) and c for c in df.columns):
        raise InvalidArgumentError('Column names must be nonempty strings.')


def _missing(value) -> bool:
    """Process internal missing data.
    
    Args:
        value (Any): Input for the _missing operation.
    
    Returns:
        bool: Result of the _missing operation; refer to its public API contract for schema details."""
    if value is None or value is pd.NA or value is pd.NaT:
        return True
    return isinstance(value, (float, np.floating)) and math.isnan(value)


def _decimal(value, column):
    """Process internal decimal data.
    
    Args:
        value (Any): Input for the _decimal operation.
        column (Any): Input for the _decimal operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails."""
    if _missing(value):
        return None
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (str, Decimal, numbers.Real)):
        raise InvalidArgumentError(f'{column}: expected a number or a numeric string.')
    try:
        text = str(value).translate(_DIGITS).strip()
        result = Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise InvalidArgumentError(f'{column}: invalid numeric text; separators are not guessed.') from exc
    if not result.is_finite():
        raise InvalidArgumentError(f'{column}: nonfinite values are not supported.')
    return result


def frame_metadata(df: pd.DataFrame) -> dict:
    """Return a deep copy of df.attrs['pydara']; absent evidence stays unknown."""
    _frame(df)
    raw = df.attrs.get('pydara')
    if raw is not None and not isinstance(raw, dict):
        raise InvalidArgumentError("df.attrs['pydara'] must be a dict.")
    return deepcopy(raw) if raw is not None else {'coverage_status':'unknown', 'provenance_status':'unknown'}


def select_columns(df: pd.DataFrame, columns: Sequence[str] | str = 'compact') -> pd.DataFrame:
    """Select explicit columns, or the documented 'compact'/'full' presentation.

    Compact output is a view for users, not a provenance-complete archive. Full
    metadata is copied, and any removed evidence columns are listed in it.
    Unknown/duplicate column names raise InvalidArgumentError instead of being ignored.
    """
    _frame(df)
    if isinstance(columns, str):
        if columns == 'full':
            names = list(df.columns)
        elif columns == 'compact':
            schema_id = frame_metadata(df).get('base_schema', frame_metadata(df).get('schema_id'))
            prefix = list(_MARKET_SCHEMAS[schema_id].display) if schema_id in _MARKET_SCHEMAS else []
            ordered = [*prefix, 'request_index', 'input_symbol', 'status', *DISPLAY_COLUMNS,
                       'jdate', 'name', 'market', 'is_active', 'from_cache', 'is_stale',
                       'error_code', 'error_message']
            names = list(dict.fromkeys(c for c in ordered if c in df))
            if not names:
                raise InvalidArgumentError('No known compact columns; provide explicit names.')
        else:
            raise InvalidArgumentError("Use 'compact', 'full', or a sequence of column names.")
    elif isinstance(columns, (Sequence, pd.Index, np.ndarray)):
        names = list(columns)
    else:
        raise InvalidArgumentError('columns must be a sequence of names or a documented preset.')
    if not names or any(not isinstance(c, str) for c in names) or len(set(names)) != len(names):
        raise InvalidArgumentError('Select one or more unique string column names.')
    absent = [c for c in names if c not in df]
    if absent:
        raise InvalidArgumentError(f'Unknown columns: {absent}.')
    out = df.loc[:, names].copy(deep=True)
    out.attrs = deepcopy(df.attrs)
    meta = frame_metadata(out)
    removed = [c for c in ('row_id', 'row_version_id', 'observation_id', 'fetched_at',
                          'first_observed_at', 'available_at', 'quality_flags') if c in df and c not in out]
    meta.update(selected_columns=names, removed_evidence_columns=removed)
    if removed:
        meta['presentation_only'] = True
    out.attrs['pydara'] = meta
    return out


def validate_data(df: pd.DataFrame, *, schema: str | None = None,
                  raise_on_error: bool = False, check_order: bool = True) -> pd.DataFrame:
    """Report schema/value issues without changing data or contacting TSETMC.

    The report columns are severity, rule, column, count, row_positions, message.
    row_positions are zero-based positions (not possibly duplicated index labels).
    At most ten example positions are kept per rule. Warnings do not certify or
    invalidate financial truth. This function is NOT a point-in-time/leakage audit.
    """
    _frame(df)
    if not isinstance(raise_on_error, bool) or not isinstance(check_order, bool):
        raise InvalidArgumentError('raise_on_error and check_order must be bool.')
    if schema is None:
        meta=frame_metadata(df)
        schema=meta.get('base_schema',meta.get('schema_id')) or 'daily_bars'
        if schema=='daily_bars.batch':schema='daily_bars'
    template = _schema_frame(schema)
    issues = []
    def add(severity, rule, column, positions, message):
        """Perform the add operation.
        
        Args:
            severity (Any): Input for the add operation.
            rule (Any): Input for the add operation.
            column (Any): Input for the add operation.
            positions (Any): Input for the add operation.
            message (Any): Input for the add operation."""
        positions = list(positions)
        issues.append(dict(severity=severity, rule=rule, column=column, count=len(positions),
                           row_positions=tuple(positions[:10]), message=message))
    for c in _REQUIRED[schema]:
        if c not in df:
            add('error', 'missing_column', c, [], 'A required schema column is absent.')
    failed = np.zeros(len(df), dtype=bool)
    if schema == 'quotes.batch' and 'status' in df:
        failed = df['status'].eq('error').fillna(False).to_numpy(dtype=bool)
    for c in ('ins_code', 'index_code', 'date'):
        if c not in df or c == 'date' and schema not in ('daily_bars','index_history','index_intraday'):
            continue
        if schema=='funds' and c=='ins_code':continue
        invalid = [i for i, v in enumerate(df[c]) if not failed[i] and _missing(v)]
        if invalid:
            add('error', 'missing_identity_or_date', c, invalid, 'Missing key on a successful data row.')
    for code_col in ('ins_code', 'index_code'):
        if code_col not in df: continue
        bad = [i for i, v in enumerate(df[code_col]) if not _missing(v) and (
               not isinstance(v, str) or not v.isascii() or not v.isdigit() or int(v) <= 0)]
        if bad:
            add('error', 'identifier_not_exact_text', code_col, bad, 'Keep identifiers as exact positive digit strings.')
    for c in df:
        if c not in template:
            continue
        if str(template[c].dtype) in ('Float64', 'Int64'):
            bad = []; negative = []; noninteger = []
            for i, v in enumerate(df[c]):
                if _missing(v):
                    continue
                try:
                    n = _decimal(v, c)
                    if isinstance(v, str):
                        bad.append(i)
                    if n < 0 and not (schema in _MARKET_SCHEMAS and c in _SIGNED_FIELDS):
                        negative.append(i)
                    if str(template[c].dtype) == 'Int64' and n != n.to_integral_value():
                        noninteger.append(i)
                except InvalidArgumentError:
                    bad.append(i)
            if bad: add('error', 'invalid_numeric_value', c, bad, 'Use finite numeric values, not text/booleans.')
            if negative: add('error', 'negative_value', c, negative, 'This schema field is nonnegative.')
            if noninteger: add('error', 'nonintegral_count', c, noninteger, 'Count/position fields must be integral.')
        if c == 'date':
            if not is_datetime64_any_dtype(df[c].dtype) or isinstance(df[c].dtype, pd.DatetimeTZDtype):
                add('error', 'date_dtype', c, [], 'Use a timezone-naive Pandas datetime column for daily dates.')
            else:
                nonmidnight = df[c].notna() & df[c].ne(df[c].dt.normalize())
                if nonmidnight.any(): add('error','date_has_time',c,np.flatnonzero(nonmidnight), 'Daily dates must not contain a time.')
        elif isinstance(template[c].dtype, pd.DatetimeTZDtype):
            if not isinstance(df[c].dtype, pd.DatetimeTZDtype) or str(df[c].dtype.tz) != 'UTC':
                add('error','timestamp_dtype',c,[], 'Real timestamps must be timezone-aware UTC.')
    keys = ['ins_code', 'date'] if schema == 'daily_bars' else ['request_index'] if schema == 'quotes.batch' else ['ins_code']
    if schema == 'daily_bars' and 'request_index' in df:
        keys = ['request_index', *keys]
    if schema in _MARKET_SCHEMAS:
        keys = list(_MARKET_SCHEMAS[schema].key)
        if 'request_index' in df and keys: keys = ['request_index', *keys]
    if keys and all(k in df for k in keys):
        duplicates = df.duplicated(keys, keep=False)
        if duplicates.any(): add('error', 'duplicate_key', ','.join(keys), np.flatnonzero(duplicates), 'Duplicate natural keys; do not silently drop revisions.')
        if check_order and schema == 'daily_bars' and len(df):
            try:
                actual = df.loc[:, keys].reset_index(drop=True)
                ordered = actual.sort_values(keys, kind='stable').reset_index(drop=True)
                if not actual.equals(ordered): add('warning', 'unsorted_rows', ','.join(keys), [], 'Daily rows are not in ascending key order.')
            except (ValueError, TypeError):
                pass  # Invalid value rules above carry the primary error.
    if {'low_price', 'high_price'}.issubset(df):
        bad=[]
        for i, (lo, hi) in enumerate(zip(df.low_price, df.high_price)):
            try:
                a,b = _decimal(lo,'low_price'),_decimal(hi,'high_price')
                if a is not None and b is not None and b > 0 and a > b: bad.append(i)
            except InvalidArgumentError: pass
        if bad: add('error','low_above_high','low_price,high_price',bad,'Reported daily low exceeds high.')
    if not isinstance(df.attrs.get('pydara'), dict):
        add('warning','provenance_unknown',None,[], 'No PyDara metadata: structural validity is not source authenticity.')
    out = pd.DataFrame(issues, columns=['severity','rule','column','count','row_positions','message'])
    for c in ('severity','rule','column','message'): out[c] = out[c].astype('string')
    out['count'] = out['count'].astype('Int64')
    out.attrs['pydara'] = {'validated_schema':schema,'checked_rows':len(df),
        'is_valid':not any(r['severity']=='error' for r in issues), 'economic_truth_verified':False}
    if raise_on_error and not out.attrs['pydara']['is_valid']:
        exc = DataQualityError('Data validation failed; inspect exception.report or call validate_data().')
        exc.report = out
        raise exc
    return out


def normalize_data(df: pd.DataFrame, *, schema: str = 'daily_bars',
                   columns: Mapping[str, str] | None = None, calendar: Calendar = 'gregorian',
                   numeric: str = 'analysis', timezone: str | None = None,
                   sort: bool = False) -> pd.DataFrame:
    """Normalize only present known fields; never invent source/time/zero values.

    ``columns`` is an explicit old-name -> standard-name mapping. Date strings
    use the explicitly supplied calendar. Naive real timestamps require timezone.
    Floating-point identifiers are rejected even when they look integral: original
    digits may already be lost. Unknown columns are preserved, rows are not dropped,
    duplicate keys are left for validate_data(), and the input/index are preserved
    unless sort=True reorders rows. No investment calculation is performed.
    """
    _frame(df)
    template = _schema_frame(schema, numeric)
    if not isinstance(calendar, str) or calendar not in ('gregorian','jalali') or not isinstance(sort, bool):
        raise InvalidArgumentError('Use an explicit calendar and a bool sort.')
    if columns is not None and (not isinstance(columns, Mapping) or
            any(k not in df or not isinstance(v,str) or not v for k,v in columns.items())):
        raise InvalidArgumentError('columns must map existing columns to nonempty new names.')
    out = df.copy(deep=True)
    out.attrs = deepcopy(df.attrs)
    if columns:
        out = out.rename(columns=dict(columns))
    _frame(out)
    changes = []
    for c in out:
        if c not in template:
            continue
        expected = template[c].dtype
        vals = list(out[c])
        if c in _IDENTIFIERS:
            converted=[]
            for v in vals:
                if _missing(v): converted.append(pd.NA)
                elif isinstance(v, str): converted.append(v.strip())
                elif isinstance(v, numbers.Integral) and not isinstance(v, (bool,np.bool_)): converted.append(str(v))
                else: raise InvalidArgumentError(f'{c}: floating identifiers cannot be safely recovered; reload as text.')
            if c in ('ins_code', 'index_code') and any(v is not pd.NA and (not v.isascii() or not v.isdigit() or int(v)<=0) for v in converted):
                raise InvalidArgumentError(f'{c} must contain positive ASCII digits.')
            out[c] = pd.array(converted, dtype='string')
        elif c == 'date':
            days=[]
            for v in vals:
                if _missing(v): days.append(pd.NaT); continue
                if isinstance(v, (pd.Timestamp,datetime)):
                    if v.tzinfo is not None or any((v.hour,v.minute,v.second,v.microsecond,getattr(v,'nanosecond',0))):
                        raise InvalidArgumentError('Daily date contains a timezone/time; convert explicitly before normalization.')
                    v=v.date()
                days.append(parse_date(v,calendar=calendar,name='date'))
            out[c]=pd.array(days,dtype='datetime64[ns]')
        elif isinstance(expected,pd.DatetimeTZDtype):
            stamps=[]
            for v in vals:
                if _missing(v): stamps.append(pd.NaT); continue
                if isinstance(v, numbers.Number):
                    raise InvalidArgumentError(f'{c}: epoch units are not inferred.')
                try:
                    stamp=pd.Timestamp(v)
                    if stamp.tzinfo is None:
                        if timezone is None: raise InvalidArgumentError(f'{c}: provide timezone for naive timestamps.')
                        stamp=stamp.tz_localize(timezone,ambiguous='raise',nonexistent='raise')
                    stamps.append(stamp.tz_convert('UTC'))
                except (ValueError,TypeError) as exc:
                    if isinstance(exc,InvalidArgumentError): raise
                    raise InvalidArgumentError(f'{c}: invalid timestamp.') from exc
            out[c]=pd.array(stamps,dtype='datetime64[ns, UTC]')
        elif str(expected) in ('Float64','Int64') or c in (*_PRICE_COLUMNS,'volume','turnover') or (schema in _MARKET_SCHEMAS and c in _MARKET_SCHEMAS[schema].numbers):
            nums=[_decimal(v,c) for v in vals]
            if str(expected)=='Int64':
                if any(v is not None and v!=v.to_integral_value() for v in nums): raise InvalidArgumentError(f'{c}: expected integer counts.')
                out[c]=pd.array([int(v) if v is not None else pd.NA for v in nums],dtype='Int64')
            elif numeric=='exact': out[c]=pd.Series(nums,index=out.index,dtype=object)
            else:
                if any(v is not None and not math.isfinite(float(v)) for v in nums): raise InvalidArgumentError(f'{c}: overflow; use numeric="exact".')
                out[c]=pd.array([float(v) if v is not None else pd.NA for v in nums],dtype='Float64')
        elif str(expected)=='boolean':
            if any(not _missing(v) and not isinstance(v,(bool,np.bool_)) for v in vals):
                raise InvalidArgumentError(f'{c}: use bool values; strings such as "False" are not guessed.')
            out[c]=pd.array(vals,dtype='boolean')
        elif isinstance(expected,pd.StringDtype):
            if any(not _missing(v) and not isinstance(v,str) for v in vals):
                raise InvalidArgumentError(f'{c}: expected strings.')
            if c=='symbol': vals=[normalize_symbol(v) if not _missing(v) else pd.NA for v in vals]
            out[c]=pd.array(vals,dtype='string')
        else: continue
        changes.append(c)
    if sort:
        keys=[c for c in ('request_index','index_code','ins_code','date','source_timestamp') if c in out]
        if keys: out=out.sort_values(keys,kind='stable')
    meta=frame_metadata(df)
    if columns: meta['renamed_columns']=dict(columns)
    meta.update(normalized_schema=schema,normalized_columns=changes,numeric=numeric,
                normalization_does_not_verify_source=True)
    out.attrs['pydara']=meta
    return out


def validate(df: pd.DataFrame, *, schema: str, strict: bool = True) -> pd.DataFrame:
    """Roadmap-compatible validation entry point.

    Returns row_id, rule, severity, message and additional grouped diagnostic
    columns. A grouped issue may have no single row_id; count and row_positions
    then describe it. strict=True raises DataQualityError with this same report.
    This verifies a structural contract, not source correctness or completeness.
    """
    if not isinstance(strict,bool):
        raise InvalidArgumentError('strict must be bool.')
    out=validate_data(df,schema=schema,raise_on_error=False)
    row_ids=[]
    for examples in out.row_positions:
        rid=df.iloc[examples[0]]['row_id'] if len(examples)==1 and 'row_id' in df else pd.NA
        row_ids.append(rid)
    out.insert(0,'row_id',pd.array(row_ids,dtype='string'))
    if strict and not out.attrs['pydara']['is_valid']:
        exc=DataQualityError('Data validation failed; inspect exception.report.')
        exc.report=out
        raise exc
    return out


def normalize(df: pd.DataFrame, *, schema: str, source: str,
              strict: bool = True) -> pd.DataFrame:
    """Roadmap normalization entry point for already canonical column names.

    source='canonical' is the currently reviewed mapping. Raw external API
    mappings are not inferred; use normalize_data(columns=...) for an explicit
    user mapping and then validate it. All unknown sources fail explicitly.
    """
    if not isinstance(source,str) or source!='canonical':
        from pydara.tse._core.exceptions import UnsupportedCapabilityError
        raise UnsupportedCapabilityError(
            "normalize currently supports source='canonical' only. "
            'For user-provided column mappings use normalize_data(columns=...).')
    if not isinstance(strict,bool):
        raise InvalidArgumentError('strict must be bool.')
    result=normalize_data(df,schema=schema)
    if strict:validate(result,schema=schema)
    return result


def load_sample(name: str = 'daily_prices_v1') -> pd.DataFrame:
    """Load explicit synthetic data with no database access or real network.

    Names: daily_prices_v1, quote_v1, market_watch_v1, client_types_v1,
    indices_v1 and index_history_v1. These are teaching/test values, never
    current market prices, and they cannot become live data through fallback.
    """
    extended_samples = {
        'trades_v1': ('get_trades', ('\u0641\u0648\u0644\u0627\u062f',), {'day':'2025-03-18'}),
        'order_book_v1': ('get_order_book', ('\u0641\u0648\u0644\u0627\u062f',), {}),
        'adjustments_v1': ('get_adjustments', ('\u0641\u0648\u0644\u0627\u062f',), {}),
        'adjusted_history_v1': ('get_adjusted_history', ('\u0641\u0648\u0644\u0627\u062f',), {}),
        'funds_v1': ('get_funds', (), {}),
        'fund_nav_v1': ('get_fund_nav_history', ('7001',), {}),
        'shareholders_v1': ('get_shareholders', ('\u0641\u0648\u0644\u0627\u062f',), {}),
        'options_v1': ('get_options', (), {}),
        'futures_v1': ('get_futures', (), {}),
        'dividends_v1': ('get_dividends', ('\u0641\u0648\u0644\u0627\u062f',), {}),
    }
    if isinstance(name,str) and name in extended_samples:
        from .samples.extended import sample_extended_client
        method,args,kwargs=extended_samples[name]
        with sample_extended_client() as client:return getattr(client,method)(*args,**kwargs)
    if isinstance(name,str) and name in ('market_watch_v1','client_types_v1','index_history_v1','indices_v1'):
        from .samples.market import sample_market_client
        with sample_market_client(storage=False) as client:
            if name == 'market_watch_v1': frame = client.get_market_watch(include_order_book=True, include_client_types=True)
            elif name == 'client_types_v1': frame = client._get_client_type_history('\u0641\u0648\u0644\u0627\u062f', include_jdate=True)
            elif name == 'indices_v1': frame = client.get_indices(market=None)
            else: frame = client.get_index_history('32097828799138957', include_jdate=True)
        frame.attrs['pydara'].update(synthetic=True, sample_name=name)
        return frame
    if not isinstance(name,str) or name not in ('daily_prices_v1','quote_v1'):
        raise InvalidArgumentError('Unknown sample. Use daily_prices_v1, quote_v1, market_watch_v1, client_types_v1, indices_v1 or index_history_v1.')
    from .samples import sample_client
    with sample_client(storage=False) as client:
        if name=='daily_prices_v1':
            frame=client.get_history('\u0641\u0648\u0644\u0627\u062f',include_jdate=True)
        else:frame=client.get_quote_frame('\u0641\u0648\u0644\u0627\u062f')
    frame.attrs['pydara'].update(synthetic=True,sample_name=name)
    return frame

# Shared metadata does not turn reported adjustments into a total-return series.
_DESCRIPTIONS['adjustment'] = 'Raw none or explicitly requested source-adjusted series; inspect method and anchor metadata.'
