"""Read-only daily-history adapter. A response is validated before caching.

Only GetClosingPriceDailyList/{verified_ins_code}/0 is used. This is one full
server response, not a range/pagination API. Missing days are not fabricated.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from zoneinfo import ZoneInfo

from pydara.tse._core.exceptions import DataQualityError, SchemaMismatchError
from ..transport import Packet, RequestSpec, decode
from .public import decimal_value, identifier, quote_response_identifier_status

NUMERIC_FIELDS = {
    'open_price': 'priceFirst', 'high_price': 'priceMax', 'low_price': 'priceMin',
    'last_price': 'pDrCotVal', 'closing_price': 'pClosing',
    'previous_reference_price': 'priceYesterday', 'volume': 'qTotTran5J',
    'turnover': 'qTotCap',
}


@dataclass(frozen=True)
class HistoryRows:
    """Represent history rows data used by the TSE module.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    rows: tuple[dict, ...]
    source_row_count: int
    identical_duplicates: int


def history_spec(ins_code: str, n: int = 0) -> RequestSpec:
    """Perform the history spec operation.
    
    Args:
        ins_code (str): Input for the history_spec operation.
        n (int): Input for the history_spec operation.
    
    Returns:
        RequestSpec: Result of the history_spec operation; refer to its public API contract for schema details.
    
    Raises:
        SchemaMismatchError: When the corresponding validation or operation fails."""
    code = identifier(ins_code)
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        raise SchemaMismatchError('History limit must be a nonnegative integer.')
    return RequestSpec('history.daily', f'ClosingPrice/GetClosingPriceDailyList/{code}/{n}',
                       'closingPriceDaily', 3600.0)


def _integral(value, field: str, *, optional=False) -> int | None:
    """Process internal integral data.
    
    Args:
        value (Any): Input for the _integral operation.
        field (str): Requested data field.
        optional (Any): Input for the _integral operation.
    
    Returns:
        int | None: Result of the _integral operation; refer to its public API contract for schema details.
    
    Raises:
        DataQualityError: When the corresponding validation or operation fails.
        SchemaMismatchError: When the corresponding validation or operation fails."""
    if value in (None, '') and not isinstance(value, bool) and optional:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, str, Decimal)):
        raise SchemaMismatchError(f'{field} must be an exact integer representation.')
    try:
        number = Decimal(value)
    except (ValueError, InvalidOperation) as exc:
        raise SchemaMismatchError(f'Invalid integer {field}: {value!r}.') from exc
    if not number.is_finite() or number < 0 or number != number.to_integral_value():
        raise SchemaMismatchError(f'{field} is negative, nonfinite or nonintegral: {value!r}.')
    if number > 9223372036854775807:
        raise DataQualityError(f'{field} does not fit Int64; refusing lossy coercion.')
    return int(number)


def _date_time(row: dict) -> tuple[date, datetime | None]:
    """Process internal date time data.
    
    Args:
        row (dict): Input for the _date_time operation.
    
    Returns:
        tuple[date, datetime | None]: Result of the _date_time operation; refer to its public API contract for schema details.
    
    Raises:
        SchemaMismatchError: When the corresponding validation or operation fails.
        ValueError: When the corresponding validation or operation fails."""
    value = _integral(row.get('dEven'), 'dEven')
    text = str(value)
    try:
        if len(text) != 8:
            raise ValueError
        day = date(int(text[:4]), int(text[4:6]), int(text[6:]))
        if not date(1678, 1, 1) <= day <= date(2261, 12, 31):
            raise ValueError
    except ValueError as exc:
        raise SchemaMismatchError(f'dEven is not a supported Gregorian YYYYMMDD: {value!r}.') from exc
    heven = _integral(row.get('hEven'), 'hEven', optional=True)
    if heven is None:
        return day, None
    h, m, s = heven // 10000, heven // 100 % 100, heven % 100
    try:
        stamp = datetime(day.year, day.month, day.day, h, m, s,
                         tzinfo=ZoneInfo('Asia/Tehran')).astimezone(UTC)
    except ValueError as exc:
        raise SchemaMismatchError(f'hEven is not HHMMSS: {heven!r}.') from exc
    return day, stamp


