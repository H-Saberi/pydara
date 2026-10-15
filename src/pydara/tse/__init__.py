"""Data-only public facade: simple functions and native sync/async clients.

All tabular outputs are ordinary Pandas DataFrames. No network, directory,
SQLite database or worker thread is created by importing this module.
"""
from __future__ import annotations
from copy import deepcopy
from threading import RLock
from collections.abc import Sequence, Iterator
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import pandas as pd
import numpy as np
from .engine import build_config
from pydara.tse._core.models import InstrumentLike
from pydara.tse._core.exceptions import ConfigurationError
from .config import positive
from .sync import SyncResult, SyncPlan

from pydara.tse._core.models import (
    InstrumentRef, InstrumentRecord, Quote, Market, QuoteUnit, QuantityUnit,
    RecordMeta, WriteReceipt, StorageStatus, FlushReport,
)
from .config import ClientConfig, NetworkConfig, StorageConfig, FetchPolicy, FreshnessPolicy
from .client import Client
from .async_client import AsyncClient
from .services import capability_frame
from .dates import DateLike, Calendar, to_gregorian, to_jalali
from .history_models import BatchFrames

__all__ = ["Client", "AsyncClient", "ClientConfig", "NetworkConfig", "StorageConfig",
           "FetchPolicy", "FreshnessPolicy", "InstrumentRef", "InstrumentRecord", "Quote", "Market",
           "QuoteUnit", "QuantityUnit", "RecordMeta", "WriteReceipt", "StorageStatus", "FlushReport",
           "search_instruments", "get_quote", "get_price", "get_quotes",
           "get_history", "get_history_many", "iter_history", "BatchFrames",
           "to_gregorian", "to_jalali", "DateLike", "Calendar",
           "capabilities", "storage_status", "get_write_receipt", "flush", "close"]
_default = None
_default_lock = RLock()



_default_config: ClientConfig | None = None

def _client() -> Client:
    """Process internal client data.
    
    Returns:
        Client: Result of the _client operation; refer to its public API contract for schema details."""
    global _default
    with _default_lock:
        if _default is None:
            _default = Client(config=_default_config)
        return _default


def configure(config: ClientConfig | None = None, *, source: str | None = None,
              mode: str | None = None, storage: bool | None = None,
              data_dir: str | Path | None = None, numeric: str | None = None) -> ClientConfig:
    """Configure the lazy module-level client without HTTP or creating a database.

Args:
    config (ClientConfig | None): See the function signature and related source validation for the accepted structure. Default: None.
    source (str | None): See the function signature and related source validation for the accepted structure. Default: None.
    mode (str | None): See the function signature and related source validation for the accepted structure. Default: None.
    storage (bool | None): See the function signature and related source validation for the accepted structure. Default: None.
    data_dir (str | Path | None): See the function signature and related source validation for the accepted structure. Default: None.
    numeric (str | None): See the function signature and related source validation for the accepted structure. Default: None.

Returns:
    ClientConfig: See the API reference for columns, metadata and error reporting.

Notes:
    Configure the lazy module-level client without HTTP or creating a database.
    
        Call before using data.get_*; if a default client already exists, close it
        explicitly with data.close() first. This avoids silently losing queued work
        or changing the configuration of an in-flight request. Omitted settings use
        ClientConfig defaults (or the explicitly supplied config)."""
    global _default_config
    new = build_config(config, source, mode, storage, data_dir, numeric)
    with _default_lock:
        if _default is not None:
            raise ConfigurationError('Call data.close() and inspect its report before data.configure().')
        _default_config = new
    return new


def get_config() -> ClientConfig:
    """Return immutable default settings without creating a Client or any I/O."""
    with _default_lock:
        return _default.config if _default is not None else (_default_config or ClientConfig())

