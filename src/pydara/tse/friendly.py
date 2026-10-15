"""Small Pandas/data helpers. No hidden HTTP, disk writes, or financial analysis."""
from __future__ import annotations
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from collections.abc import Sequence
import math
import pandas as pd
from pydara.tse._core.exceptions import InvalidArgumentError, DataQualityError
from .dates import parse_range, parse_date
from .pandas_tools import _frame, select_columns, frame_metadata

_DIGITS=str.maketrans('\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669','01234567890123456789')


def friendly_range(start=None,end=None,*,calendar='auto'):
    """Auto is ONLY for supported contemporary ranges: 1200..1599 Jalali,
    1800..2199 Gregorian. Other years require an explicit calendar. This does
    not guess between two valid historical calendars outside those ranges.
    Dates are Gregorian by Python convention; mixing inferred calendars raises.
    """
    vals=[v.translate(_DIGITS).replace('/','-') if isinstance(v,str) else v for v in (start,end)]
    if calendar=='auto':
        inferred=set()
        for v in vals:
            if v is None:continue
            if isinstance(v,(date,datetime)):inferred.add('gregorian');continue
            if not isinstance(v,str):raise InvalidArgumentError('Dates must be date objects or YYYY-MM-DD strings.')
            try:y=int(v.split('-')[0])
            except ValueError as exc:raise InvalidArgumentError('Invalid date string.') from exc
            if 1200<=y<=1599:inferred.add('jalali')
            elif 1800<=y<=2199:inferred.add('gregorian')
            else:raise InvalidArgumentError('Ambiguous calendar: pass calendar="gregorian" or "jalali".')
        if len(inferred)>1:raise InvalidArgumentError('Do not mix inferred Gregorian and Jalali ranges.')
        calendar=next(iter(inferred),'gregorian')
    lo,hi=parse_range(*vals,calendar=calendar)
    return lo,hi,calendar


def to_pandas(value, *, copy=True) -> pd.DataFrame:
    """Obtain a caller-owned DataFrame; no automatic import of optional engines.
    Supports DataFrame, a PyDara object with to_frame(), records, or BatchFrames.data.
    Does not invent provenance for external data.
    """
    if not isinstance(copy,bool):raise InvalidArgumentError('copy must be bool.')
    if isinstance(value,pd.DataFrame):return value.copy(deep=True) if copy else value
    if hasattr(value,'to_frame'):return value.to_frame()
    if hasattr(value,'data') and isinstance(value.data,pd.DataFrame):return value.data.copy(deep=copy)
    if isinstance(value,(list,tuple,dict)):
        frame=pd.DataFrame(value);frame.attrs['pydara']={'provenance':'unknown_external','coverage_status':'unknown'};return frame
    raise InvalidArgumentError('Expected DataFrame, PyDara quote/batch, or records.')


def select(df: pd.DataFrame, columns=None, *, symbols=None, start=None, end=None, calendar='auto', date_column='date') -> pd.DataFrame:
    """Filter without mutating input. Omitted columns retain all evidence."""
    _frame(df);out=df.copy(deep=True);out.attrs=deepcopy(df.attrs)
    if symbols is not None:
        from .providers.public import normalize_symbol
        if 'symbol' not in out:raise InvalidArgumentError('No symbol column.')
        if isinstance(symbols,str):symbols=[symbols]
        symbols=[normalize_symbol(s) for s in symbols]
        out=out.loc[out['symbol'].isin(symbols)].copy()
    lo,hi,cal=friendly_range(start,end,calendar=calendar)
    if lo or hi:
        if date_column not in out:raise InvalidArgumentError('Missing date column.')
        dates=pd.to_datetime(out[date_column],errors='raise')
        if getattr(dates.dt,'tz',None) is not None:raise InvalidArgumentError('Use a timezone-naive session date column.')
        out=out.loc[(dates>=pd.Timestamp(lo) if lo else True)&(dates<=pd.Timestamp(hi) if hi else True)].copy()
    out=out.reset_index(drop=True);out.attrs=deepcopy(df.attrs)
    out.attrs.setdefault('pydara',{}).update(filtered=True,returned_rows=len(out),selected_calendar=cal)
    return select_columns(out,columns) if columns is not None else out


