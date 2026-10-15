"""Native async HTTP with the same parsers, plans, frames and policies as Client."""
from __future__ import annotations
import asyncio
from collections.abc import Sequence, Iterator, AsyncIterator
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import httpx
import pandas as pd
import numpy as np

from pydara.tse._core.exceptions import (
    BatchDataError, PyDaraError, NetworkError, OfflineDataUnavailableError, StaleDataError,
    ServiceUnavailableError, UnknownReceiptError, UnsupportedCapabilityError,
)
from pydara.tse._core.models import InstrumentLike, InstrumentRecord, Market, Quote, WriteReceipt, StorageStatus, FlushReport
from .config import ClientConfig, FetchPolicy, FreshnessPolicy, positive, coerce_policy
from .engine import Core, build_config
from .frames import instrument_frame, quote_frame, quote_row
from .providers.public import instrument_plan, quote_plan
from .services import capability_frame, price_value, search_plan, validate_batch
from .dates import Calendar, DateLike
from .history import (prepare_history, history_plan, finish_history, validate_chunks,
                      split_history_frames, HistoryBatchBuilder)
from .history_models import BatchFrames
from .sync import SyncResult
from .transport import AsyncWire, Deadline


from .market_client import AsyncMarketClientMixin


from .extended_client import AsyncExtendedClientMixin

from .workflow_client import AsyncWorkflowClientMixin