def search_instruments(query: str, *, market: Market | None=None, include_inactive: bool=True, limit: int | None=None, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Search symbols without silently selecting the first match. Returns a typed DataFrame, including for no matches. A limit only limits displayed results; it is not a server pagination parameter.

Args:
    query (str): Search expression. A query is not a unique identifier and may match many results.
    market (Market | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: None.
    include_inactive (bool): Whether to include instruments without a reported active status. Default: True.
    limit (int | None): Maximum returned/displayed matches; None retains all eligible rows. Not necessarily remote pagination. Default: None.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Search symbols without silently selecting the first match. Returns a typed DataFrame, including for no matches. A limit only limits displayed results; it is not a server pagination parameter."""
    return _client().search_instruments(query, market=market, include_inactive=include_inactive, limit=limit, policy=policy)


def get_quote(instrument: InstrumentLike, *, freshness: FreshnessPolicy | None=None, policy: FetchPolicy | str | None=None) -> Quote:
    """Fetch the latest report as an immutable Quote with source and retrieval timestamps. A last report may be from a past trading day. Use an explicit offline policy to permit stale cached data; autosave errors are reported separately.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    freshness (FreshnessPolicy | None): FreshnessPolicy or None: controls tolerance of age for quote data; does not manufacture current market activity. Default: None.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    Quote: See the API reference for columns, metadata and error reporting.

Notes:
    Fetch the latest report as an immutable Quote with source and retrieval timestamps. A last report may be from a past trading day. Use an explicit offline policy to permit stale cached data; autosave errors are reported separately."""
    return _client().get_quote(instrument, freshness=freshness, policy=policy)


def get_price(instrument: InstrumentLike, *, field: str='last', freshness: FreshnessPolicy | None=None, policy: FetchPolicy | str | None=None) -> Decimal:
    """Return a Decimal price. field is last, closing or previous_reference. Missing price raises MissingValueError and unverified price units raise UnsupportedQuoteUnitError. Use get_quote/get_quote_frame to retain time and unit metadata.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    field (str): Allowed "last", "closing", "previous_reference" for get_price(). Default: 'last'.
    freshness (FreshnessPolicy | None): FreshnessPolicy or None: controls tolerance of age for quote data; does not manufacture current market activity. Default: None.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    Decimal: See the API reference for columns, metadata and error reporting.

Notes:
    Return a Decimal price. field is last, closing or previous_reference. Missing price raises MissingValueError and unverified price units raise UnsupportedQuoteUnitError. Use get_quote/get_quote_frame to retain time and unit metadata."""
    return _client().get_price(instrument, field=field, freshness=freshness, policy=policy)


def get_quote_frame(instrument: InstrumentLike, *, freshness: FreshnessPolicy | None=None, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """A one-row Pandas quote with the same checks as get_quote; no second HTTP call.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    freshness (FreshnessPolicy | None): FreshnessPolicy or None: controls tolerance of age for quote data; does not manufacture current market activity. Default: None.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    A one-row Pandas quote with the same checks as get_quote; no second HTTP call."""
    return _client().get_quote_frame(instrument, freshness=freshness, policy=policy)


def get_instrument_frame(instrument: InstrumentLike, *, market: Market | None=None, as_of: date | None=None, known_at: datetime | None=None, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Resolve exactly one instrument and return its typed one-row DataFrame.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    market (Market | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: None.
    as_of (date | None): See the function signature and related source validation for the accepted structure. Default: None.
    known_at (datetime | None): See the function signature and related source validation for the accepted structure. Default: None.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Resolve exactly one instrument and return its typed one-row DataFrame."""
    return _client().get_instrument_frame(instrument, market=market, as_of=as_of, known_at=known_at, policy=policy)


def get_quotes(instruments: Sequence[InstrumentLike] | pd.Series | pd.Index | np.ndarray, *, on_error: str='raise', freshness: FreshnessPolicy | None=None, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Fetch an ordered batch to a DataFrame. Accepts list/tuple, Series, Index or a 1D NumPy array. Duplicates and input order are preserved. on_error=collect records per-item errors; raise attaches partial_result to BatchDataError. No concurrency is implied.

Args:
    instruments (Sequence[InstrumentLike] | pd.Series | pd.Index | np.ndarray): Sequence of instrument references, pandas Series/Index, or one-dimensional NumPy array. See batch report for partial errors.
    on_error (str): Allowed: "collect" (record item failures and preserve successful rows) or "raise" (stop and raise). Defaults differ between individual APIs; see Signature. Default: 'raise'.
    freshness (FreshnessPolicy | None): FreshnessPolicy or None: controls tolerance of age for quote data; does not manufacture current market activity. Default: None.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Fetch an ordered batch to a DataFrame. Accepts list/tuple, Series, Index or a 1D NumPy array. Duplicates and input order are preserved. on_error=collect records per-item errors; raise attaches partial_result to BatchDataError. No concurrency is implied."""
    return _client().get_quotes(instruments, on_error=on_error, freshness=freshness, policy=policy)


def get_history(instrument: InstrumentLike, *, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', adjustment: str='none', series: str='listing', as_of: datetime | None=None, policy: FetchPolicy | str | None=None, include_jdate: bool=False) -> pd.DataFrame:
    """Daily history, ascending and inclusive, without filling absent rows. Raw is the default. adjustment="source" uses the separate TSETMC chart a=1 response and keeps raw history untouched; inspect method/anchor metadata. It is not a total-return or point-in-time guarantee. Stitched identities and as_of remain unsupported.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    start (DateLike | None): Inclusive starting date or None: date, supported date string or pandas.Timestamp. Use calendar for string interpretation. Default: None.
    end (DateLike | None): Inclusive ending date or None: date, supported date string or pandas.Timestamp. No missing trading days are fabricated. Default: None.
    calendar (Calendar): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'gregorian'.
    adjustment (str): Allowed "none" (raw prices), "source" (source-adjusted when supported). Source adjustment does not guarantee total-return or point-in-time correctness. Default: 'none'.
    series (str): See the function signature and related source validation for the accepted structure. Default: 'listing'.
    as_of (datetime | None): See the function signature and related source validation for the accepted structure. Default: None.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.
    include_jdate (bool): True adds a Jalali date column; False does not. This does not convert the underlying Gregorian date column. Default: False.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Daily history, ascending and inclusive, without filling absent rows. Raw is the default. adjustment="source" uses the separate TSETMC chart a=1 response and keeps raw history untouched; inspect method/anchor metadata. It is not a total-return or point-in-time guarantee. Stitched identities and as_of remain unsupported."""
    return _client().get_history(instrument, start=start, end=end, calendar=calendar, adjustment=adjustment, series=series, as_of=as_of, policy=policy, include_jdate=include_jdate)


def get_history_many(instruments: Sequence[InstrumentLike] | pd.Series | pd.Index | np.ndarray, *, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', adjustment: str='none', on_error: str='raise', policy: FetchPolicy | str | None=None, include_jdate: bool=False) -> BatchFrames:
    """Bounded sequential batch. Each input, even repeated/empty, gets a report row.

Args:
    instruments (Sequence[InstrumentLike] | pd.Series | pd.Index | np.ndarray): Sequence of instrument references, pandas Series/Index, or one-dimensional NumPy array. See batch report for partial errors.
    start (DateLike | None): Inclusive starting date or None: date, supported date string or pandas.Timestamp. Use calendar for string interpretation. Default: None.
    end (DateLike | None): Inclusive ending date or None: date, supported date string or pandas.Timestamp. No missing trading days are fabricated. Default: None.
    calendar (Calendar): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'gregorian'.
    adjustment (str): Allowed "none" (raw prices), "source" (source-adjusted when supported). Source adjustment does not guarantee total-return or point-in-time correctness. Default: 'none'.
    on_error (str): Allowed: "collect" (record item failures and preserve successful rows) or "raise" (stop and raise). Defaults differ between individual APIs; see Signature. Default: 'raise'.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.
    include_jdate (bool): True adds a Jalali date column; False does not. This does not convert the underlying Gregorian date column. Default: False.

Returns:
    BatchFrames: See the API reference for columns, metadata and error reporting.

Notes:
    Bounded sequential batch. Each input, even repeated/empty, gets a report row."""
    return _client().get_history_many(instruments, start=start, end=end, calendar=calendar, adjustment=adjustment, on_error=on_error, policy=policy, include_jdate=include_jdate)


def iter_history(instrument: InstrumentLike, *, start: DateLike, end: DateLike, calendar: Calendar='gregorian', adjustment: str='none', chunk_days: int=366, policy: FetchPolicy | str | None=None, include_jdate: bool=False) -> Iterator[pd.DataFrame]:
    """Yield local calendar chunks. The underlying full HTTP response is NOT streamed.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    start (DateLike): Inclusive starting date or None: date, supported date string or pandas.Timestamp. Use calendar for string interpretation.
    end (DateLike): Inclusive ending date or None: date, supported date string or pandas.Timestamp. No missing trading days are fabricated.
    calendar (Calendar): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'gregorian'.
    adjustment (str): Allowed "none" (raw prices), "source" (source-adjusted when supported). Source adjustment does not guarantee total-return or point-in-time correctness. Default: 'none'.
    chunk_days (int): See the function signature and related source validation for the accepted structure. Default: 366.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.
    include_jdate (bool): True adds a Jalali date column; False does not. This does not convert the underlying Gregorian date column. Default: False.

Returns:
    Iterator[pd.DataFrame]: See the API reference for columns, metadata and error reporting.

Notes:
    Yield local calendar chunks. The underlying full HTTP response is NOT streamed.
    
    Skips chunks without rows; yields one typed empty frame if the whole
    selected range is empty. Each frame records its actual and chunk range."""
    yield from _client().iter_history(instrument, start=start, end=end, calendar=calendar, adjustment=adjustment, chunk_days=chunk_days, policy=policy, include_jdate=include_jdate)


def sync_history(instrument: InstrumentLike, *, full: bool=False, overlap_days: int=14, full_refresh_days: float=7, wait: bool=True, timeout: float=30.0, on_storage_error: str='report') -> SyncResult:
    """Explicit reconciliation into the local history index. full=True rechecks old corrections; overlap_days controls the tail window. wait=True may wait for storage. on_storage_error=report preserves fetched data with failure information; raise demands success. SyncResult.data is only this fetch, not the whole database.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    full (bool): See the function signature and related source validation for the accepted structure. Default: False.
    overlap_days (int): See the function signature and related source validation for the accepted structure. Default: 14.
    full_refresh_days (float): See the function signature and related source validation for the accepted structure. Default: 7.
    wait (bool): See the function signature and related source validation for the accepted structure. Default: True.
    timeout (float): See the function signature and related source validation for the accepted structure. Default: 30.0.
    on_storage_error (str): See the function signature and related source validation for the accepted structure. Default: 'report'.

Returns:
    SyncResult: See the API reference for columns, metadata and error reporting.

Notes:
    Explicit reconciliation into the local history index. full=True rechecks old corrections; overlap_days controls the tail window. wait=True may wait for storage. on_storage_error=report preserves fetched data with failure information; raise demands success. SyncResult.data is only this fetch, not the whole database."""
    return _client().sync_history(instrument, full=full, overlap_days=overlap_days, full_refresh_days=full_refresh_days, wait=wait, timeout=timeout, on_storage_error=on_storage_error)


def load_stored_history(instrument: InstrumentLike, *, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, as_of: datetime | None=None) -> pd.DataFrame:
    """Read the versioned local history index; never sends HTTP. Dates are inclusive. as_of is a local observation/commit cutoff, not proof of historical public availability. Raises OfflineDataUnavailableError when no usable indexed data exists.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    start (DateLike | None): Inclusive starting date or None: date, supported date string or pandas.Timestamp. Use calendar for string interpretation. Default: None.
    end (DateLike | None): Inclusive ending date or None: date, supported date string or pandas.Timestamp. No missing trading days are fabricated. Default: None.
    calendar (Calendar): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'gregorian'.
    include_jdate (bool): True adds a Jalali date column; False does not. This does not convert the underlying Gregorian date column. Default: False.
    as_of (datetime | None): See the function signature and related source validation for the accepted structure. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Read the versioned local history index; never sends HTTP. Dates are inclusive. as_of is a local observation/commit cutoff, not proof of historical public availability. Raises OfflineDataUnavailableError when no usable indexed data exists."""
    return _client().load_stored_history(instrument, start=start, end=end, calendar=calendar, include_jdate=include_jdate, as_of=as_of)


def history_status() -> pd.DataFrame:
    'Return per-instrument counts, ranges and latest fetch state from the local index. Explicit disk read; no HTTP. Counts do not certify full market history.'
    return _client().history_status()


def get_history_revisions(instrument: InstrumentLike, *, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian') -> pd.DataFrame:
    """Return locally observed economic revisions in the requested inclusive range. This is local evidence, not all revisions ever published by the exchange.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    start (DateLike | None): Inclusive starting date or None: date, supported date string or pandas.Timestamp. Use calendar for string interpretation. Default: None.
    end (DateLike | None): Inclusive ending date or None: date, supported date string or pandas.Timestamp. No missing trading days are fabricated. Default: None.
    calendar (Calendar): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'gregorian'.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Return locally observed economic revisions in the requested inclusive range. This is local evidence, not all revisions ever published by the exchange."""
    return _client().get_history_revisions(instrument, start=start, end=end, calendar=calendar)


def reindex_history() -> dict:
    'Explicitly rebuild missing normalized history from cached responses of previous releases, without HTTP. Existing history is not deleted. Return a dictionary report; durable storage can raise StorageError.'
    return _client().reindex_history()


def capabilities() -> pd.DataFrame:
    'Return the implemented, conditional and deferred capability matrix. A source-reviewed endpoint is not a live-service guarantee.'
    return capability_frame()


def storage_status() -> StorageStatus:
    'Return in-memory storage counters without querying the database. Queued work is not durable until committed.'
    return _client().storage_status()


def get_write_receipt(receipt_id: str) -> WriteReceipt:
    """Read the receipt status for this process. Unknown IDs raise UnknownReceiptError. A queued receipt does not prove disk durability.

Args:
    receipt_id (str): See the function signature and related source validation for the accepted structure.

Returns:
    WriteReceipt: See the API reference for columns, metadata and error reporting.

Notes:
    Read the receipt status for this process. Unknown IDs raise UnknownReceiptError. A queued receipt does not prove disk durability."""
    return _client().get_write_receipt(receipt_id)


def flush(*, timeout: float=5.0, raise_on_error: bool=True) -> FlushReport:
    """Explicitly wait up to timeout seconds for queued persistence. With raise_on_error=True incomplete or failed storage raises StorageError/StorageFlushTimeout. Normal automatic saving never waits for this call.

Args:
    timeout (float): See the function signature and related source validation for the accepted structure. Default: 5.0.
    raise_on_error (bool): See the function signature and related source validation for the accepted structure. Default: True.

Returns:
    FlushReport: See the API reference for columns, metadata and error reporting.

Notes:
    Explicitly wait up to timeout seconds for queued persistence. With raise_on_error=True incomplete or failed storage raises StorageError/StorageFlushTimeout. Normal automatic saving never waits for this call."""
    return _client().flush(timeout=timeout, raise_on_error=raise_on_error)


def close(*, flush_timeout: float = 1.0) -> FlushReport:
    """Close the default client. Explicitly flush first to require durable writes.

Args:
    flush_timeout (float): See the function signature and related source validation for the accepted structure. Default: 1.0.

Returns:
    FlushReport: See the API reference for columns, metadata and error reporting.

Notes:
    Close the default client. Explicitly flush first to require durable writes.
    
        The selected configuration is retained; configure() can replace it after close."""
    global _default
    positive('flush_timeout', flush_timeout, zero=True)
    with _default_lock:
        if _default is None:
            from .engine import Core
            return Core.empty_report()
        c, _default = _default, None
    return c.close(flush_timeout=flush_timeout)


from .io import save, load
from .storage.history_store import HistoryStore
from .pandas_tools import (schema_info, validate_data, normalize_data, select_columns, frame_metadata,
                           validate, normalize, load_sample)
from .reference import api_reference
__all__ += ['get_quote_frame','get_instrument_frame','configure','get_config',
            'save','load','HistoryStore','SyncPlan','SyncResult',
            'sync_history','load_stored_history','history_status','get_history_revisions','reindex_history',
            'schema_info','validate_data','normalize_data','select_columns','frame_metadata','api_reference']

__all__ += ["validate", "normalize", "load_sample"]


# Market, participant and index public API (0.4.0).

def get_market_watch(*, market: Market | str | None=None, include_order_book: bool=False, include_client_types: bool=False, show_traded: bool=False, backend: str='auto', policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Return the current public market watch as a typed DataFrame. auto falls back to the reviewed legacy text route only when JSON returns a valid empty list. Optional books and client types retain independent provenance; rows are not an atomic snapshot. Empty is not proof of a closed market.

Args:
    market (Market | str | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: None.
    include_order_book (bool): Include order-book observations as available from the provider (not inferred). Default: False.
    include_client_types (bool): Include separate real/legal client types data when the source supports it. Default: False.
    show_traded (bool): See the function signature and related source validation for the accepted structure. Default: False.
    backend (str): Allowed "auto", "json", "legacy" where supported; auto fallback is conditional rather than a generic retry on every error. Default: 'auto'.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Return the current public market watch as a typed DataFrame. auto falls back to the reviewed legacy text route only when JSON returns a valid empty list. Optional books and client types retain independent provenance; rows are not an atomic snapshot. Empty is not proof of a closed market."""
    return _client().get_market_watch(market=market, include_order_book=include_order_book, include_client_types=include_client_types, show_traded=show_traded, backend=backend, policy=policy)

def get_market_order_book(*, market: Market | str | None=None, backend: str='auto', policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Return reported best-limit levels for the current watch. This is not the full exchange order book or historical depth. Missing levels are not filled. Source timestamps not reported by the feed remain missing.

Args:
    market (Market | str | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: None.
    backend (str): Allowed "auto", "json", "legacy" where supported; auto fallback is conditional rather than a generic retry on every error. Default: 'auto'.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Return reported best-limit levels for the current watch. This is not the full exchange order book or historical depth. Missing levels are not filled. Source timestamps not reported by the feed remain missing."""
    return _client().get_market_order_book(market=market, backend=backend, policy=policy)

def get_market_overview(*, market: Market | str=Market.TSE, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Return one row of reported market totals and index values. TSE or IFB only. Activity time and overall data time remain separate.

Args:
    market (Market | str): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: Market.TSE.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Return one row of reported market totals and index values. TSE or IFB only. Activity time and overall data time remain separate."""
    return _client().get_market_overview(market=market, policy=policy)

def get_market_map(*, sector_code: str | None=None, limit: int=9999, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Return the reported market-map data only; no drawing or computed ranking. The source size parameter can truncate output; coverage is not certified.

Args:
    sector_code (str | None): See the function signature and related source validation for the accepted structure. Default: None.
    limit (int): Maximum returned/displayed matches; None retains all eligible rows. Not necessarily remote pagination. Default: 9999.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Return the reported market-map data only; no drawing or computed ranking. The source size parameter can truncate output; coverage is not certified."""
    return _client().get_market_map(sector_code=sector_code, limit=limit, policy=policy)

def get_sectors(*, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Return sector codes/names with the four source counters preserved as source_c1..source_c4. Their undocumented bucket meanings are not guessed.

Args:
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Return sector codes/names with the four source counters preserved as source_c1..source_c4. Their undocumented bucket meanings are not guessed."""
    return _client().get_sectors(policy=policy)

def get_sector_instruments(sector_code: str, *, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Return current related-company quotes for an exact sector code. This is industry grouping, not evidence of corporate ownership.

Args:
    sector_code (str): See the function signature and related source validation for the accepted structure.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Return current related-company quotes for an exact sector code. This is industry grouping, not evidence of corporate ownership."""
    return _client().get_sector_instruments(sector_code, policy=policy)

def get_key_statistics(*, ins_code: str | int | None=None, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Return all reported parameter-code/value pairs (potentially a large response). ins_code filtering is local after the bulk response. reported_value stays text: undocumented units and metrics are not guessed.

Args:
    ins_code (str | int | None): One positive exchange instrument code as str/int, or an ordered list of codes for instrument(), history() and price(). Codes are identifiers, not company tickers. Default: None.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Return all reported parameter-code/value pairs (potentially a large response). ins_code filtering is local after the bulk response. reported_value stays text: undocumented units and metrics are not guessed."""
    return _client().get_key_statistics(ins_code=ins_code, policy=policy)



def get_market_client_types(*, market: Market | str | None=None, backend: str='auto', policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Return the bulk client-type response. With market selected, intersect with current watch identities (one extra component); without a filter, keep every returned ins_code. No date/value/market is guessed when absent.

Args:
    market (Market | str | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: None.
    backend (str): Allowed "auto", "json", "legacy" where supported; auto fallback is conditional rather than a generic retry on every error. Default: 'auto'.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Return the bulk client-type response. With market selected, intersect with current watch identities (one extra component); without a filter, keep every returned ins_code. No date/value/market is guessed when absent."""
    return _client().get_market_client_types(market=market, backend=backend, policy=policy)

def get_indices(*, market: Market | str | None=Market.TSE, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Return index codes, names and latest reported values. market=None explicitly requests TSE and IFB catalogs separately. Unit is points, never currency.

Args:
    market (Market | str | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: Market.TSE.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Return index codes, names and latest reported values. market=None explicitly requests TSE and IFB catalogs separately. Unit is points, never currency."""
    return _client().get_indices(market=market, policy=policy)

def search_indices(query: str, *, market: Market | str | None=Market.TSE, limit: int | None=None, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Search normalized current index names; never choose the first match implicitly. A local limit does not change server pagination.

Args:
    query (str): Search expression. A query is not a unique identifier and may match many results.
    market (Market | str | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: Market.TSE.
    limit (int | None): Maximum returned/displayed matches; None retains all eligible rows. Not necessarily remote pagination. Default: None.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Search normalized current index names; never choose the first match implicitly. A local limit does not change server pagination."""
    return _client().search_indices(query, market=market, limit=limit, policy=policy)

def get_index(index: str | int | InstrumentRef, *, market: Market | str | None=Market.TSE, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Resolve exactly one index from the current catalog by exact name or code, returning a one-row DataFrame. Ambiguous names raise. Use get_indices(market=None) to inspect available codes.

Args:
    index (str | int | InstrumentRef): Exact index identifier/name; ambiguous results must not be selected silently.
    market (Market | str | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: Market.TSE.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Resolve exactly one index from the current catalog by exact name or code, returning a one-row DataFrame. Ambiguous names raise. Use get_indices(market=None) to inspect available codes."""
    return _client().get_index(index, market=market, policy=policy)

def get_index_history(index: str | int | InstrumentRef, *, market: Market | str | None=Market.TSE, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Return daily index close/high/low in points, ascending with inclusive date filtering. Open and volume are not invented. A full response is fetched before local filtering.

Args:
    index (str | int | InstrumentRef): Exact index identifier/name; ambiguous results must not be selected silently.
    market (Market | str | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: Market.TSE.
    start (DateLike | None): Inclusive starting date or None: date, supported date string or pandas.Timestamp. Use calendar for string interpretation. Default: None.
    end (DateLike | None): Inclusive ending date or None: date, supported date string or pandas.Timestamp. No missing trading days are fabricated. Default: None.
    calendar (Calendar): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'gregorian'.
    include_jdate (bool): True adds a Jalali date column; False does not. This does not convert the underlying Gregorian date column. Default: False.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Return daily index close/high/low in points, ascending with inclusive date filtering. Open and volume are not invented. A full response is fetched before local filtering."""
    return _client().get_index_history(index, market=market, start=start, end=end, calendar=calendar, include_jdate=include_jdate, policy=policy)

def get_index_intraday(index: str | int | InstrumentRef, *, market: Market | str | None=Market.TSE, day: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Return index observations for the latest session available from the public endpoint. day=None only; selecting a historical session is not supported and raises before HTTP. Equal-time points preserve source order.

Args:
    index (str | int | InstrumentRef): Exact index identifier/name; ambiguous results must not be selected silently.
    market (Market | str | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: Market.TSE.
    day (DateLike | None): See the function signature and related source validation for the accepted structure. Default: None.
    calendar (Calendar): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'gregorian'.
    include_jdate (bool): True adds a Jalali date column; False does not. This does not convert the underlying Gregorian date column. Default: False.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Return index observations for the latest session available from the public endpoint. day=None only; selecting a historical session is not supported and raises before HTTP. Equal-time points preserve source order."""
    return _client().get_index_intraday(index, market=market, day=day, calendar=calendar, include_jdate=include_jdate, policy=policy)

def get_index_members(index: str | int | InstrumentRef, *, market: Market | str | None=Market.TSE, as_of: DateLike | None=None, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Return current constituent quotes, not historical membership or index weights. as_of is unsupported and raises before HTTP. Quote dates are not membership effective dates.

Args:
    index (str | int | InstrumentRef): Exact index identifier/name; ambiguous results must not be selected silently.
    market (Market | str | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: Market.TSE.
    as_of (DateLike | None): See the function signature and related source validation for the accepted structure. Default: None.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Return current constituent quotes, not historical membership or index weights. as_of is unsupported and raises before HTTP. Quote dates are not membership effective dates."""
    return _client().get_index_members(index, market=market, as_of=as_of, policy=policy)

def get_index_impact(*, market: Market | str=Market.TSE, limit: int=7, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """EXPERIMENTAL: fetch the reported total-market index-effect records and preserve every source field in source_fields. impact_points/unit remain unknown until the live economic mapping is verified. This does not compute index impact or address arbitrary indices.

Args:
    market (Market | str): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: Market.TSE.
    limit (int): Maximum returned/displayed matches; None retains all eligible rows. Not necessarily remote pagination. Default: 7.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    EXPERIMENTAL: fetch the reported total-market index-effect records and preserve every source field in source_fields. impact_points/unit remain unknown until the live economic mapping is verified. This does not compute index impact or address arbitrary indices."""
    return _client().get_index_impact(market=market, limit=limit, policy=policy)

def watch_market(*, interval: float=10.0, max_updates: int | None=10, market: Market | str | None=None, include_order_book: bool=False, include_client_types: bool=False, show_traded: bool=False, backend: str='auto') -> Iterator[pd.DataFrame]:
    """Yield freshly fetched full snapshots with bounded polling, not WebSocket deltas.

Args:
    interval (float): See the function signature and related source validation for the accepted structure. Default: 10.0.
    max_updates (int | None): See the function signature and related source validation for the accepted structure. Default: 10.
    market (Market | str | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: None.
    include_order_book (bool): Include order-book observations as available from the provider (not inferred). Default: False.
    include_client_types (bool): Include separate real/legal client types data when the source supports it. Default: False.
    show_traded (bool): See the function signature and related source validation for the accepted structure. Default: False.
    backend (str): Allowed "auto", "json", "legacy" where supported; auto fallback is conditional rather than a generic retry on every error. Default: 'auto'.

Returns:
    Iterator[pd.DataFrame]: See the API reference for columns, metadata and error reporting.

Notes:
    Yield freshly fetched full snapshots with bounded polling, not WebSocket deltas.
    
    A one-second local lower bound is not an exchange rate-limit promise.
    max_updates=None opts into indefinite polling. Cancel/close the iterator
    or interrupt execution to stop; exceptions propagate, no infinite retry."""
    yield from _client().watch_market(interval=interval, max_updates=max_updates, market=market, include_order_book=include_order_book, include_client_types=include_client_types, show_traded=show_traded, backend=backend)



def get_index_history_many(indices: Sequence[str | int | InstrumentRef] | pd.Series | pd.Index | np.ndarray, *, market: Market | str | None=Market.TSE, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, on_error: str='raise', policy: FetchPolicy | str | None=None) -> BatchFrames:
    """Sequential ordered batch with data/errors/requests tables. Input duplicates.

Args:
    indices (Sequence[str | int | InstrumentRef] | pd.Series | pd.Index | np.ndarray): See the function signature and related source validation for the accepted structure.
    market (Market | str | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: Market.TSE.
    start (DateLike | None): Inclusive starting date or None: date, supported date string or pandas.Timestamp. Use calendar for string interpretation. Default: None.
    end (DateLike | None): Inclusive ending date or None: date, supported date string or pandas.Timestamp. No missing trading days are fabricated. Default: None.
    calendar (Calendar): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'gregorian'.
    include_jdate (bool): True adds a Jalali date column; False does not. This does not convert the underlying Gregorian date column. Default: False.
    on_error (str): Allowed: "collect" (record item failures and preserve successful rows) or "raise" (stop and raise). Defaults differ between individual APIs; see Signature. Default: 'raise'.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    BatchFrames: See the API reference for columns, metadata and error reporting.

Notes:
    Sequential ordered batch with data/errors/requests tables. Input duplicates
    and empty successes have separate request rows. on_error=raise includes
    partial_result; collect reports per-item errors without claiming completeness."""
    return _client().get_index_history_many(indices, market=market, start=start, end=end, calendar=calendar, include_jdate=include_jdate, on_error=on_error, policy=policy)

__all__ += ['get_market_watch', 'get_market_order_book', 'get_market_overview', 'get_market_map', 'get_sectors', 'get_sector_instruments', 'get_key_statistics', 'get_market_client_types', 'get_indices', 'search_indices', 'get_index', 'get_index_history', 'get_index_intraday', 'get_index_members', 'get_index_impact', 'watch_market', 'get_index_history_many']


# Expanded data families

def get_adjustments(instrument: InstrumentLike, *, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Reported price-adjustment events and price ratios. Reasons and complete corporate-action coverage are unknown; this is not a total-return algorithm.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    start (DateLike | None): Inclusive starting date or None: date, supported date string or pandas.Timestamp. Use calendar for string interpretation. Default: None.
    end (DateLike | None): Inclusive ending date or None: date, supported date string or pandas.Timestamp. No missing trading days are fabricated. Default: None.
    calendar (Calendar): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'gregorian'.
    include_jdate (bool): True adds a Jalali date column; False does not. This does not convert the underlying Gregorian date column. Default: False.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Reported price-adjustment events and price ratios. Reasons and complete corporate-action coverage are unknown; this is not a total-return algorithm."""
    return _client().get_adjustments(instrument=instrument, start=start, end=end, calendar=calendar, include_jdate=include_jdate, policy=policy)

def get_share_capital_history(instrument: InstrumentLike, *, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Reported old/new share counts, not legal capital-increase classifications. All observed rows are retained.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    start (DateLike | None): Inclusive starting date or None: date, supported date string or pandas.Timestamp. Use calendar for string interpretation. Default: None.
    end (DateLike | None): Inclusive ending date or None: date, supported date string or pandas.Timestamp. No missing trading days are fabricated. Default: None.
    calendar (Calendar): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'gregorian'.
    include_jdate (bool): True adds a Jalali date column; False does not. This does not convert the underlying Gregorian date column. Default: False.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Reported old/new share counts, not legal capital-increase classifications. All observed rows are retained."""
    return _client().get_share_capital_history(instrument=instrument, start=start, end=end, calendar=calendar, include_jdate=include_jdate, policy=policy)

def get_dividends(instrument: InstrumentLike, *, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Dividend history from the legacy text route. Payment/ex dates are not inferred; failed or HTML responses raise.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    start (DateLike | None): Inclusive starting date or None: date, supported date string or pandas.Timestamp. Use calendar for string interpretation. Default: None.
    end (DateLike | None): Inclusive ending date or None: date, supported date string or pandas.Timestamp. No missing trading days are fabricated. Default: None.
    calendar (Calendar): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'gregorian'.
    include_jdate (bool): True adds a Jalali date column; False does not. This does not convert the underlying Gregorian date column. Default: False.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Dividend history from the legacy text route. Payment/ex dates are not inferred; failed or HTML responses raise."""
    return _client().get_dividends(instrument=instrument, start=start, end=end, calendar=calendar, include_jdate=include_jdate, policy=policy)

def get_adjusted_history(instrument: InstrumentLike, *, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Source-adjusted chart history, separate from raw history. Source method tsetmc_chart_a1; anchor is the last returned date. No total-return or point-in-time guarantee. Missing turnover/count/reference price stay missing.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    start (DateLike | None): Inclusive starting date or None: date, supported date string or pandas.Timestamp. Use calendar for string interpretation. Default: None.
    end (DateLike | None): Inclusive ending date or None: date, supported date string or pandas.Timestamp. No missing trading days are fabricated. Default: None.
    calendar (Calendar): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'gregorian'.
    include_jdate (bool): True adds a Jalali date column; False does not. This does not convert the underlying Gregorian date column. Default: False.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Source-adjusted chart history, separate from raw history. Source method tsetmc_chart_a1; anchor is the last returned date. No total-return or point-in-time guarantee. Missing turnover/count/reference price stay missing."""
    return _client().get_adjusted_history(instrument=instrument, start=start, end=end, calendar=calendar, include_jdate=include_jdate, policy=policy)

def get_shareholders(instrument: InstrumentLike, *, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Latest reported major shareholders. Empty does not prove that no major holders exist.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Latest reported major shareholders. Empty does not prove that no major holders exist."""
    return _client().get_shareholders(instrument=instrument, policy=policy)

def get_shareholder_history(instrument: InstrumentLike, holder_id: str | int, *, days: int=90, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """History of one holder of one instrument; holder_id comes from get_shareholders, not the holding_ref. days is 1..3650; date filtering is local.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    holder_id (str | int): See the function signature and related source validation for the accepted structure.
    days (int): See the function signature and related source validation for the accepted structure. Default: 90.
    start (DateLike | None): Inclusive starting date or None: date, supported date string or pandas.Timestamp. Use calendar for string interpretation. Default: None.
    end (DateLike | None): Inclusive ending date or None: date, supported date string or pandas.Timestamp. No missing trading days are fabricated. Default: None.
    calendar (Calendar): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'gregorian'.
    include_jdate (bool): True adds a Jalali date column; False does not. This does not convert the underlying Gregorian date column. Default: False.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    History of one holder of one instrument; holder_id comes from get_shareholders, not the holding_ref. days is 1..3650; date filtering is local."""
    return _client().get_shareholder_history(instrument=instrument, holder_id=holder_id, days=days, start=start, end=end, calendar=calendar, include_jdate=include_jdate, policy=policy)

def get_disclosures(instrument: InstrumentLike, *, limit: int=20, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Disclosure metadata linked by TSETMC. Does not download or parse financial-statement attachments. limit is 1..1000; dates filter the returned subset only.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    limit (int): Maximum returned/displayed matches; None retains all eligible rows. Not necessarily remote pagination. Default: 20.
    start (DateLike | None): Inclusive starting date or None: date, supported date string or pandas.Timestamp. Use calendar for string interpretation. Default: None.
    end (DateLike | None): Inclusive ending date or None: date, supported date string or pandas.Timestamp. No missing trading days are fabricated. Default: None.
    calendar (Calendar): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'gregorian'.
    include_jdate (bool): True adds a Jalali date column; False does not. This does not convert the underlying Gregorian date column. Default: False.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Disclosure metadata linked by TSETMC. Does not download or parse financial-statement attachments. limit is 1..1000; dates filter the returned subset only."""
    return _client().get_disclosures(instrument=instrument, limit=limit, start=start, end=end, calendar=calendar, include_jdate=include_jdate, policy=policy)

def get_messages(instrument: InstrumentLike, *, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Reported instrument supervisor messages, with source timestamp and original text.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    start (DateLike | None): Inclusive starting date or None: date, supported date string or pandas.Timestamp. Use calendar for string interpretation. Default: None.
    end (DateLike | None): Inclusive ending date or None: date, supported date string or pandas.Timestamp. No missing trading days are fabricated. Default: None.
    calendar (Calendar): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'gregorian'.
    include_jdate (bool): True adds a Jalali date column; False does not. This does not convert the underlying Gregorian date column. Default: False.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Reported instrument supervisor messages, with source timestamp and original text."""
    return _client().get_messages(instrument=instrument, start=start, end=end, calendar=calendar, include_jdate=include_jdate, policy=policy)

def get_trades(instrument: InstrumentLike, *, day: DateLike | None=None, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, max_days: int=31, cancellation: str='as_reported', policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Reported executions, current or per explicit calendar day. Same-second trades are not deduplicated. Cancellation remains unknown; only as_reported is supported. Max 31 days by default, configurable up to 366.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    day (DateLike | None): See the function signature and related source validation for the accepted structure. Default: None.
    start (DateLike | None): Inclusive starting date or None: date, supported date string or pandas.Timestamp. Use calendar for string interpretation. Default: None.
    end (DateLike | None): Inclusive ending date or None: date, supported date string or pandas.Timestamp. No missing trading days are fabricated. Default: None.
    calendar (Calendar): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'gregorian'.
    include_jdate (bool): True adds a Jalali date column; False does not. This does not convert the underlying Gregorian date column. Default: False.
    max_days (int): See the function signature and related source validation for the accepted structure. Default: 31.
    cancellation (str): See the function signature and related source validation for the accepted structure. Default: 'as_reported'.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Reported executions, current or per explicit calendar day. Same-second trades are not deduplicated. Cancellation remains unknown; only as_reported is supported. Max 31 days by default, configurable up to 366."""
    return _client().get_trades(instrument=instrument, day=day, start=start, end=end, calendar=calendar, include_jdate=include_jdate, max_days=max_days, cancellation=cancellation, policy=policy)

def get_order_book(instrument: InstrumentLike, *, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Current reported best limits (up to five depths), not a full exchange order book. Missing source timestamps stay missing.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Current reported best limits (up to five depths), not a full exchange order book. Missing source timestamps stay missing."""
    return _client().get_order_book(instrument=instrument, policy=policy)

def get_order_book_history(instrument: InstrumentLike, *, start: DateLike, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, max_days: int=31, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Historical best-limit updates. Sequence/reference and source position are preserved. No fill-forward or fictional complete snapshots; empty days do not prove holidays.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    start (DateLike): Inclusive starting date or None: date, supported date string or pandas.Timestamp. Use calendar for string interpretation.
    end (DateLike | None): Inclusive ending date or None: date, supported date string or pandas.Timestamp. No missing trading days are fabricated. Default: None.
    calendar (Calendar): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'gregorian'.
    include_jdate (bool): True adds a Jalali date column; False does not. This does not convert the underlying Gregorian date column. Default: False.
    max_days (int): See the function signature and related source validation for the accepted structure. Default: 31.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Historical best-limit updates. Sequence/reference and source position are preserved. No fill-forward or fictional complete snapshots; empty days do not prove holidays."""
    return _client().get_order_book_history(instrument=instrument, start=start, end=end, calendar=calendar, include_jdate=include_jdate, max_days=max_days, policy=policy)

def get_instrument_states(instrument: InstrumentLike, *, day: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Reported state/price-limit records for one day. No day means the last trading date reported by the quote, not today. Empty is not interpreted as open/unrestricted.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    day (DateLike | None): See the function signature and related source validation for the accepted structure. Default: None.
    calendar (Calendar): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'gregorian'.
    include_jdate (bool): True adds a Jalali date column; False does not. This does not convert the underlying Gregorian date column. Default: False.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Reported state/price-limit records for one day. No day means the last trading date reported by the quote, not today. Empty is not interpreted as open/unrestricted."""
    return _client().get_instrument_states(instrument=instrument, day=day, calendar=calendar, include_jdate=include_jdate, policy=policy)

def get_thresholds(instrument: InstrumentLike, *, day: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Reported state/price-limit records for one day. No day means the last trading date reported by the quote, not today. Empty is not interpreted as open/unrestricted.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    day (DateLike | None): See the function signature and related source validation for the accepted structure. Default: None.
    calendar (Calendar): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'gregorian'.
    include_jdate (bool): True adds a Jalali date column; False does not. This does not convert the underlying Gregorian date column. Default: False.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Reported state/price-limit records for one day. No day means the last trading date reported by the quote, not today. Empty is not interpreted as open/unrestricted."""
    return _client().get_thresholds(instrument=instrument, day=day, calendar=calendar, include_jdate=include_jdate, policy=policy)

def get_boards(*, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Board codes from the reviewed reference HTML table. A replaced page raises rather than returning a false empty registry.

Args:
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Board codes from the reviewed reference HTML table. A replaced page raises rather than returning a false empty registry."""
    return _client().get_boards(policy=policy)

def get_instruments(*, market: Market | str | None=None, include_inactive: bool=False, changed_since: DateLike | None=None, backend: str='auto', policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Current observed watch instrument list only. include_inactive=True and changed_since require a historical registry and raise; suspended instruments may still be in the current watch.

Args:
    market (Market | str | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: None.
    include_inactive (bool): Whether to include instruments without a reported active status. Default: False.
    changed_since (DateLike | None): See the function signature and related source validation for the accepted structure. Default: None.
    backend (str): Allowed "auto", "json", "legacy" where supported; auto fallback is conditional rather than a generic retry on every error. Default: 'auto'.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Current observed watch instrument list only. include_inactive=True and changed_since require a historical registry and raise; suspended instruments may still be in the current watch."""
    return _client().get_instruments(market=market, include_inactive=include_inactive, changed_since=changed_since, backend=backend, policy=policy)

def get_funds(category: str | None='stock', *, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Registered funds by category name/code; None explicitly fetches the ten reviewed categories. registration_no is not an ins_code.

Args:
    category (str | None): See the function signature and related source validation for the accepted structure. Default: 'stock'.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Registered funds by category name/code; None explicitly fetches the ten reviewed categories. registration_no is not an ins_code."""
    return _client().get_funds(category=category, policy=policy)

def get_fund(registration_no: str | int, *, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Fund detail as a one-row frame with raw fields retained. Use the registration_no from get_funds.

Args:
    registration_no (str | int): See the function signature and related source validation for the accepted structure.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Fund detail as a one-row frame with raw fields retained. Use the registration_no from get_funds."""
    return _client().get_fund(registration_no=registration_no, policy=policy)

def get_fund_nav_history(registration_no: str | int, *, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Reported NAV stats; unit/currency not supplied by source remain unknown, not assumed from stock prices.

Args:
    registration_no (str | int): See the function signature and related source validation for the accepted structure.
    start (DateLike | None): Inclusive starting date or None: date, supported date string or pandas.Timestamp. Use calendar for string interpretation. Default: None.
    end (DateLike | None): Inclusive ending date or None: date, supported date string or pandas.Timestamp. No missing trading days are fabricated. Default: None.
    calendar (Calendar): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'gregorian'.
    include_jdate (bool): True adds a Jalali date column; False does not. This does not convert the underlying Gregorian date column. Default: False.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Reported NAV stats; unit/currency not supplied by source remain unknown, not assumed from stock prices."""
    return _client().get_fund_nav_history(registration_no=registration_no, start=start, end=end, calendar=calendar, include_jdate=include_jdate, policy=policy)

def get_options(underlying: InstrumentLike | None=None, *, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Public option-chain pairs expanded into one row per put/call contract. Underlying filter is optional and local. No option pricing or inferred Greeks.

Args:
    underlying (InstrumentLike | None): See the function signature and related source validation for the accepted structure. Default: None.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Public option-chain pairs expanded into one row per put/call contract. Underlying filter is optional and local. No option pricing or inferred Greeks."""
    return _client().get_options(underlying=underlying, policy=policy)

def get_futures(*, source: str='tse_exchange', policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Current futures snapshot from the separate public tse.ir exchange gateway (not TSETMC CDN). Source must be tse_exchange. Fields with unverified meanings remain in source_fields. No history or commodity-exchange completeness guarantee.

Args:
    source (str): See the function signature and related source validation for the accepted structure. Default: 'tse_exchange'.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Current futures snapshot from the separate public tse.ir exchange gateway (not TSETMC CDN). Source must be tse_exchange. Fields with unverified meanings remain in source_fields. No history or commodity-exchange completeness guarantee."""
    return _client().get_futures(source=source, policy=policy)


from .friendly import to_pandas, set_date_index, select, concat, coverage, missing_sessions, compare_sources
from .diagnostics import setup, check_connection, diagnose
from .workflows import export_many
from .io import save as export

def history(assets=None, *, ins_code=None, symbol=None, start=None, end=None,
            calendar='auto', adjustment='none', include_jdate=False, policy=None,
            on_multiple='all', on_conflict='error', on_error='collect') -> pd.DataFrame:
    """Return unified daily history for symbol, explicit code, instrument DataFrame or list.

Args:
    assets (pandas.DataFrame | str | list[str] | None): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied. Default: None.
    ins_code (Any): One positive exchange instrument code as str/int, or an ordered list of codes for instrument(), history() and price(). Codes are identifiers, not company tickers. Default: None.
    symbol (Any): Trading symbol text (e.g. "فولاد"); history() also accepts this named criterion. Multiple matching records are governed by on_multiple. Default: None.
    start (Any): Inclusive starting date or None: date, supported date string or pandas.Timestamp. Use calendar for string interpretation. Default: None.
    end (Any): Inclusive ending date or None: date, supported date string or pandas.Timestamp. No missing trading days are fabricated. Default: None.
    calendar (Any): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'auto'.
    adjustment (Any): Allowed "none" (raw prices), "source" (source-adjusted when supported). Source adjustment does not guarantee total-return or point-in-time correctness. Default: 'none'.
    include_jdate (Any): True adds a Jalali date column; False does not. This does not convert the underlying Gregorian date column. Default: False.
    policy (Any): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.
    on_multiple (Any): Allowed: "all" (default: keep every match), "first" (choose one in stable source order), "error" (raise on multiple matches). Applies to identity resolution, not HTTP errors. Default: 'all'.
    on_conflict (Any): Allowed: "error" (default: reject conflicting identity criteria), "ins_code" (trust explicit ins_code when other filters conflict; requires ins_code). Default: 'error'.
    on_error (Any): Allowed: "collect" (record item failures and preserve successful rows) or "raise" (stop and raise). Defaults differ between individual APIs; see Signature. Default: 'collect'.

Returns:
    pd.DataFrame: Returns one merged DataFrame, including identity columns for multiple instruments. With on_error="collect", consult result.attrs["pydara"]["errors"] for item failures. Dates are inclusive. No missing sessions are inserted.

Raises:
    InvalidArgumentError: Unsupported or inconsistent input or policy value.
    AmbiguousInstrumentError: Ambiguous identity when on_multiple="error".
    PyDaraError: Data acquisition, network, offline or validation errors as applicable.

Notes:
    Returns one merged DataFrame, including identity columns for multiple instruments. With on_error="collect", consult result.attrs["pydara"]["errors"] for item failures. Dates are inclusive. No missing sessions are inserted.

Examples:
    >>> from pydara import tse
    >>> instruments = tse.assets(symbol="فولاد")
    >>> data = tse.history(instruments, start="1403-01-01", end="1403-12-29", calendar="jalali")
    >>> data.attrs.get("pydara", {}).get("errors")"""
    return _public_frame(_client().history(_normalize_assets(assets), ins_code=ins_code, symbol=symbol, start=start,
        end=end, calendar=calendar, adjustment=adjustment, include_jdate=include_jdate,
        policy=policy, on_multiple=on_multiple, on_conflict=on_conflict, on_error=on_error))

def _legacy_price(instrument=None, *, ins_code=None, on_multiple='all', on_conflict='error',
          on_error='collect', freshness=None, policy=None) -> pd.DataFrame:
    """Return unified quote DataFrame including trading state and retrieval timestamps.

Args:
    instrument (pandas.DataFrame | str | list[str] | None): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied. Default: None.
    ins_code (Any): One positive exchange instrument code as str/int, or an ordered list of codes for instrument(), history() and price(). Codes are identifiers, not company tickers. Default: None.
    on_multiple (Any): Allowed: "all" (default: keep every match), "first" (choose one in stable source order), "error" (raise on multiple matches). Applies to identity resolution, not HTTP errors. Default: 'all'.
    on_conflict (Any): Allowed: "error" (default: reject conflicting identity criteria), "ins_code" (trust explicit ins_code when other filters conflict; requires ins_code). Default: 'error'.
    on_error (Any): Allowed: "collect" (record item failures and preserve successful rows) or "raise" (stop and raise). Defaults differ between individual APIs; see Signature. Default: 'collect'.
    freshness (Any): FreshnessPolicy or None: controls tolerance of age for quote data; does not manufacture current market activity. Default: None.
    policy (Any): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: Returns one DataFrame for one or many instruments. state describes the trading quote state, is_active the instrument identity status, and fetched_at the retrieval timestamp. These are different concepts; a cached quote is not a live quote.

Raises:
    InvalidArgumentError: Unsupported or inconsistent input or policy value.
    AmbiguousInstrumentError: Ambiguous identity when on_multiple="error".
    PyDaraError: Data acquisition, network, offline or validation errors as applicable.

Notes:
    Returns one DataFrame for one or many instruments. state describes the trading quote state, is_active the instrument identity status, and fetched_at the retrieval timestamp. These are different concepts; a cached quote is not a live quote.

Examples:
    >>> from pydara import tse
    >>> selected = tse.assets(symbol="فولاد")
    >>> quotes = tse.prices(selected, on_multiple="all", on_error="collect")
    >>> quotes[[c for c in ("symbol", "state", "is_active", "fetched_at") if c in quotes]]"""
    return _client().price(instrument,ins_code=ins_code,on_multiple=on_multiple,
        on_conflict=on_conflict,on_error=on_error,freshness=freshness,policy=policy)

def market(*, market: Market | str | None=None, include_order_book: bool=False, include_client_types: bool=False, backend: str='auto', policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Simple alias for get_market_watch; no financial analysis.

Args:
    market (Market | str | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: None.
    include_order_book (bool): Include order-book observations as available from the provider (not inferred). Default: False.
    include_client_types (bool): Include separate real/legal client types data when the source supports it. Default: False.
    backend (str): Allowed "auto", "json", "legacy" where supported; auto fallback is conditional rather than a generic retry on every error. Default: 'auto'.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Simple alias for get_market_watch; no financial analysis."""
    return _client().market(market=market, include_order_book=include_order_book, include_client_types=include_client_types, backend=backend, policy=policy)

def index_history(index: str | int, *, start: DateLike | None=None, end: DateLike | None=None, calendar: str='auto', include_jdate: bool=False, market: Market | str | None=Market.TSE, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
    """Simple index-history alias with explicit auto-calendar policy.

Args:
    index (str | int): Exact index identifier/name; ambiguous results must not be selected silently.
    start (DateLike | None): Inclusive starting date or None: date, supported date string or pandas.Timestamp. Use calendar for string interpretation. Default: None.
    end (DateLike | None): Inclusive ending date or None: date, supported date string or pandas.Timestamp. No missing trading days are fabricated. Default: None.
    calendar (str): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'auto'.
    include_jdate (bool): True adds a Jalali date column; False does not. This does not convert the underlying Gregorian date column. Default: False.
    market (Market | str | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: Market.TSE.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Simple index-history alias with explicit auto-calendar policy."""
    return _client().index_history(index=index, start=start, end=end, calendar=calendar, include_jdate=include_jdate, market=market, policy=policy)

def datasets() -> pd.DataFrame:
    'List locally stored response families, without HTTP.'
    return _client().datasets()

def storage_info() -> pd.DataFrame:
    'Inspect local storage health and file sizes, without HTTP.'
    return _client().storage_info()

def query(instrument: InstrumentLike, *, dataset: str='history', start: DateLike | None=None, end: DateLike | None=None, calendar: str='auto', include_jdate: bool=False) -> pd.DataFrame:
    """Read locally stored data only. Never a live request; cached results retain time and stale flags.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    dataset (str): Dataset family, such as "history", accepted by the specific API. See catalog/capabilities for supported data. Default: 'history'.
    start (DateLike | None): Inclusive starting date or None: date, supported date string or pandas.Timestamp. Use calendar for string interpretation. Default: None.
    end (DateLike | None): Inclusive ending date or None: date, supported date string or pandas.Timestamp. No missing trading days are fabricated. Default: None.
    calendar (str): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'auto'.
    include_jdate (bool): True adds a Jalali date column; False does not. This does not convert the underlying Gregorian date column. Default: False.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Read locally stored data only. Never a live request; cached results retain time and stale flags."""
    return _client().query(instrument=instrument, dataset=dataset, start=start, end=end, calendar=calendar, include_jdate=include_jdate)

def backup(path: str | Path, *, overwrite: bool=False, timeout: float=30.0, flush: bool=True) -> dict:
    """Explicit SQLite backup with WAL consistency, integrity check and timeout. Does not change the original database.

Args:
    path (str | Path): See the function signature and related source validation for the accepted structure.
    overwrite (bool): See the function signature and related source validation for the accepted structure. Default: False.
    timeout (float): See the function signature and related source validation for the accepted structure. Default: 30.0.
    flush (bool): See the function signature and related source validation for the accepted structure. Default: True.

Returns:
    dict: See the API reference for columns, metadata and error reporting.

Notes:
    Explicit SQLite backup with WAL consistency, integrity check and timeout. Does not change the original database."""
    return _client().backup(path=path, overwrite=overwrite, timeout=timeout, flush=flush)

def download(symbols, *, dataset: str='history', start: DateLike | None=None, end: DateLike | None=None, calendar: str='auto', update: bool=True, store: bool | None=None, on_error: str='collect', checkpoint_dir: str | Path | None=None, resume: bool=True, resume_max_age: float=3600.0, include_jdate: bool=False, progress=None, policy: FetchPolicy | str | None=None) -> BatchFrames:
    """Ordered data job with reports and opt-in disk checkpoints. Uses existing bounded network budget; partial success is explicit.

Args:
    symbols (Any): Ordered collection of symbol references to download; independent symbols do not need common characters.
    dataset (str): Dataset family, such as "history", accepted by the specific API. See catalog/capabilities for supported data. Default: 'history'.
    start (DateLike | None): Inclusive starting date or None: date, supported date string or pandas.Timestamp. Use calendar for string interpretation. Default: None.
    end (DateLike | None): Inclusive ending date or None: date, supported date string or pandas.Timestamp. No missing trading days are fabricated. Default: None.
    calendar (str): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'auto'.
    update (bool): See the function signature and related source validation for the accepted structure. Default: True.
    store (bool | None): True/False override of local persistence, or None to use the current configuration. Default: None.
    on_error (str): Allowed: "collect" (record item failures and preserve successful rows) or "raise" (stop and raise). Defaults differ between individual APIs; see Signature. Default: 'collect'.
    checkpoint_dir (str | Path | None): Directory for resumable batch checkpoint state; does not replace the persistent market database. Default: None.
    resume (bool): Continue from an existing valid checkpoint where supported; does not guarantee every record is fresh. Default: True.
    resume_max_age (float): See the function signature and related source validation for the accepted structure. Default: 3600.0.
    include_jdate (bool): True adds a Jalali date column; False does not. This does not convert the underlying Gregorian date column. Default: False.
    progress (Any): Optional callback for batch progress notifications. Default: None.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    BatchFrames: See the API reference for columns, metadata and error reporting.

Notes:
    Ordered data job with reports and opt-in disk checkpoints. Uses existing bounded network budget; partial success is explicit."""
    if store is not None and store != get_config().storage.enabled:
        with Client(config=get_config(),storage=store) as client:
            return client.download(symbols=symbols, dataset=dataset, start=start, end=end, calendar=calendar, update=update, on_error=on_error, checkpoint_dir=checkpoint_dir, resume=resume, resume_max_age=resume_max_age, include_jdate=include_jdate, progress=progress, policy=policy)
    return _client().download(symbols=symbols, dataset=dataset, start=start, end=end, calendar=calendar, update=update, store=store, on_error=on_error, checkpoint_dir=checkpoint_dir, resume=resume, resume_max_age=resume_max_age, include_jdate=include_jdate, progress=progress, policy=policy)

def update(symbols, *, start: DateLike | None=None, end: DateLike | None=None, calendar: str='auto', on_error: str='collect', checkpoint_dir: str | Path | None=None, resume: bool=False, progress=None) -> BatchFrames:
    """Update raw histories with overlap/correction handling. Default resume=False checks anew rather than reusing a job snapshot.

Args:
    symbols (Any): Ordered collection of symbol references to download; independent symbols do not need common characters.
    start (DateLike | None): Inclusive starting date or None: date, supported date string or pandas.Timestamp. Use calendar for string interpretation. Default: None.
    end (DateLike | None): Inclusive ending date or None: date, supported date string or pandas.Timestamp. No missing trading days are fabricated. Default: None.
    calendar (str): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'auto'.
    on_error (str): Allowed: "collect" (record item failures and preserve successful rows) or "raise" (stop and raise). Defaults differ between individual APIs; see Signature. Default: 'collect'.
    checkpoint_dir (str | Path | None): Directory for resumable batch checkpoint state; does not replace the persistent market database. Default: None.
    resume (bool): Continue from an existing valid checkpoint where supported; does not guarantee every record is fresh. Default: False.
    progress (Any): Optional callback for batch progress notifications. Default: None.

Returns:
    BatchFrames: See the API reference for columns, metadata and error reporting.

Notes:
    Update raw histories with overlap/correction handling. Default resume=False checks anew rather than reusing a job snapshot."""
    return _client().update(symbols=symbols, start=start, end=end, calendar=calendar, on_error=on_error, checkpoint_dir=checkpoint_dir, resume=resume, progress=progress)

def download_market(*, dataset: str='history', market: Market | str | None=None, limit: int=100, start: DateLike | None=None, end: DateLike | None=None, calendar: str='auto', dry_run: bool=True, on_error: str='collect', checkpoint_dir: str | Path | None=None) -> pd.DataFrame | BatchFrames:
    """Plan bounded downloads for the current watch universe. dry_run=True performs only watch retrieval; historical universe is not reconstructed.

Args:
    dataset (str): Dataset family, such as "history", accepted by the specific API. See catalog/capabilities for supported data. Default: 'history'.
    market (Market | str | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: None.
    limit (int): Maximum returned/displayed matches; None retains all eligible rows. Not necessarily remote pagination. Default: 100.
    start (DateLike | None): Inclusive starting date or None: date, supported date string or pandas.Timestamp. Use calendar for string interpretation. Default: None.
    end (DateLike | None): Inclusive ending date or None: date, supported date string or pandas.Timestamp. No missing trading days are fabricated. Default: None.
    calendar (str): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'auto'.
    dry_run (bool): See the function signature and related source validation for the accepted structure. Default: True.
    on_error (str): Allowed: "collect" (record item failures and preserve successful rows) or "raise" (stop and raise). Defaults differ between individual APIs; see Signature. Default: 'collect'.
    checkpoint_dir (str | Path | None): Directory for resumable batch checkpoint state; does not replace the persistent market database. Default: None.

Returns:
    pd.DataFrame | BatchFrames: See the API reference for columns, metadata and error reporting.

Notes:
    Plan bounded downloads for the current watch universe. dry_run=True performs only watch retrieval; historical universe is not reconstructed."""
    return _client().download_market(dataset=dataset, market=market, limit=limit, start=start, end=end, calendar=calendar, dry_run=dry_run, on_error=on_error, checkpoint_dir=checkpoint_dir)


download_many = download

from .reference import examples, help, columns


def get_trades_many(instruments, *, start, end=None, calendar='gregorian', include_jdate=False, on_error='collect', policy=None) -> BatchFrames:
    """Trades for multiple inputs with explicit errors, not silent dropping.

Args:
    instruments (Any): Sequence of instrument references, pandas Series/Index, or one-dimensional NumPy array. See batch report for partial errors.
    start (Any): Inclusive starting date or None: date, supported date string or pandas.Timestamp. Use calendar for string interpretation.
    end (Any): Inclusive ending date or None: date, supported date string or pandas.Timestamp. No missing trading days are fabricated. Default: None.
    calendar (Any): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'gregorian'.
    include_jdate (Any): True adds a Jalali date column; False does not. This does not convert the underlying Gregorian date column. Default: False.
    on_error (Any): Allowed: "collect" (record item failures and preserve successful rows) or "raise" (stop and raise). Defaults differ between individual APIs; see Signature. Default: 'collect'.
    policy (Any): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    BatchFrames: See the API reference for columns, metadata and error reporting.

Notes:
    Trades for multiple inputs with explicit errors, not silent dropping."""
    return _client().get_trades_many(instruments,start=start,end=end,calendar=calendar,include_jdate=include_jdate,on_error=on_error,policy=policy)


def get_order_book_updates(instrument, *, start, end=None, calendar='gregorian', include_jdate=False, max_days=31, policy=None) -> pd.DataFrame:
    """Historical best-limit updates, not full snapshots.

Args:
    instrument (Any): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    start (Any): Inclusive starting date or None: date, supported date string or pandas.Timestamp. Use calendar for string interpretation.
    end (Any): Inclusive ending date or None: date, supported date string or pandas.Timestamp. No missing trading days are fabricated. Default: None.
    calendar (Any): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'gregorian'.
    include_jdate (Any): True adds a Jalali date column; False does not. This does not convert the underlying Gregorian date column. Default: False.
    max_days (Any): See the function signature and related source validation for the accepted structure. Default: 31.
    policy (Any): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Historical best-limit updates, not full snapshots."""
    return _client().get_order_book_updates(instrument,start=start,end=end,calendar=calendar,include_jdate=include_jdate,max_days=max_days,policy=policy)

__all__ += ['get_adjustments', 'get_share_capital_history', 'get_dividends', 'get_adjusted_history', 'get_shareholders', 'get_shareholder_history', 'get_disclosures', 'get_messages', 'get_trades', 'get_order_book', 'get_order_book_history', 'get_instrument_states', 'get_thresholds', 'get_boards', 'get_instruments', 'get_funds', 'get_fund', 'get_fund_nav_history', 'get_options', 'get_futures', 'history', 'market', 'index_history', 'datasets', 'storage_info', 'query', 'backup', 'download', 'update', 'download_market', 'get_trades_many', 'get_order_book_updates', 'export', 'export_many', 'download_many', 'setup', 'check_connection', 'diagnose', 'to_pandas', 'set_date_index', 'select', 'concat', 'coverage', 'missing_sessions', 'compare_sources', 'examples', 'help', 'columns']


# Short and descriptive instrument lookup facade.
def _legacy_instrument(*, ins_code=None, instrument_id=None, company_cisin=None, symbol=None,
               raw_symbol=None, name=None, market=None, raw_flow=None,
               instrument_type=None, currency=None, is_active=None, strict=True,
               on_multiple="all", on_conflict="error", policy=None) -> pd.DataFrame:
    """Return all matching instruments by default, with explicit multiplicity and conflict policies.

Args:
    ins_code (Any): One positive exchange instrument code as str/int, or an ordered list of codes for instrument(), history() and price(). Codes are identifiers, not company tickers. Default: None.
    instrument_id (Any): Exchange instrument identifier distinct from ins_code. Default: None.
    company_cisin (Any): Company C-ISIN identifier, distinct from instrument code. Default: None.
    symbol (Any): Trading symbol text (e.g. "فولاد"); history() also accepts this named criterion. Multiple matching records are governed by on_multiple. Default: None.
    raw_symbol (Any): Unnormalized symbol exactly as supplied by the provider. Default: None.
    name (Any): Company/instrument display name criterion; not necessarily the trading symbol. Default: None.
    market (Any): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: None.
    raw_flow (Any): Provider-reported raw market-flow classification. Default: None.
    instrument_type (Any): Instrument classification filter; use values found in the returned catalog. Default: None.
    currency (Any): Reported currency code filter; no currency conversion is performed. Default: None.
    is_active (Any): Boolean or None: filter by reported activity state; activity is not the same as the latest trading-session state. Default: None.
    strict (Any): Boolean: require strict matching in instrument identity resolution, rather than relaxed matching. Default: True.
    on_multiple (Any): Allowed: "all" (default: keep every match), "first" (choose one in stable source order), "error" (raise on multiple matches). Applies to identity resolution, not HTTP errors. Default: 'all'.
    on_conflict (Any): Allowed: "error" (default: reject conflicting identity criteria), "ins_code" (trust explicit ins_code when other filters conflict; requires ins_code). Default: 'error'.
    policy (Any): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: Output is a pandas.DataFrame; ins_code identifies an exchange instrument. No historical identity reconstruction is implied. Multiple values in ins_code are de-duplicated by the resolver.

Raises:
    InvalidArgumentError: Unsupported or inconsistent input or policy value.
    AmbiguousInstrumentError: Ambiguous identity when on_multiple="error".
    PyDaraError: Data acquisition, network, offline or validation errors as applicable.

Notes:
    Output is a pandas.DataFrame; ins_code identifies an exchange instrument. No historical identity reconstruction is implied. Multiple values in ins_code are de-duplicated by the resolver.

Examples:
    >>> from pydara import tse
    >>> found = tse.assets(ins_code=["46348559193224090"], on_multiple="all")
    >>> found.columns.tolist()  # inspect the returned schema"""
    return _client().instrument(ins_code=ins_code, instrument_id=instrument_id,
        company_cisin=company_cisin, symbol=symbol, raw_symbol=raw_symbol, name=name,
        market=market, raw_flow=raw_flow, instrument_type=instrument_type,
        currency=currency, is_active=is_active, strict=strict,
        on_multiple=on_multiple, on_conflict=on_conflict, policy=policy)


def _legacy_resolve_instrument(**kwargs) -> pd.DataFrame:
    """Descriptive alias for instrument().

Args:
    kwargs (Any): See the function signature and related source validation for the accepted structure.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Descriptive alias for instrument()."""
    return assets(**kwargs)


def search(query: str, *, market: Market | None=None, include_inactive: bool=True,
           limit: int | None=None, policy=None) -> pd.DataFrame:
    """Short alias for search_instruments().

Args:
    query (str): Search expression. A query is not a unique identifier and may match many results.
    market (Market | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: None.
    include_inactive (bool): Whether to include instruments without a reported active status. Default: True.
    limit (int | None): Maximum returned/displayed matches; None retains all eligible rows. Not necessarily remote pagination. Default: None.
    policy (Any): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Short alias for search_instruments()."""
    return search_instruments(query, market=market, include_inactive=include_inactive,
                              limit=limit, policy=policy)


def catalog(*, market: Market | str | None=None, include_inactive: bool=False,
            changed_since: DateLike | None=None, backend: str='auto', policy=None) -> pd.DataFrame:
    """Short alias for get_instruments(); current watch coverage limitations remain.

Args:
    market (Market | str | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: None.
    include_inactive (bool): Whether to include instruments without a reported active status. Default: False.
    changed_since (DateLike | None): See the function signature and related source validation for the accepted structure. Default: None.
    backend (str): Allowed "auto", "json", "legacy" where supported; auto fallback is conditional rather than a generic retry on every error. Default: 'auto'.
    policy (Any): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Short alias for get_instruments(); current watch coverage limitations remain."""
    return get_instruments(market=market, include_inactive=include_inactive,
        changed_since=changed_since, backend=backend, policy=policy)

__all__ += ['instrument', 'resolve_instrument', 'search', 'catalog']

__all__ += ["price"]


def _legacy_clients(instrument=None, *, ins_code=None, start=None, end=None, day=None,
            calendar='auto', include_jdate=False, on_multiple='all',
            on_conflict='error', on_error='collect', policy=None) -> pd.DataFrame:
    """Receive individual/institutional buying and selling for one or many instruments.

    Args:
        instrument (DataFrame | str | list[str] | InstrumentRef | None): A DataFrame from
            ``tse.assets()`` (one or multiple rows), a trading symbol or a sequence
            of symbols. Do not combine with ``ins_code``.
        ins_code (str | int | list[str | int] | None): One exchange instrument code or
            a one-dimensional sequence of codes. Duplicate codes are requested once.
        start, end (date | str | None): Inclusive date range for historical data.
            With neither specified, fetch the latest available observation.
        day (date | str | None): A single session; cannot be combined with start/end.
        calendar (Literal['auto', 'jalali', 'gregorian']): Interpretation of date text.
        include_jdate (bool): Include the Jalali date as ``jdate`` when True.
        on_multiple (Literal['all', 'first', 'error']): How ambiguous symbol matches
            are resolved. Default is ``all``.
        on_conflict (Literal['error', 'ins_code']): How inconsistent identity filters
            are resolved. Default is ``error``; explicit codes can take precedence.
        on_error (Literal['collect', 'raise']): Collect per-instrument errors (default)
            or stop on the first failed request.
        policy (FetchPolicy | str | None): Existing online/offline/cache policy.

    Returns:
        pandas.DataFrame: One merged table, one row per instrument and observation
            date. Public column names contain no underscores; ``inscode``,
            ``symbol`` and ``date`` identify observations. ``ibuycount``,
            ``isellcount``, ``lbuycount``, ``lsellcount`` are buyer/seller counts;
            corresponding ``*volume`` and ``*value`` fields report source volumes
            and values. ``buydddcount`` and ``buydddvolume`` retain DDD fields
            **without** treating them as individual/institutional metrics. Missing
            observations remain missing. ``df.attrs['pydara']['errors']`` and
            ``['requests']`` describe partial batch results. Column renaming applies
            only to this public output, not to cache/SQLite storage schemas.

    Raises:
        InvalidArgumentError: Unsupported selector or conflicting date criteria.
        PyDaraError: A failed request when ``on_error='raise'``.

    Examples:
        >>> from pydara import tse
        >>> selected = tse.assets(symbol='فولاد')
        >>> frame = tse.traders(selected, start='1403-01-01', end='1403-12-29')
        >>> frame = tse.traders(ins_code=['46348559193224090'], day='1403-01-05')

    Notes:
        Latest means the latest observation returned by the chosen source, not
        necessarily a currently trading session. A historical range may require
        downloading the full available source history before local date filtering.
        No live exchange validation is implied by offline fixture tests.
    """
    return _client().clients(instrument, ins_code=ins_code, start=start, end=end, day=day,
        calendar=calendar, include_jdate=include_jdate, on_multiple=on_multiple,
        on_conflict=on_conflict, on_error=on_error, policy=policy)

__all__ += ['clients']


# Public API 0.7.0. Storage names and provider contracts remain unchanged.
def _normalize_assets(value):
    """Translate the one-word public asset identifier column to the storage schema."""
    if isinstance(value, pd.DataFrame) and 'inscode' in value.columns:
        return value.rename(columns={'inscode': 'ins_code'})
    return value


def _public_frame(frame):
    """Present one-word public columns without modifying cache or SQLite schemas."""
    out = frame.rename(columns={c: c.replace('_', '') for c in frame.columns})
    out.attrs.update(frame.attrs)
    return out


def assets(selector=None, *, ins_code=None, instrument_id=None, company_cisin=None, symbol=None,
           raw_symbol=None, name=None, markets=None, raw_flow=None,
           instrument_type=None, currency=None, is_active=None,
           industry=None, industry_code=None, strict=True,
           on_multiple='all', on_conflict='error', policy=None) -> pd.DataFrame:
    """List or resolve exchange assets, optionally applying source-supported filters.

    Args:
        selector (str | int | None): Optional positional symbol or numeric ins_code.
            ``assets("فولاد")`` is the same as ``assets(symbol="فولاد")``.
            Numeric identifiers are interpreted as ins_code, never as symbols.
            Do not combine with symbol or ins_code unless on_conflict="ins_code"
            is selected for an explicit code selector.
        ins_code (str | int | list[str | int] | None): Explicit instrument identifiers.
        instrument_id (str | None): Source instrument identifier, distinct from ins_code.
        company_cisin (str | None): Company-level source identifier.
        symbol (str | list[str] | None): Exact trading symbol or one-dimensional sequence of symbols; None lists observed assets.
        name (str | None): Exact instrument name when searching.
        raw_symbol (str | None): Source-reported unnormalized symbol.
        markets (str | list[str] | DataFrame | None): Selected markets or a
            DataFrame returned by tse.markets(); None means all observed markets.
        raw_flow (str | None): Source-specific trading market flow code.
        instrument_type (str | None): Provider's instrument classification.
        currency (str | None): Source-reported currency code.
        is_active (bool | None): Reported identity activity status, not trade state.
        industry (str | None): Sector name as returned by ``get_sectors()``.
        industry_code (str | None): Exact sector code from ``get_sectors()``.
        strict (bool): Require identity filters to match verified data.
        on_multiple (Literal['all', 'first', 'error']): Match cardinality policy.
        on_conflict (Literal['error', 'ins_code']): Conflicting identity policy.
        policy (FetchPolicy | str | None): Online/cache/offline selection.

    Returns:
        pandas.DataFrame: One row per observed instrument, with single-word
        column names such as ``inscode``, ``symbol``, ``isactive``. The
        no-identifier result covers the CURRENT OBSERVED market watch only;
        it is NOT a complete historical exchange registry. Rows with missing
        metadata are not silently claimed to match a requested filter.

    Raises:
        InvalidArgumentError: Invalid or unsupported criteria.
        PyDaraError: Data-source, cache, offline and validation failures.

    Examples:
        >>> from pydara import tse
        >>> table = tse.assets(markets='TSE')
        >>> chosen = tse.assets(ins_code=['46348559193224090'])
        >>> by_symbol = tse.assets("فولاد")
        >>> active = tse.assets(markets=tse.markets(), is_active=True)
        >>> group = tse.assets(markets='TSE', symbol=['فولاد', 'وبملت'])

    Notes:
        For TSE/IFB a source-filtered watch request is made. When the source
        omits the market label, membership comes from its requested market
        filter and is marked in quality_flags and the pydara metadata;
        contradictory provider responses raise an error. Unclassified rows
        from sources without a server filter are excluded. See
        ``result.attrs['pydara']['unknown_market_rows_excluded']`` and
        ``market_filter_incomplete`` for coverage limitations. Unfiltered
        lookups retain rows with missing market labels. This is the observed
        watch, not a complete historical instrument registry.
    """
    from .instrument_lookup import lookup_policies
    from ._core.exceptions import (InvalidArgumentError, UnsupportedCapabilityError,
                                   OfflineDataUnavailableError)
    if selector is not None:
        from .instrument_lookup import normalize_ins_codes
        if isinstance(selector, bool) or not isinstance(selector, (str, int)) or not str(selector).strip():
            raise InvalidArgumentError('Positional assets selector must be a symbol or ins_code.')
        is_code = isinstance(selector, int) or (isinstance(selector, str) and selector.isascii() and selector.isdecimal())
        if is_code:
            selector_code = normalize_ins_codes(selector)[0]
            if ins_code is not None or symbol is not None:
                if on_conflict != 'ins_code':
                    raise InvalidArgumentError('Positional selector conflicts with symbol/ins_code; provide one locator.')
                # Explicit keyword ins_code wins under the existing ins_code policy.
                if ins_code is None:
                    ins_code = selector_code
            else:
                ins_code = selector_code
        else:
            if symbol is not None or ins_code is not None:
                raise InvalidArgumentError('Positional symbol cannot be combined with symbol/ins_code.')
            symbol = selector
    lookup_policies(on_multiple, on_conflict, has_ins_code=ins_code is not None)
    from .public_workflows import markets_filter
    selection = markets_filter(markets, allow_base=True)
    # Selection is applied locally to verified labels in observed watch rows.
    source_market = selection[0] if selection and len(selection) == 1 else None
    if symbol is not None:
        from ._core.exceptions import InvalidArgumentError
        if isinstance(symbol, str):
            if not symbol.strip():
                raise InvalidArgumentError('symbol must not be empty.')
        elif isinstance(symbol, (list, tuple, pd.Series, pd.Index)):
            if not len(symbol) or any(not isinstance(x, str) or not x.strip() for x in symbol):
                raise InvalidArgumentError('symbol values must be nonempty strings.')
            symbol = list(dict.fromkeys(symbol))
        else:
            raise InvalidArgumentError('symbol must be a nonempty string or list of strings.')
    if industry is not None and (not isinstance(industry, str) or not industry.strip()):
        raise InvalidArgumentError('industry must be a nonempty sector name.')
    if industry_code is not None and (not isinstance(industry_code, str) or not industry_code.strip()):
        raise InvalidArgumentError('industry_code must be a nonempty sector code.')
    identity = (ins_code, symbol, raw_symbol, name)
    no_locator = all(x is None for x in identity)
    if no_locator:
        # Prefer one source-filtered watch per selected market. The source query
        # carries market membership even when individual JSON rows omit `flow`.
        # Unselected calls preserve all observed rows, including unknown markets.
        if selection is None:
            frame = _client().get_instruments(market=None, policy=policy)
        else:
            parts = []
            for code in selection:
                try:
                    part = _client().get_instruments(
                        market=code if code in ('TSE', 'IFB') else None,
                        policy=policy)
                except UnsupportedCapabilityError as exc:
                    if 'does not identify each row market' not in str(exc):
                        raise
                    # Compatibility for providers that reject the filtered
                    # endpoint; legacy data must still verify each row market.
                    part = _client().get_instruments(
                        market=None, backend='legacy', policy=policy)
                except OfflineDataUnavailableError:
                    # Older offline caches may contain only the unfiltered URL.
                    # Reuse its VERIFIED row labels; do not infer a market from
                    # the requested code when this request was not fetched.
                    part = _client().get_instruments(market=None, policy=policy)
                if code == 'BASE':
                    part = part.loc[part['market'].astype('string').eq('BASE').fillna(False)].copy()
                parts.append(part)
            if len(parts) == 1:
                frame = parts[0]
            else:
                frame = pd.concat(parts, ignore_index=True).drop_duplicates('ins_code', keep='first')
                components = [deepcopy(part.attrs.get('pydara', {})) for part in parts]
                frame.attrs['pydara'] = {
                    'schema_id': 'observed_instruments',
                    'components': components,
                    'requested_markets': list(selection),
                    'market_selection_basis': 'separate_source_requests',
                    'market_labels_from_server_selector': sum(
                        int(m.get('market_labels_from_server_selector', 0)) for m in components),
                    'unknown_market_rows_excluded': sum(
                        int(m.get('unknown_market_rows_excluded', 0)) for m in components),
                    'coverage_status': 'unknown',
                }
        # Never silently invent unavailable source metadata.
        for key, value in [('instrument_id',instrument_id),('company_cisin',company_cisin),
                           ('raw_flow',raw_flow),('instrument_type',instrument_type),
                           ('currency',currency),('is_active',is_active)]:
            if value is not None:
                if key not in frame.columns:
                    if key == 'is_active':
                        from ._core.models import InstrumentRef
                        from ._core.exceptions import UnknownInstrumentError
                        statuses = []
                        for code in frame['ins_code']:
                            record = _client()._resolve_instrument_record(
                                InstrumentRef.by_ins_code(str(code)), policy=policy)
                            statuses.append(record.is_active)
                        frame = frame.copy()
                        frame['is_active'] = pd.Series(statuses, index=frame.index, dtype='boolean')
                    else:
                        raise UnsupportedCapabilityError(f'Watch catalog cannot verify {key}.')
                frame = frame.loc[frame[key].notna() & (frame[key] == value)]
    else:
        if isinstance(symbol, list):
            frames = [
                _legacy_instrument(ins_code=ins_code, instrument_id=instrument_id,
                    company_cisin=company_cisin, symbol=sym, raw_symbol=raw_symbol,
                    name=name, market=source_market, raw_flow=raw_flow,
                    instrument_type=instrument_type, currency=currency,
                    is_active=is_active, strict=strict, on_multiple=on_multiple,
                    on_conflict=on_conflict, policy=policy)
                for sym in symbol
            ]
            frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
            if 'ins_code' in frame:
                frame = frame.drop_duplicates(subset=['ins_code'], keep='first')
        else:
            frame = _legacy_instrument(ins_code=ins_code, instrument_id=instrument_id,
                company_cisin=company_cisin, symbol=symbol, raw_symbol=raw_symbol,
                name=name, market=source_market, raw_flow=raw_flow,
                instrument_type=instrument_type, currency=currency,
                is_active=is_active, strict=strict, on_multiple=on_multiple,
                on_conflict=on_conflict, policy=policy)
    if selection is not None:
        if 'market' not in frame.columns:
            raise UnsupportedCapabilityError('Asset source has no market column; market selection cannot be verified.')
        # Missing labels are excluded only when a market filter is requested.
        # Report how many were excluded; do not invent missing classifications.
        # Low-level market-watch filtering may already have excluded unknowns.
        # Preserve that count instead of accidentally reporting zero here.
        previous_missing = int(frame.attrs.get('pydara', {}).get('unknown_market_rows_excluded', 0))
        missing_market = int(frame['market'].isna().sum()) + previous_missing
        frame_attrs = deepcopy(frame.attrs)
        frame = frame.loc[frame['market'].notna() & frame['market'].astype(str).isin(selection)].copy()
        frame.attrs = frame_attrs
        frame.attrs.setdefault('pydara', {}).update(
            unknown_market_rows_excluded=missing_market,
            market_filter_incomplete=bool(missing_market),
            requested_markets=list(selection),
        )
    if industry is not None or industry_code is not None:
        from ._core.exceptions import UnsupportedCapabilityError
        if 'sector_code' not in frame:
            raise UnsupportedCapabilityError('Asset data does not contain verified sector_code.')
        if industry is not None:
            sectors = _client().get_sectors(policy=policy)
            codecol = next((c for c in ('sector_code', 'code') if c in sectors), None)
            namecol = next((c for c in ('sector_name', 'name') if c in sectors), None)
            if codecol is None or namecol is None:
                raise UnsupportedCapabilityError('Sector names and codes are unavailable from this source.')
            matched = sectors.loc[sectors[namecol] == industry]
            if industry_code is not None:
                matched = matched.loc[matched[codecol].astype(str) == industry_code]
            codes = set(matched[codecol].dropna().astype(str))
        else:
            codes = {industry_code}
        frame = frame.loc[frame['sector_code'].astype(str).isin(codes)]
    if no_locator:
        if on_multiple == 'error' and len(frame)>1:
            from ._core.exceptions import AmbiguousInstrumentError
            raise AmbiguousInstrumentError('Multiple assets match the requested filters.')
        if on_multiple == 'first':frame=frame.head(1)
    out=_public_frame(frame.copy())
    out.attrs.setdefault('pydara',{})['coverage_note']='Current observed watch only; not a complete historical instrument registry.' if no_locator else 'Identity lookup; historical completeness not guaranteed.'
    return out


def _prices_preserve_asset_market(result: pd.DataFrame, assets) -> pd.DataFrame:
    """Enrich quote market only from a verified input asset identity.

    Provider market wins when present. Conflicting non-missing labels remain
    unchanged and are reported in attrs, never silently overwritten.
    """
    if not isinstance(assets, pd.DataFrame) or 'inscode' not in assets or 'market' not in assets or 'inscode' not in result:
        return result
    source = assets[['inscode', 'market']].dropna(subset=['inscode']).copy()
    source['inscode'] = source['inscode'].astype(str)
    source = source.dropna(subset=['market'])
    conflicts_in_input = source.groupby('inscode')['market'].nunique(dropna=True)
    ambiguous = set(conflicts_in_input[conflicts_in_input > 1].index)
    source = source.loc[~source['inscode'].isin(ambiguous)].drop_duplicates('inscode')
    labels = source.set_index('inscode')['market']
    output = result.copy()
    if 'market' not in output:
        output['market'] = pd.Series([pd.NA] * len(output), index=output.index, dtype='string')
    incoming = output['inscode'].astype(str).map(labels)
    previous = output['market']
    conflicts = previous.notna() & incoming.notna() & previous.astype('string').ne(incoming.astype('string')).fillna(False)
    unknown = previous.isna() & incoming.notna()
    output.loc[unknown, 'market'] = incoming.loc[unknown]
    output.attrs = deepcopy(result.attrs)
    meta = output.attrs.setdefault('pydara', {})
    meta['asset_market_filled'] = int(unknown.sum())
    meta['asset_market_conflicts'] = int(conflicts.sum())
    meta['asset_market_ambiguous_inputs'] = len(ambiguous)
    meta['asset_market_basis'] = 'input_assets_inscode_match_only'
    return output


def _valid_bulk_quote_rows(frame: pd.DataFrame) -> pd.Series:
    """Identify observed quotes with a positive close and a valid trade date.

    Zero quotes and unknown trade dates are not evidence of a completed price
    observation, even when their instrument identifier occurs in the watch.
    """
    close = pd.to_numeric(frame.get('closingprice', pd.Series(pd.NA, index=frame.index)), errors='coerce')
    dates = pd.to_datetime(frame.get('date', pd.Series(pd.NaT, index=frame.index)), errors='coerce')
    return (close.gt(0) & dates.notna()).fillna(False).astype(bool)


def prices(assets=None, *, ins_code=None, markets=None, include_queues=True,
           max_quote_fallback=20, on_multiple='all', on_conflict='error', on_error='collect',
           freshness=None, policy=None) -> pd.DataFrame:
    """Receive latest daily quotes and price returns as a one-word-column DataFrame.

    Args:
        assets (DataFrame | str | list[str] | None): Table returned by
            ``tse.assets()`` or one/many symbol selectors. Large DataFrames
            use a single bulk market-watch request, falling back to specific
            quotes for instruments missing from the snapshot. With None and no
            ``ins_code``, bulk-fetch the observed market watch.
        ins_code (str | int | list[str | int] | None): One or more explicit codes.
        markets (str | list[str] | DataFrame | None): Market codes or ``markets()``
            DataFrame, ONLY when querying the bulk watch (no assets/ins_code).
        include_queues (bool): Include observable best-limit buy/sell queues
            when price limits and both order-book sides are explicitly reported.
            Unknown is NA, not zero. Default: True.
        max_quote_fallback (int): Maximum individual requests used to repair
            incomplete/missing bulk-watch rows per call. Default 20; zero disables
            repair. Raise explicitly for a larger batch. Does not bypass the
            client's network budget or service rate limits.
        on_multiple (Literal['all','first','error']): Identity policy.
        on_conflict (Literal['error','ins_code']): Identity conflict policy.
        on_error (Literal['collect','raise']): Per-asset error handling. The
            no-selector bulk watch is one source request and propagates errors.
        freshness (FreshnessPolicy | None): Age tolerance for individual quotes.
        policy (FetchPolicy | str | None): Fresh/cache/offline data policy.

    Returns:
        pandas.DataFrame: One row per reported instrument. Includes one-word
            source fields, ``change`` (price difference), ``return`` (fractional
            close/reference price return) and ``returnpct`` (percentage, 100*
            return). For example 0.02 and 2.0 mean a 2% daily price return.
            Missing/nonpositive closing or reference prices yield NA. Unadjusted price return
            does NOT include dividends or guarantee total return. ``fetchedat``
            is retrieval time, NOT proof of live trading. ``buyqueue`` and
            ``sellqueue`` are confirmed observable volumes or NA. For per-asset
            quotes, optional queue data come from a separate non-atomic watch.
            Provenance/errors are in ``df.attrs['pydara']``.

    Raises:
        InvalidArgumentError: Inconsistent or invalid selectors.
        PyDaraError: Provider, validation, cache or offline failures.

    Examples:
        >>> from pydara import tse
        >>> all_prices = tse.prices(markets=tse.markets())
        >>> selected = tse.assets(ins_code=['46348559193224090'])
        >>> result = tse.prices(assets=selected)
        >>> result[['symbol','change','return','returnpct']]
    """
    from .public_workflows import quote_watch, enrich_quotes, returns
    from ._core.exceptions import InvalidArgumentError
    if not isinstance(include_queues, bool):
        raise InvalidArgumentError('include_queues must be bool.')
    if isinstance(max_quote_fallback, bool) or not isinstance(max_quote_fallback, int) or max_quote_fallback < 0:
        raise InvalidArgumentError('max_quote_fallback must be a nonnegative integer.')
    if on_error not in ('collect', 'raise'):
        raise InvalidArgumentError('on_error must be collect or raise.')
    from .instrument_lookup import lookup_policies
    lookup_policies(on_multiple, on_conflict, has_ins_code=ins_code is not None)
    if assets is None and ins_code is None:
        return quote_watch(_client(), markets=markets, include_queues=include_queues,
            policy=policy, on_error=on_error)
    if markets is not None:
        raise InvalidArgumentError('markets is only for prices() without assets/ins_code; filter assets first.')
    # Bulk selection: a large assets() DataFrame is best served by one current
    # market-watch request, not hundreds of sequential per-instrument HTTP calls.
    # Skip when explicit freshness control is supplied, preserving that contract.
    if (isinstance(assets, pd.DataFrame) and ins_code is None
            and freshness is None and len(assets) >= 20
            and 'inscode' in assets.columns):
        from ._core.exceptions import InvalidArgumentError
        from .instrument_lookup import normalize_ins_codes
        from .public_workflows import quote_watch
        requested = normalize_ins_codes(assets['inscode'].tolist())
        try:
            watch = quote_watch(_client(), include_queues=include_queues,
                                policy=policy, on_error=on_error)
        except Exception:
            # A failed bulk watch must not disable the established per-asset
            # quote path, especially when an explicit stale/offline policy applies.
            watch = None
        if watch is not None:
            matched = watch.loc[watch['inscode'].astype(str).isin(requested)].copy()
            matched['inscode'] = matched['inscode'].astype(str)
            # A row with a known identifier but no trade date or usable close
            # is *not* a usable quote, especially in holiday watch snapshots.
            valid = _valid_bulk_quote_rows(matched)
            valid_codes = set(matched.loc[valid, 'inscode'])
            repair_candidates = [code for code in requested if code not in valid_codes]
            repair_codes = repair_candidates[:max_quote_fallback]
            fallback_meta = None
            repaired = set()
            repair_errors = []
            if repair_codes:
                try:
                    extra = _public_frame(_legacy_price(None, ins_code=repair_codes,
                        on_multiple=on_multiple, on_conflict=on_conflict,
                        on_error=on_error, freshness=freshness, policy=policy))
                    fallback_meta = deepcopy(extra.attrs.get('pydara', {}))
                    if not extra.empty:
                        extra['inscode'] = extra['inscode'].astype(str)
                        good = _valid_bulk_quote_rows(extra)
                        extra = extra.loc[good].drop_duplicates('inscode', keep='first').copy()
                        repaired = set(extra['inscode'])
                        if include_queues:
                            extra = enrich_quotes(extra, watch, include_queues=True)
                        else:
                            extra = returns(extra)
                        matched = pd.concat([matched.loc[~matched['inscode'].isin(repaired)], extra], ignore_index=True)
                except Exception as exc:
                    if on_error == 'raise':
                        raise
                    repair_errors.append({'component': 'individual_quote_repair',
                                          'error': type(exc).__name__, 'message': str(exc)})
            # Preserve incomplete watch rows for audit, but never invent a quote.
            # A missing identifier remains explicitly unmatched.
            position = {code: i for i, code in enumerate(requested)}
            matched = matched.loc[matched['inscode'].isin(position)].copy()
            matched['_position'] = matched['inscode'].map(position)
            matched = matched.sort_values('_position', kind='stable').drop(columns=['_position'])
            matched = matched.drop_duplicates('inscode', keep='first').reset_index(drop=True)
            # Keep NA return fields for incomplete watch rows.
            valid_final = _valid_bulk_quote_rows(matched)
            for col in ('change', 'return', 'returnpct'):
                if col in matched:
                    matched.loc[~valid_final, col] = pd.NA
            matched.attrs['pydara'] = deepcopy(watch.attrs.get('pydara', {}))
            unresolved = [code for code in repair_candidates if code not in repaired]
            matched.attrs['pydara'].update(selection='bulk_watch_then_validated_quote_repair',
                requested_assets=len(requested), returned_assets=len(matched),
                valid_bulk_quotes=len(valid_codes), repair_candidates=len(repair_candidates),
                repair_attempted=len(repair_codes), repair_succeeded=len(repaired),
                repair_limit=max_quote_fallback, repair_deferred=repair_candidates[len(repair_codes):],
                unresolved_quotes=unresolved, repair_errors=repair_errors,
                incomplete_quote_rows=int((~valid_final).sum()),
                unmatched_assets=[code for code in requested if code not in set(matched['inscode'])])
            if fallback_meta is not None:
                matched.attrs['pydara']['individual_quote_fallback'] = fallback_meta
            return _prices_preserve_asset_market(matched, assets)
    quotes = _public_frame(_legacy_price(_normalize_assets(assets), ins_code=ins_code,
        on_multiple=on_multiple, on_conflict=on_conflict, on_error=on_error,
        freshness=freshness, policy=policy))
    if include_queues:
        try:
            observed = quote_watch(_client(), include_queues=True, policy=policy,
                on_error=on_error)
        except Exception as exc:
            if on_error == 'raise':
                raise
            quotes.attrs.setdefault('pydara', {}).setdefault('errors', []).append({
                'component': 'market_watch_queues', 'error': type(exc).__name__, 'message': str(exc)})
            return _prices_preserve_asset_market(returns(quotes), assets)
        return _prices_preserve_asset_market(enrich_quotes(quotes, observed, include_queues=True), assets)
    return _prices_preserve_asset_market(returns(quotes), assets)


def traders(assets=None, *, ins_code=None, start=None, end=None, day=None,
            calendar='auto', include_jdate=False, on_multiple='all',
            on_conflict='error', on_error='collect', policy=None) -> pd.DataFrame:
    """Return individual/institutional traders' observed buy/sell activity.

    Args:
        assets (DataFrame | str | list[str] | None): Table returned by ``assets()``.
        ins_code (str | int | list[str | int] | None): One or more instrument codes.
        start, end (date | str | None): Inclusive historical interval.
        day (date | str | None): Single session; exclusive with start and end.
        calendar (Literal['auto','gregorian','jalali']): Date interpretation.
        include_jdate (bool): Also include Jalali dates.
        on_multiple (Literal['all','first','error']): Ambiguity handling.
        on_conflict (Literal['error','ins_code']): Conflict handling.
        on_error (Literal['collect','raise']): Failure handling.
        policy (FetchPolicy | str | None): Online/cache/offline policy.

    Returns:
        pandas.DataFrame: One-word columns for buyer/seller counts, volumes,
        values and dates. DDD fields are retained without reclassification.
        See ``result.attrs['pydara']['errors']`` for partial failures.

    Examples:
        >>> from pydara import tse
        >>> frame = tse.traders(tse.assets(symbol='فولاد'))
    """
    return _public_frame(_legacy_clients(_normalize_assets(assets),ins_code=ins_code,
        start=start,end=end,day=day,calendar=calendar,include_jdate=include_jdate,
        on_multiple=on_multiple,on_conflict=on_conflict,on_error=on_error,policy=policy))

__all__ = list(dict.fromkeys([x for x in __all__ if x not in {
    'instrument','resolve_instrument','price','clients'
}] + ['assets','prices','traders']))


def markets(market=None, *, include_breadth=True, include_queues=True,
            include_traders=True, include_indices=True, on_error='collect',
            policy=None) -> pd.DataFrame:
    """Return one row per supported market with summary and observed breadth.

    Args:
        market (None | str | Market | Sequence[str]): None selects TSE and IFB;
            a code or list selects exchanges with a verified overview source.
        include_breadth (bool): Derive observed positive, negative and unchanged
            counts from closing vs previous-reference prices. Default: True.
        include_queues (bool): Count confirmed observable limit queues; unknown
            queue states are not counted or labeled zero. Default: True.
        include_traders (bool): Aggregate individually bought and sold source
            value by market, with unknown values preserved. Default: True.
        include_indices (bool): Include the source overview's index metrics.
        on_error (Literal['collect','raise']): Preserve successful components or
            raise the first provider failure. Default: 'collect'.
        policy (FetchPolicy | str | None): Network/cache/offline policy.

    Returns:
        pandas.DataFrame: One row per requested market and one-word fields
            ``market``, ``indexvalue``, ``volume``, ``turnover``, ``positive``,
            ``negative``, ``buyqueues``, ``sellqueues``, ``realbuy``, ``realsell``,
            ``netreal``, etc., when actually available. Calculated fields are
            source-dependent and never certified as full-market coverage.
            Per-component errors and independent fetch metadata are available
            at ``df.attrs['pydara']``; responses are NOT simultaneous.

    Examples:
        >>> from pydara import tse
        >>> table = tse.markets()
        >>> selected_assets = tse.assets(markets=table)
    """
    from .public_workflows import market_summary
    return market_summary(_client(), market=market, include_breadth=include_breadth,
        include_queues=include_queues, include_traders=include_traders,
        include_indices=include_indices, on_error=on_error, policy=policy)


def orders(assets=None, *, ins_code=None, markets=None, day=None, start=None,
           end=None, calendar='auto', include_jdate=False, depth=5, side='all',
           max_days=31, on_multiple='all', on_conflict='error',
           on_error='collect', policy=None) -> pd.DataFrame:
    """Fetch reported best bid/ask orders and optional historical updates.

    Args:
        assets (DataFrame | str | list[str] | None): ``tse.assets()`` selection;
            omit for bulk current market watch.
        ins_code (str | int | list[str | int] | None): One or many identifiers.
        markets (str | list[str] | DataFrame | None): Bulk current-market filter,
            or a DataFrame returned by ``tse.markets()``. With selected assets,
            this argument must be omitted.
        day (DateLike | None): A single session (requires specific assets).
        start, end (DateLike | None): Inclusive historical update window. The
            source's available data and time span can be limited.
        calendar (Literal['auto','gregorian','jalali']): Date text calendar.
        include_jdate (bool): Add Jalali dates on historical queries.
        depth (int): Number of best-book levels to keep, 1..5. Default: 5.
        side (Literal['all','buy','sell']): Order side filter. Default: 'all'.
        max_days (int): Maximum historical calendar days, 1..366. Default: 31.
        on_multiple (Literal['all','first','error']): Ambiguous symbol handling.
        on_conflict (Literal['error','ins_code']): Identity conflict handling.
        on_error (Literal['collect','raise']): Per-asset failure policy.
        policy (FetchPolicy | str | None): Fetch/cache/offline policy.

    Returns:
        pandas.DataFrame: One row for each observed instrument, depth and
            buy/sell side, with one-word columns ``inscode``, ``symbol``,
            ``date``, ``side``, ``level``, ``price``, ``volume``, ``count`` and
            timestamps. Historical rows are reported updates, NOT a certified
            complete sequence of full-book snapshots. The source reports at
            most five best-limit depths, not the complete order book.

    Raises:
        InvalidArgumentError: Invalid selectors, dates, level or side.
        PyDaraError: Provider or missing offline data failure.

    Examples:
        >>> from pydara import tse
        >>> book = tse.orders(markets='TSE', depth=5)
        >>> selected = tse.assets(symbol='فولاد')
        >>> updated = tse.orders(assets=selected, depth=3)
    """
    from .public_workflows import books
    return books(_client(), assets=_normalize_assets(assets), ins_code=ins_code,
        markets=markets, day=day, start=start, end=end, calendar=calendar,
        include_jdate=include_jdate, depth=depth, side=side, max_days=max_days,
        on_multiple=on_multiple, on_conflict=on_conflict, on_error=on_error,
        policy=policy)

__all__ = list(dict.fromkeys([*__all__, 'markets', 'orders']))


def trades(assets=None, *, ins_code=None, start=None, end=None,
           starttime='00:00:00', endtime='23:59:59', calendar='auto',
           include_jdate=True, max_days=31, on_multiple='all',
           on_conflict='error', on_error='collect', policy=None,
           maxassets=20, progress=True, workers=1, checkpoint=None) -> pd.DataFrame:
    """Retrieve source-reported execution records in a Tehran-local date/time window.

    Args:
        assets (DataFrame | str | list[str] | None): DataFrame from ``tse.assets()``,
            a symbol or list of symbols. Supply this OR ``ins_code``.
        ins_code (str | int | list[str | int] | None): One or multiple exchange
            instrument codes. Codes are identifiers, not numeric ticker names.
        start (date | str | None): Inclusive first date. Defaults to today in
            Asia/Tehran when both dates are missing; when only ``end`` is given,
            defaults to ``end``. Python date objects are Gregorian.
        end (date | str | None): Inclusive final date. Defaults to today in
            Asia/Tehran when ``start`` is given without ``end``.
        starttime (str | datetime.time): Earliest time of day, inclusive, Tehran
            local time; HH:MM or HH:MM:SS. Default ``'00:00:00'``.
        endtime (str | datetime.time): Latest time of day, inclusive, Tehran
            local time; HH:MM or HH:MM:SS. Default ``'23:59:59'``.
        calendar (Literal['auto', 'jalali', 'gregorian']): Calendar for string dates.
            ``auto`` recognizes 1200..1599 as Jalali and 1800..2199 as Gregorian.
        include_jdate (bool): Include Jalali trading-date column; default True.
        max_days (int): Maximum calendar span of one invocation; 1..366,
            default 31. Large downloads should be split into checkpoints.
        on_multiple (Literal['all', 'first', 'error']): Handling of ambiguous
            symbols. Default ``'all'``.
        on_conflict (Literal['error', 'ins_code']): Identity conflict policy.
            Default ``'error'``.
        on_error (Literal['collect', 'raise']): Continue and record per-instrument
            errors or immediately raise. Default ``'collect'``.
        policy (FetchPolicy | str | None): Fetch/cache/offline policy, including
            ``'auto'``, ``'online'``, and ``'offline'``.
        maxassets (int): Maximum number of selected instruments per call;
            default 20. Set a larger value explicitly for bulk processing.
        progress (bool): Print per-instrument progress to stderr; default True.
        workers (int): Must equal 1. Shared synchronous Client is not safe
            for multithreaded calls; concurrent fetching is not implemented.
        checkpoint (str | Path | None): Optional local directory where successful
            source-backed responses are written as JSON for safe interruption
            and resumption using the same dates and policy. Do not use an
            untrusted or shared directory; partial temp files are ignored.

    Returns:
        pandas.DataFrame: One row per *reported* execution; one-word columns
            ``inscode``, ``symbol``, ``market``, ``date``, ``jdate``, ``time``,
            ``tradeid``, ``sequence``, ``price``, ``quantity``, ``value``,
            ``sourcetimestamp``, ``fetchedat`` and other reported evidence.
            Missing fields remain missing; value is NOT fabricated from price
            and quantity. Request errors and coverage limitations are in
            ``frame.attrs['pydara']``.

    Raises:
        InvalidArgumentError: Invalid selectors, clock, calendar, or range.
        PyDaraError: Source, cache, or transport failure with ``on_error='raise'``.

    Notes:
        Timestamps are filtered using Asia/Tehran local clock; missing source
        timestamps are excluded when a nondefault intraday window is requested.
        Source history is neither a certified complete trade tape nor guaranteed
        for every past session. Equal-second executions are not deduplicated.
        Defaults use the current Tehran date, not the notebook system timezone.
        Weekend/holiday dates may legitimately produce no records.

    Examples:
        >>> from pydara import tse
        >>> selected = tse.assets(symbol=['فولاد', 'وبملت'])
        >>> df = tse.trades(selected, start='1405-07-01', end='1405-07-22',
        ...                 starttime='09:00', endtime='12:30')
        >>> print(df.attrs['pydara']['errors'])
        >>> df = tse.trades(selected, maxassets=100, checkpoint='./trades_checkpoints')
    """
    from .trades_workflow import trades as _trades
    return _trades(_client(), assets=_normalize_assets(assets), ins_code=ins_code,
        start=start, end=end, starttime=starttime, endtime=endtime,
        calendar=calendar, include_jdate=include_jdate, max_days=max_days,
        on_multiple=on_multiple, on_conflict=on_conflict,
        on_error=on_error, policy=policy, maxassets=maxassets,
        progress=progress, workers=workers, checkpoint=checkpoint)

__all__ = list(dict.fromkeys([*__all__, 'trades']))