def set_date_index(df: pd.DataFrame, *, column='date', calendar='gregorian', by=None, sort=True, verify_unique=True) -> pd.DataFrame:
    """Use a date or (ins_code,date) index, preserving identifier strings.
    Multi-instrument frames automatically retain ins_code in the index.
    """
    _frame(df)
    if column not in df:raise InvalidArgumentError(f'Missing column {column}.')
    if not isinstance(sort,bool) or not isinstance(verify_unique,bool):raise InvalidArgumentError('sort/verify_unique must be bool.')
    out=df.copy(deep=True)
    if calendar=='jalali':
        out[column]=pd.to_datetime([parse_date(str(v),calendar='jalali') if pd.notna(v) else None for v in out[column]])
    elif calendar=='gregorian':out[column]=pd.to_datetime(out[column],errors='raise')
    else:raise InvalidArgumentError('Index calendar must be explicit: gregorian or jalali.')
    if out[column].isna().any():raise DataQualityError('Missing date cannot become a reliable date index.')
    if by is None:by=['ins_code'] if 'ins_code' in out and out.ins_code.nunique(dropna=False)>1 else []
    if isinstance(by,str):by=[by]
    if not isinstance(by,(list,tuple)) or any(c not in out for c in by):raise InvalidArgumentError('by must contain existing columns.')
    try:out=out.set_index([*by,column],verify_integrity=verify_unique)
    except ValueError as exc:raise DataQualityError('Duplicate index keys; preserve revisions or request_index explicitly.') from exc
    if sort:out=out.sort_index(kind='stable')
    out.attrs=deepcopy(df.attrs);out.attrs.setdefault('pydara',{}).update(index_columns=[*by,column])
    return out


def concat(frames: Sequence[pd.DataFrame], *, verify_keys=None) -> pd.DataFrame:
    """Concatenate schema-compatible tables, preserving component provenance.
    Unknown schema remains unknown. Raw and adjusted data are never mixed silently.
    """
    frames=list(frames)
    if not frames:raise InvalidArgumentError('Supply at least one DataFrame.')
    for f in frames:_frame(f)
    schemas={f.attrs.get('pydara',{}).get('schema_id') for f in frames}
    if len(schemas-{None})>1:raise DataQualityError('Different schemas; align explicitly before concat.')
    for c in ('adjustment','series','currency','quote_unit','quantity_unit'):
        vals=set()
        for f in frames:
            if c in f:vals.update(str(x) for x in f[c].dropna().unique())
        if len(vals)>1:raise DataQualityError(f'Incompatible {c} values.')
    components=[deepcopy(f.attrs.get('pydara',{})) for f in frames]
    copies=[]
    for f in frames:c=f.copy();c.attrs={};copies.append(c)
    out=pd.concat(copies,ignore_index=True)
    if verify_keys and out.duplicated(list(verify_keys)).any():raise DataQualityError('Duplicate requested natural keys.')
    out.attrs['pydara']={'schema_id':next(iter(schemas)) if len(schemas)==1 else None,
        'components':components,'coverage_status':'unknown','returned_rows':len(out),
        'is_stale':any(bool(x.get('is_stale')) for x in components),
        'warnings':['concatenation_does_not_certify_coverage']}
    return out


def coverage(df: pd.DataFrame, *, expected_sessions=None, start=None, end=None, calendar='auto') -> pd.DataFrame:
    """Observed coverage only. Holidays/halts cannot be inferred from absent rows."""
    _frame(df)
    if 'date' not in df:raise InvalidArgumentError('A date column is required.')
    f=select(df,start=start,end=end,calendar=calendar)
    expected=None if expected_sessions is None else _expected(expected_sessions)
    if expected is not None:
        lo,hi,_=friendly_range(start,end,calendar=calendar)
        if lo:expected=expected[expected>=pd.Timestamp(lo)]
        if hi:expected=expected[expected<=pd.Timestamp(hi)]
    rows=[];groups=f.groupby('ins_code',dropna=False,sort=False) if 'ins_code' in f and len(f) else [(None,f)]
    for code,g in groups:
        dates=pd.to_datetime(g['date']).dropna().dt.normalize();unique=pd.DatetimeIndex(dates.unique())
        rows.append(dict(ins_code=code,rows=len(g),observed_sessions=len(unique),first_date=dates.min(),last_date=dates.max(),
            duplicate_dates=int(dates.duplicated().sum()),missing_expected_sessions=None if expected is None else len(expected.difference(unique)),
            coverage_status='unknown' if expected is None else 'complete_relative_to_supplied_sessions' if expected.difference(unique).empty else 'partial_relative_to_supplied_sessions'))
    return pd.DataFrame(rows,columns=['ins_code','rows','observed_sessions','first_date','last_date','duplicate_dates','missing_expected_sessions','coverage_status'])