class AsyncClient(AsyncMarketClientMixin, AsyncExtendedClientMixin, AsyncWorkflowClientMixin):
    """Use within one event loop and async context manager. No hidden asyncio.run()."""
    def __init__(self, *, config: ClientConfig | None = None, source: str | None = None,
                 mode: str | None = None, storage: bool | None = None,
                 data_dir: str | Path | None = None, numeric: str | None = None, credentials=None,
                 transport: httpx.AsyncBaseTransport | None = None, _namespace: str = "public"):
        """Initialize the instance and its configured state.
        
        Args:
            config (ClientConfig | None): Input for the __init__ operation.
            source (str | None): Input for the __init__ operation.
            mode (str | None): Selected operating or fetching mode.
            storage (bool | None): Input for the __init__ operation.
            data_dir (str | Path | None): Input for the __init__ operation.
            numeric (str | None): Numeric conversion or output representation setting.
            credentials (Any): Input for the __init__ operation.
            transport (httpx.AsyncBaseTransport | None): Input for the __init__ operation.
            _namespace (str): Input for the __init__ operation.
        
        Raises:
            UnsupportedCapabilityError: When the corresponding validation or operation fails."""
        if credentials is not None:
            raise UnsupportedCapabilityError("Official credentials are not supported in this release.")
        self.config = build_config(config, source, mode, storage, data_dir, numeric)
        self._core = Core(self.config, _namespace)
        self._wire = AsyncWire(self.config.network, transport)
        self._semaphore = asyncio.Semaphore(self.config.network.max_concurrency)
        self._close_report = None

    async def __aenter__(self):
        """Asynchronously enter the resource context.
        
        Notes:
            This coroutine must be awaited.
        
        Returns:
            Implementation-defined result or generator output; see the calling API."""
        self._core.check()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Asynchronously exit the resource context.
        
        Args:
            exc_type (Any): Input for the __aexit__ operation.
            exc (Any): Input for the __aexit__ operation.
            tb (Any): Input for the __aexit__ operation.
        
        Notes:
            This coroutine must be awaited.
        
        Returns:
            Implementation-defined result or generator output; see the calling API."""
        try:
            await self.aclose()
        except Exception:
            if exc_type is None:
                raise
        return False

    @property
    def request_count(self) -> int:
        """Perform the request count operation.
        
        Returns:
            int: Result of the request_count operation; refer to its public API contract for schema details."""
        return self._wire.requests_sent

    async def _fetch(self, spec, deadline, *, policy=None, freshness=None):
        """Fetch the requested value.
        
        Args:
            spec (Any): Request or schema specification.
            deadline (Any): Input for the _fetch operation.
            policy (Any): Fetch policy controlling network and cached/offline behavior.
            freshness (Any): Optional freshness criteria for returned data.
        
        Notes:
            This coroutine must be awaited.
        
        Returns:
            Implementation-defined result or generator output; see the calling API.
        
        Raises:
            OfflineDataUnavailableError: When the corresponding validation or operation fails.
            StaleDataError: When the corresponding validation or operation fails."""
        mode, fp = self._core.policy(spec, policy, freshness)
        key = spec.key(self._core.namespace)
        memory = self._core.cached_memory(key)
        admitted = self._core.admitted(memory, spec, fp, allow_stale=(mode == "offline"))
        if admitted is not None:
            return admitted
        disk = None
        if mode == "offline" or fp.max_age.total_seconds() > 0:
            disk = await self._core.adisk(key, required=(mode == "offline"))
            admitted = self._core.admitted(disk, spec, fp, allow_stale=(mode == "offline"))
            if admitted is not None:
                self._core.remember(admitted)
                return admitted
        if mode == "offline":
            if memory is not None or disk is not None:
                raise StaleDataError("Cached response exceeds max_age; explicitly allow stale to use it.")
            raise OfflineDataUnavailableError("This request has not been cached; offline sends no HTTP.")
        try:
            packet = await self._wire.request(spec, self._core.namespace, deadline)
        except (NetworkError, ServiceUnavailableError):
            if mode == "auto" and fp.allow_stale:
                cached = memory or disk or await self._core.adisk(key, required=True)
                admitted = self._core.admitted(cached, spec, fp, allow_stale=True)
                if admitted is not None:
                    return admitted
            raise
        return self._core.accept_network(packet, spec)

    async def _run(self, plan, *, policy=None, freshness=None):
        """Process internal run data.
        
        Args:
            plan (Any): Input for the _run operation.
            policy (Any): Fetch policy controlling network and cached/offline behavior.
            freshness (Any): Optional freshness criteria for returned data.
        
        Notes:
            This coroutine must be awaited.
        
        Returns:
            Implementation-defined result or generator output; see the calling API.
        
        Raises:
            OperationTimeoutError: When the corresponding validation or operation fails."""
        self._core.check()
        deadline = Deadline(self.config.network.operation_timeout)
        try:
            async with asyncio.timeout(deadline.remaining()):
                async with self._semaphore:
                    self._core.check()
                    try:
                        spec = next(plan)
                        while True:
                            packet = await self._fetch(spec, deadline, policy=policy, freshness=freshness)
                            spec = plan.send(packet)
                    except StopIteration as done:
                        return done.value
        except TimeoutError as exc:
            from pydara.tse._core.exceptions import OperationTimeoutError
            raise OperationTimeoutError("The operation exceeded its time budget.") from exc
        finally:
            plan.close()

    async def search_instruments(self, query: str, *, market: Market | None=None, include_inactive: bool=True, limit: int | None=None, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
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
        records = await self._run(search_plan(query, market=market, include_inactive=include_inactive, limit=limit, namespace=self._core.namespace), policy=policy)
        return instrument_frame(records)

    async def _resolve_instrument_record(self, instrument: InstrumentLike, *, market: Market | None=None, as_of: date | None=None, known_at: datetime | None=None, policy: FetchPolicy | str | None=None) -> InstrumentRecord:
        """Resolve one symbol or explicit InstrumentRef and verify its identity. Raises AmbiguousInstrumentError for multiple exact matches; use candidates or search_instruments to choose an ins_code. Historical identity and ISIN-only lookup remain unsupported."""
        return await self._run(instrument_plan(instrument, market=market, as_of=as_of, known_at=known_at, namespace=self._core.namespace), policy=policy)

    async def instrument(self, *, ins_code=None, instrument_id=None, company_cisin=None,
                   symbol=None, raw_symbol=None, name=None, market=None, raw_flow=None,
                   instrument_type=None, currency=None, is_active=None, strict=True,
                   on_multiple="all", on_conflict="error", policy=None) -> pd.DataFrame:
        """Find instruments as a DataFrame. Default: all exact matches; error on conflicts.

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
        from .instrument_lookup import (
            normalize_ins_codes,
            constraints, locator, lookup_policies, matching_codes,
            select_codes, verify_identity,
        )
        from pydara.tse._core.models import InstrumentRef
        ins_codes = normalize_ins_codes(ins_code) if ins_code is not None else None
        criteria, strict = constraints(
            ins_code=ins_codes[0] if ins_codes else None, instrument_id=instrument_id, company_cisin=company_cisin,
            symbol=symbol, raw_symbol=raw_symbol, name=name, market=market,
            raw_flow=raw_flow, instrument_type=instrument_type, currency=currency,
            is_active=is_active, strict=strict,
        )
        on_multiple, on_conflict = lookup_policies(
            on_multiple, on_conflict, has_ins_code="ins_code" in criteria)
        if "ins_code" in criteria:
            codes = select_codes(ins_codes, on_multiple)
        else:
            records = await self._run(search_plan(
                locator(criteria), market=None, include_inactive=True, limit=None,
                namespace=self._core.namespace), policy=policy)
            codes = select_codes(matching_codes(records, criteria, strict), on_multiple)
        resolved = []
        for code in codes:
            record = await self._resolve_instrument_record(InstrumentRef.by_ins_code(code), policy=policy)
            check = dict(criteria, ins_code=code)
            resolved.append(verify_identity(record, check, strict, on_conflict))
        return instrument_frame(resolved)

    async def resolve_instrument(self, **kwargs) -> pd.DataFrame:
        """Backward-compatible descriptive alias for instrument().

Args:
    kwargs (Any): See the function signature and related source validation for the accepted structure.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Backward-compatible descriptive alias for instrument()."""
        return await self.instrument(**kwargs)

    async def get_quote(self, instrument: InstrumentLike, *, freshness: FreshnessPolicy | None=None, policy: FetchPolicy | str | None=None) -> Quote:
        """Fetch the latest report as an immutable Quote with source and retrieval timestamps. A last report may be from a past trading day. Use an explicit offline policy to permit stale cached data; autosave errors are reported separately.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    freshness (FreshnessPolicy | None): FreshnessPolicy or None: controls tolerance of age for quote data; does not manufacture current market activity. Default: None.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    Quote: See the API reference for columns, metadata and error reporting.

Notes:
    Fetch the latest report as an immutable Quote with source and retrieval timestamps. A last report may be from a past trading day. Use an explicit offline policy to permit stale cached data; autosave errors are reported separately."""
        result = await self._run(quote_plan(instrument, namespace=self._core.namespace), policy=policy, freshness=freshness)
        return self._core.finish_quote(result, freshness, policy)

    async def get_price(self, instrument: InstrumentLike, *, field: str='last', freshness: FreshnessPolicy | None=None, policy: FetchPolicy | str | None=None) -> Decimal:
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
        if not isinstance(field, str) or field not in ('last', 'closing', 'previous_reference'):
            from pydara.tse._core.exceptions import InvalidArgumentError
            raise InvalidArgumentError('Invalid price field.')
        return price_value(await self.get_quote(instrument, freshness=freshness, policy=policy), field)

    async def get_quote_frame(self, instrument: InstrumentLike, *, freshness: FreshnessPolicy | None=None, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        """A one-row Pandas quote with the same checks as get_quote; no second HTTP call.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    freshness (FreshnessPolicy | None): FreshnessPolicy or None: controls tolerance of age for quote data; does not manufacture current market activity. Default: None.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    A one-row Pandas quote with the same checks as get_quote; no second HTTP call."""
        quote = await self.get_quote(instrument, freshness=freshness, policy=policy)
        return quote.to_frame(numeric=self.config.numeric)

    async def get_instrument_frame(self, instrument: InstrumentLike, *, market: Market | None=None, as_of: date | None=None, known_at: datetime | None=None, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
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
        record = await self._resolve_instrument_record(instrument, market=market, as_of=as_of, known_at=known_at, policy=policy)
        return instrument_frame([record])

    async def get_quotes(self, instruments: Sequence[InstrumentLike] | pd.Series | pd.Index | np.ndarray, *, on_error: str='raise', freshness: FreshnessPolicy | None=None, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
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
        self._core.check()
        policy = coerce_policy(policy)
        instruments = validate_batch(instruments, on_error)
        rows = []
        for idx, item in enumerate(instruments):
            base = dict(request_index=idx, input_symbol=item if isinstance(item, str) else item.value)
            try:
                q = await self.get_quote(item, freshness=freshness, policy=policy)
                rows.append({**quote_row(q), **base, 'status': 'ok', 'error_code': None, 'error_message': None})
            except PyDaraError as exc:
                rows.append({**base, 'status': 'error', 'error_code': type(exc).__name__, 'error_message': str(exc)})
                if on_error == 'raise':
                    partial = quote_frame([], numeric=self.config.numeric, batch_rows=rows)
                    raise BatchDataError('A batch item failed; inspect partial_result.', partial_result=partial) from exc
        return quote_frame([], numeric=self.config.numeric, batch_rows=rows)

    async def get_history(self, instrument: InstrumentLike, *, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', adjustment: str='none', series: str='listing', as_of: datetime | None=None, policy: FetchPolicy | str | None=None, include_jdate: bool=False) -> pd.DataFrame:
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
        self._core.check()
        query = prepare_history(start=start, end=end, calendar=calendar, adjustment=adjustment, series=series, as_of=as_of, include_jdate=include_jdate)
        frame = await self._run(history_plan(instrument, query=query, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_history(frame, policy)

    async def get_history_many(self, instruments: Sequence[InstrumentLike] | pd.Series | pd.Index | np.ndarray, *, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', adjustment: str='none', on_error: str='raise', policy: FetchPolicy | str | None=None, include_jdate: bool=False) -> BatchFrames:
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
        self._core.check()
        policy = coerce_policy(policy)
        instruments = validate_batch(instruments, on_error)
        prepare_history(start=start, end=end, calendar=calendar, adjustment=adjustment, include_jdate=include_jdate)
        builder = HistoryBatchBuilder(numeric=self.config.numeric, include_jdate=include_jdate, total=len(instruments))
        for index, item in enumerate(instruments):
            try:
                frame = await self.get_history(item, start=start, end=end, calendar=calendar, adjustment=adjustment, policy=policy, include_jdate=include_jdate)
                builder.success(index, item, frame)
            except PyDaraError as exc:
                builder.failure(index, item, exc)
                if on_error == 'raise':
                    raise BatchDataError('History batch item failed; inspect partial_result.', partial_result=builder.result()) from exc
        return builder.result()

    async def iter_history(self, instrument: InstrumentLike, *, start: DateLike, end: DateLike, calendar: Calendar='gregorian', adjustment: str='none', chunk_days: int=366, policy: FetchPolicy | str | None=None, include_jdate: bool=False) -> AsyncIterator[pd.DataFrame]:
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
    AsyncIterator[pd.DataFrame]: See the API reference for columns, metadata and error reporting.

Notes:
    Yield local calendar chunks. The underlying full HTTP response is NOT streamed.
    
                Skips chunks without rows; yields one typed empty frame if the whole
                selected range is empty. Each frame records its actual and chunk range."""
        self._core.check()
        validate_chunks(chunk_days)
        query = prepare_history(start=start, end=end, calendar=calendar, adjustment=adjustment, include_jdate=include_jdate)
        if query.start is None or query.end is None:
            from pydara.tse._core.exceptions import InvalidArgumentError
            raise InvalidArgumentError('iter_history requires both start and end.')
        frame = await self.get_history(instrument, start=query.start, end=query.end, calendar=calendar, adjustment=adjustment, policy=policy, include_jdate=include_jdate)
        for chunk in split_history_frames(frame, query.start, query.end, chunk_days):
            yield chunk

    async def sync_history(self, instrument: InstrumentLike, *, full: bool=False, overlap_days: int=14, full_refresh_days: float=7, wait: bool=True, timeout: float=30.0, on_storage_error: str='report') -> SyncResult:
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
        from .sync import async_sync_history
        return await async_sync_history(self, instrument, full=full, overlap_days=overlap_days, full_refresh_days=full_refresh_days, wait=wait, timeout=timeout, on_storage_error=on_storage_error)

    async def load_stored_history(self, instrument: InstrumentLike, *, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, as_of: datetime | None=None) -> pd.DataFrame:
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
        from .sync import store_for
        return await asyncio.to_thread(store_for(self._core).read, instrument, start=start, end=end, calendar=calendar, include_jdate=include_jdate, as_of=as_of)

    async def history_status(self) -> pd.DataFrame:
        """Return per-instrument counts, ranges and latest fetch state from the local index. Explicit disk read; no HTTP. Counts do not certify full market history."""
        from .sync import store_for
        return await asyncio.to_thread(store_for(self._core).status)

    async def get_history_revisions(self, instrument: InstrumentLike, *, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian') -> pd.DataFrame:
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
        from .sync import store_for
        return await asyncio.to_thread(store_for(self._core).revisions, instrument, start=start, end=end, calendar=calendar)

    async def reindex_history(self) -> dict:
        """Explicitly rebuild missing normalized history from cached responses of previous releases, without HTTP. Existing history is not deleted. Return a dictionary report; durable storage can raise StorageError."""
        from .sync import store_for
        await asyncio.to_thread(self._core.flush, self.config.storage.offline_read_timeout, False)
        return await asyncio.to_thread(store_for(self._core).reindex)

    def capabilities(self) -> pd.DataFrame:
        """Return the implemented, conditional and deferred capability matrix. A source-reviewed endpoint is not a live-service guarantee."""
        return capability_frame()

    def storage_status(self) -> StorageStatus:
        """Return in-memory storage counters without querying the database. Queued work is not durable until committed."""
        return self._core.status()

    def get_write_receipt(self, receipt_id: str) -> WriteReceipt:
        """Read the receipt status for this process. Unknown IDs raise UnknownReceiptError. A queued receipt does not prove disk durability.

Args:
    receipt_id (str): See the function signature and related source validation for the accepted structure.

Returns:
    WriteReceipt: See the API reference for columns, metadata and error reporting.

Notes:
    Read the receipt status for this process. Unknown IDs raise UnknownReceiptError. A queued receipt does not prove disk durability."""
        if not self._core.store:
            raise UnknownReceiptError('Storage is disabled.')
        return self._core.store.receipt(receipt_id)

    async def flush(self, *, timeout: float=5.0, raise_on_error: bool=True) -> FlushReport:
        """Explicitly wait up to timeout seconds for queued persistence. With raise_on_error=True incomplete or failed storage raises StorageError/StorageFlushTimeout. Normal automatic saving never waits for this call.

Args:
    timeout (float): See the function signature and related source validation for the accepted structure. Default: 5.0.
    raise_on_error (bool): See the function signature and related source validation for the accepted structure. Default: True.

Returns:
    FlushReport: See the API reference for columns, metadata and error reporting.

Notes:
    Explicitly wait up to timeout seconds for queued persistence. With raise_on_error=True incomplete or failed storage raises StorageError/StorageFlushTimeout. Normal automatic saving never waits for this call."""
        positive('timeout', timeout, zero=True)
        return await asyncio.to_thread(self._core.flush, timeout, raise_on_error)

    async def aclose(self, *, flush_timeout: float=1.0) -> FlushReport:
        """Close this AsyncClient with a bounded storage flush without blocking the event loop; returns FlushReport. Explicitly await it or use async with.

Args:
    flush_timeout (float): See the function signature and related source validation for the accepted structure. Default: 1.0.

Returns:
    FlushReport: See the API reference for columns, metadata and error reporting.

Notes:
    Close this AsyncClient with a bounded storage flush without blocking the event loop; returns FlushReport. Explicitly await it or use async with."""
        positive('flush_timeout', flush_timeout, zero=True)
        if self._close_report is not None:
            return self._close_report
        try:
            await self._wire.aclose()
        finally:
            self._close_report = await asyncio.to_thread(self._core.release, flush_timeout)
        return self._close_report