def _canonical(value):
    """Process internal canonical data.
    
    Args:
        value (Any): Input for the _canonical operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    if isinstance(value, Decimal):
        # Canonical decimal without context rounding or expansion of huge exponents.
        parts = value.as_tuple()
        digits = ''.join(map(str, parts.digits))
        if not value:
            return '0'
        trimmed = digits.rstrip('0')
        exp = parts.exponent + len(digits) - len(trimmed)
        return ('-' if parts.sign else '') + trimmed + 'e' + str(exp)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def parse_history_rows(packet: Packet, spec: RequestSpec) -> HistoryRows:
    """Parse history rows.
    
    Args:
        packet (Packet): Response packet received from a provider.
        spec (RequestSpec): Request or schema specification.
    
    Returns:
        HistoryRows: Result of the parse_history_rows operation; refer to its public API contract for schema details.
    
    Raises:
        DataQualityError: When the corresponding validation or operation fails.
        SchemaMismatchError: When the corresponding validation or operation fails.
        type(exc): When the corresponding validation or operation fails."""
    values = decode(packet, spec)
    if not isinstance(values, list):
        raise SchemaMismatchError('closingPriceDaily must be a JSON list; null is not an empty success.')
    expected = identifier(spec.path.rsplit('/', 2)[1])
    seen: dict[date, dict] = {}
    duplicates = 0
    today = packet.fetched_at.astimezone(ZoneInfo('Asia/Tehran')).date()
    for index, raw in enumerate(values):
        try:
            if not isinstance(raw, dict):
                raise SchemaMismatchError('Each history row must be a JSON object.')
            for key in ('dEven', 'pDrCotVal', 'pClosing'):
                if key not in raw:
                    raise SchemaMismatchError(f'Missing history field {key}.')
            flags = []
            identity_flag = quote_response_identifier_status(raw.get('insCode'), expected)
            if identity_flag:
                flags.append(identity_flag.replace('quote_response_', 'history_response_'))
            day, stamp = _date_time(raw)
            vals = {field: decimal_value(raw.get(source), source)
                    for field, source in NUMERIC_FIELDS.items()}
            for field, source in NUMERIC_FIELDS.items():
                if vals[field] is None:
                    flags.append('missing_' + field)
            for field, number in vals.items():
                if number is not None and (len(number.as_tuple().digits) > 128
                                          or abs(number.as_tuple().exponent) > 512):
                    raise DataQualityError(f'{field} exceeds supported numeric precision/exponent limits.')
            count = _integral(raw.get('zTotTran'), 'zTotTran', optional=True)
            if count is None:
                flags.append('missing_trade_count')
            reported_id = raw.get('id')
            if reported_id is not None and (isinstance(reported_id, bool)
                    or not isinstance(reported_id, (int, str, Decimal))):
                raise SchemaMismatchError('Invalid source row id.')
            lo, hi = vals['low_price'], vals['high_price']
            if lo is not None and hi is not None and lo > 0 and hi > 0 and lo > hi:
                raise DataQualityError('Daily low exceeds daily high.')
            if any(vals[x] == 0 for x in ('open_price', 'high_price', 'low_price', 'last_price', 'closing_price')):
                flags.append('zero_price_as_reported')
            if count == 0 or vals['volume'] == 0:
                flags.append('no_trade_or_zero_volume_as_reported')
            if lo and hi and lo <= hi:
                for field in ('last_price', 'open_price'):
                    p = vals[field]
                    if p is not None and p > 0 and not lo <= p <= hi:
                        flags.append(field + '_outside_reported_range')
            if stamp is None:
                flags.append('source_time_unknown')
            if day > today:
                flags.append('source_date_in_future')
            elif day == today:
                flags.append('current_session_row_not_certified_final')
            row = dict(ins_code=expected, date=day, **vals, trade_count=count,
                       source_timestamp=stamp, raw_ins_code=_canonical(raw.get('insCode')),
                       source_record_id=None if reported_id is None else str(reported_id),
                       quality_flags=tuple(flags))
            # Business content identity, independent of fetch time and source container id.
            business = {k: _canonical(row[k]) for k in ('ins_code', 'date', *NUMERIC_FIELDS,
                                                       'trade_count', 'source_timestamp')}
            digest = sha256(json.dumps(business, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            row['row_version_id'] = digest
            prior = seen.get(day)
            if prior is not None:
                if prior['row_version_id'] != digest:
                    raise DataQualityError(f'Conflicting duplicate daily rows on {day}; no arbitrary winner selected.')
                duplicates += 1
                prior['quality_flags'] = tuple(dict.fromkeys((*prior['quality_flags'], *flags,
                                                              'identical_duplicate_removed')))
            else:
                seen[day] = row
        except (SchemaMismatchError, DataQualityError) as exc:
            raise type(exc)(f'{spec.endpoint_id}, ins_code={expected}, row={index}: {exc}') from exc
    return HistoryRows(tuple(seen[d] for d in sorted(seen)), len(values), duplicates)