def _expected(sessions):
    """Process internal expected data.
    
    Args:
        sessions (Any): Input for the _expected operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails."""
    if isinstance(sessions,pd.DataFrame):
        if 'date' not in sessions:raise InvalidArgumentError('Expected sessions need a date column.')
        sessions=sessions['date']
    try:idx=pd.DatetimeIndex(pd.to_datetime(sessions,errors='raise'))
    except Exception as exc:raise InvalidArgumentError('expected_sessions must be explicit Gregorian dates.') from exc
    if idx.tz is not None or idx.hasnans:raise InvalidArgumentError('Expected sessions must be non-null naive dates.')
    return idx.normalize().unique().sort_values()


def missing_sessions(df: pd.DataFrame, *, expected_sessions, date_column='date') -> pd.DataFrame:
    """Compare to caller-supplied sessions. Missing means no record, not a holiday or halt."""
    _frame(df);expected=_expected(expected_sessions)
    if date_column not in df:raise InvalidArgumentError('Missing date column.')
    rows=[];groups=df.groupby('ins_code',dropna=False,sort=False) if 'ins_code' in df and len(df) else [(None,df)]
    for code,g in groups:
        actual=pd.DatetimeIndex(pd.to_datetime(g[date_column]).dropna()).normalize()
        rows.extend({'ins_code':code,'date':d,'status':'record_missing_reason_unknown'} for d in expected.difference(actual))
    return pd.DataFrame(rows,columns=['ins_code','date','status'])


def compare_sources(left: pd.DataFrame,right: pd.DataFrame, *, keys=('ins_code','date'), columns=None, atol=0.0, rtol=0.0) -> pd.DataFrame:
    """Compare two supplied tables without fetching sources or replacing values.
    Currency/adjustment mismatch raises. Differences are evidence, not a verdict.
    """
    _frame(left);_frame(right)
    if any(k not in left or k not in right for k in keys):raise InvalidArgumentError('Comparison keys missing.')
    if left.duplicated(list(keys)).any() or right.duplicated(list(keys)).any():raise DataQualityError('Comparison keys must be unique.')
    if not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) and x>=0 for x in (atol,rtol)):
        raise InvalidArgumentError('Tolerances must be finite and nonnegative.')
    for field in ('currency','quote_unit','quantity_unit','adjustment','series'):
        if field in left and field in right and set(left[field].dropna().astype(str)) != set(right[field].dropna().astype(str)):
            raise DataQualityError(f'Cannot compare incompatible {field}.')
    if columns is None:columns=[c for c in ('last_price','closing_price','volume','turnover','trade_count') if c in left and c in right]
    columns=list(columns)
    if not columns or any(c not in left or c not in right or c in keys for c in columns):raise InvalidArgumentError('Select common non-key value columns.')
    a=left.set_index(list(keys));b=right.set_index(list(keys));rows=[]
    for key in a.index.union(b.index,sort=False):
        keytuple=key if isinstance(key,tuple) else (key,);kdict=dict(zip(keys,keytuple))
        if key not in a.index or key not in b.index:
            rows.append(dict(kdict,column=None,left=None,right=None,status='left_only' if key in a.index else 'right_only'));continue
        for col in columns:
            x,y=a.loc[key,col],b.loc[key,col]
            if pd.isna(x) and pd.isna(y):continue
            equal=False
            if not pd.isna(x) and not pd.isna(y):
                if x==y:equal=True
                else:
                    try:
                        dx,dy=Decimal(str(x)),Decimal(str(y))
                        equal=abs(dx-dy)<=Decimal(str(atol))+Decimal(str(rtol))*abs(dy)
                    except (InvalidOperation,ValueError):pass
            if not equal:rows.append(dict(kdict,column=col,left=x,right=y,status='different'))
    return pd.DataFrame(rows,columns=[*keys,'column','left','right','status'])
