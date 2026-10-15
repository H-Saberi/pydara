"""Strict calendar-aware dates; no global locale or external calendar dependency.

The Nowruz calculation is adapted from jalaali-js (MIT), based on Borkowski.
See THIRD_PARTY_NOTICES.md. This API deliberately limits Jalali conversion
 to years 1200..1599 (well inside the documented Intl agreement interval).
Python date objects always mean Gregorian, regardless of ``calendar``.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta
from functools import lru_cache
import re
from typing import Literal
import pandas as pd

from pydara.tse._core.exceptions import InvalidArgumentError

DateLike = date | str | pd.Timestamp
Calendar = Literal['gregorian', 'jalali']
_DIGITS = str.maketrans('\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669', '01234567890123456789')
_BREAKS = (-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210, 1635,
           2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178)
MIN_JALALI_YEAR = 1200
MAX_JALALI_YEAR = 1599


@lru_cache(maxsize=512)
def _nowruz(jy: int) -> date:
    # All dividend values used below are nonnegative in the allowed range,
    # so Python // and % agree with jalaali-js truncation in this calculation.
    """Process internal nowruz data.
    
    Args:
        jy (int): Input for the _nowruz operation.
    
    Returns:
        date: Result of the _nowruz operation; refer to its public API contract for schema details.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails."""
    if not MIN_JALALI_YEAR - 1 <= jy <= MAX_JALALI_YEAR + 1:
        raise InvalidArgumentError('Jalali year is outside the supported conversion range.')
    gy, leap_j, jp = jy + 621, -14, _BREAKS[0]
    for jm in _BREAKS[1:]:
        jump = jm - jp
        if jy < jm:
            break
        leap_j += jump // 33 * 8 + (jump % 33) // 4
        jp = jm
    n = jy - jp
    leap_j += n // 33 * 8 + ((n % 33) + 3) // 4
    if jump % 33 == 4 and jump - n == 4:
        leap_j += 1
    leap_g = gy // 4 - ((gy // 100 + 1) * 3) // 4 - 150
    return date(gy, 3, 20 + leap_j - leap_g)


def _jalali_to_date(y: int, m: int, d: int) -> date:
    """Process internal jalali to date data.
    
    Args:
        y (int): Input for the _jalali_to_date operation.
        m (int): Input for the _jalali_to_date operation.
        d (int): Input for the _jalali_to_date operation.
    
    Returns:
        date: Result of the _jalali_to_date operation; refer to its public API contract for schema details.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails."""
    if not MIN_JALALI_YEAR <= y <= MAX_JALALI_YEAR or not 1 <= m <= 12:
        raise InvalidArgumentError('Jalali conversion supports years 1200..1599 and months 1..12.')
    leap = (_nowruz(y + 1) - _nowruz(y)).days == 366
    length = 31 if m <= 6 else 30 if m <= 11 else 30 if leap else 29
    if not 1 <= d <= length:
        raise InvalidArgumentError('Invalid day for the specified Jalali month/year.')
    offset = (m - 1) * 31 if m <= 6 else 186 + (m - 7) * 30
    return _nowruz(y) + timedelta(days=offset + d - 1)


def parse_date(value: DateLike | None, *, calendar: Calendar = 'gregorian',
               name: str = 'date') -> date | None:
    """Parse an accepted Gregorian or Jalali date representation.
    
    Args:
        value (DateLike | None): Input for the parse_date operation.
        calendar (Calendar): Calendar used to parse or format dates.
        name (str): Input for the parse_date operation.
    
    Returns:
        date | None: Result of the parse_date operation; refer to its public API contract for schema details.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails."""
    if calendar not in ('gregorian', 'jalali'):
        raise InvalidArgumentError('calendar must be gregorian or jalali.')
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        if value.tzinfo is not None or any((value.hour, value.minute, value.second,
                                          value.microsecond, value.nanosecond)):
            raise InvalidArgumentError(f'{name}: Pandas Timestamp must be midnight without timezone.')
        return value.date()
    if isinstance(value, datetime):
        raise InvalidArgumentError(f'{name}: use datetime.date or an ISO date string, not datetime.')
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise InvalidArgumentError(f'{name}: expected date or YYYY-MM-DD string.')
    text = value.translate(_DIGITS).strip()
    if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', text):
        raise InvalidArgumentError(f'{name}: use YYYY-MM-DD (calendar explicitly specified).')
    year, month, day = map(int, text.split('-'))
    try:
        return date(year, month, day) if calendar == 'gregorian' else _jalali_to_date(year, month, day)
    except ValueError as exc:
        raise InvalidArgumentError(f'{name}: invalid {calendar} date {value!r}.') from exc


def parse_range(start: DateLike | None, end: DateLike | None, *,
                calendar: Calendar = 'gregorian') -> tuple[date | None, date | None]:
    """Normalize and validate the requested date range.
    
    Args:
        start (DateLike | None): Optional beginning of the requested date range.
        end (DateLike | None): Optional end of the requested date range.
        calendar (Calendar): Calendar used to parse or format dates.
    
    Returns:
        tuple[date | None, date | None]: Result of the parse_range operation; refer to its public API contract for schema details.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails."""
    lo = parse_date(start, calendar=calendar, name='start')
    hi = parse_date(end, calendar=calendar, name='end')
    if lo is not None and hi is not None and lo > hi:
        raise InvalidArgumentError('start must not be later than end.')
    # The public table uses datetime64[ns]; reject unsupported bounds before HTTP.
    if any(x is not None and not date(1678, 1, 1) <= x <= date(2261, 12, 31) for x in (lo, hi)):
        raise InvalidArgumentError('Dates must fit the table range 1678-01-01..2261-12-31.')
    return lo, hi


def to_gregorian(value: DateLike, *, calendar: Calendar = 'jalali') -> date:
    """Convert an accepted date to its Gregorian representation.
    
    Args:
        value (DateLike): Input for the to_gregorian operation.
        calendar (Calendar): Calendar used to parse or format dates.
    
    Returns:
        date: Result of the to_gregorian operation; refer to its public API contract for schema details.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails."""
    result = parse_date(value, calendar=calendar)
    if result is None:
        raise InvalidArgumentError('A date is required.')
    return result


def to_jalali(value: DateLike) -> str:
    """Convert an accepted date to its Jalali representation.
    
    Args:
        value (DateLike): Input for the to_jalali operation.
    
    Returns:
        str: Result of the to_jalali operation; refer to its public API contract for schema details.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails."""
    gd = parse_date(value, calendar='gregorian')
    if gd is None:
        raise InvalidArgumentError('A date is required.')
    jy = gd.year - 621
    if not MIN_JALALI_YEAR <= jy <= MAX_JALALI_YEAR + 1:
        raise InvalidArgumentError('Date is outside supported Jalali years 1200..1599.')
    if gd < _nowruz(jy):
        jy -= 1
    if not MIN_JALALI_YEAR <= jy <= MAX_JALALI_YEAR:
        raise InvalidArgumentError('Date is outside supported Jalali years 1200..1599.')
    delta = (gd - _nowruz(jy)).days
    if delta < 186:
        month, day = delta // 31 + 1, delta % 31 + 1
    else:
        month, day = (delta - 186) // 30 + 7, (delta - 186) % 30 + 1
    return f'{jy:04d}-{month:02d}-{day:02d}'
