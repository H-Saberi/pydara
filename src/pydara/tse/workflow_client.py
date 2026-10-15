"""Public convenience and workflow methods (data only)."""
from __future__ import annotations
from pathlib import Path
import pandas as pd
from pydara.tse._core.models import InstrumentLike, Market
from .config import FetchPolicy
from .dates import DateLike
from .history_models import BatchFrames
from . import workflows

class WorkflowClientMixin:
    """Provide Workflow client operations to a client.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    def clients(self, instrument=None, *, ins_code=None, start=None, end=None, day=None,
                calendar='auto', include_jdate=False, on_multiple='all',
                on_conflict='error', on_error='collect', policy=None) -> pd.DataFrame:
        """Return unified client-type DataFrame; see ``tse.clients`` for full guide."""
        from .history_inputs import selectors, codes_from_frame
        from .clients_inputs import output
        from .instrument_lookup import lookup_policies
        from .workflows import friendly_range
        from .dates import parse_date
        from ._core.models import InstrumentRef
        from ._core.exceptions import PyDaraError, InvalidArgumentError
        if day is not None and (start is not None or end is not None):
            raise InvalidArgumentError('day cannot be combined with start or end.')
        if on_error not in ('collect','raise'):
            raise InvalidArgumentError('on_error must be collect or raise.')
        lookup_policies(on_multiple,on_conflict,has_ins_code=ins_code is not None)
        spec=selectors(instrument,ins_code=ins_code,on_multiple=on_multiple,on_conflict=on_conflict)
        lo,hi,cal=friendly_range(start,end,calendar=calendar)
        one=parse_date(day,calendar=cal,name='day') if day is not None else None
        frames=[];errors=[];requests=[];seen=set()
        for index,selector in enumerate(spec):
            try:
                matches=self.instrument(**selector,on_multiple=on_multiple,
                                        on_conflict=on_conflict,policy=policy)
                codes=codes_from_frame(matches)
                if not codes:
                    requests.append(dict(request_index=index,selector=selector,status='empty',row_count=0))
                for code in codes:
                    if code in seen:continue
                    seen.add(code)
                    ref=InstrumentRef.by_ins_code(code)
                    if start is not None or end is not None:
                        frame=self._get_client_type_history(ref,start=lo,end=hi,
                            calendar='gregorian',include_jdate=include_jdate,policy=policy)
                    else:
                        frame=self._get_client_types(ref,day=one,
                            calendar='gregorian',include_jdate=include_jdate,policy=policy)
                    frames.append(frame)
                    requests.append(dict(request_index=index,ins_code=code,selector=selector,
                        status='empty' if frame.empty else 'ok',row_count=len(frame)))
            except PyDaraError as exc:
                item=dict(request_index=index,selector=selector,error_code=type(exc).__name__,error_message=str(exc))
                errors.append(item);requests.append(dict(**item,status='error',row_count=0))
                if on_error=='raise':raise
        return output(frames,errors,requests,numeric=self.config.numeric,
                      include_jdate=include_jdate,calendar=cal)

    def history(self, instrument=None, *, ins_code=None, symbol=None, start=None, end=None,
                calendar='auto', adjustment='none', include_jdate=False, policy=None,
                on_multiple='all', on_conflict='error', on_error='collect') -> pd.DataFrame:
        """Fetch a unified daily-history DataFrame for symbols, codes, lists or instrument tables.

        Args:
            instrument: Symbol, ``InstrumentRef``, list/Series or DataFrame from ``instrument()``.
            ins_code: Explicit TSETMC code (string or integer); not inferred from symbol text.
            symbol: Symbol, optionally combined with ``ins_code`` for identity verification.
            start: Inclusive start date.
            end: Inclusive end date.
            calendar: ``auto``, ``jalali`` or ``gregorian`` for input dates.
            adjustment: ``none`` or supported source adjustment mode.
            include_jdate: Add Jalali date column when True.
            policy: Existing network/cache/offline fetch policy, passed to all requests.
            on_multiple: ``all`` (default), ``first`` or ``error`` for each selector.
            on_conflict: ``error`` (default) or ``ins_code`` for explicit code conflicts.
            on_error: ``collect`` (default) or ``raise`` on per-instrument failure.

        Returns:
            pandas.DataFrame: Unified history, including ``ins_code`` and ``symbol``.
            ``df.attrs['pydara']['requests']`` and ``['errors']`` retain batch results.
            Empty selections yield an empty typed frame. No artificial market rows.

        Notes:
            Duplicate ins_codes are fetched once. Selection is sequential; it reuses
            the existing history/network/cache engine. ``on_conflict='ins_code'``
            requires an explicit code when it is used.
        """
        from .history_inputs import selectors, codes_from_frame, merged_result
        from .instrument_lookup import lookup_policies
        from .workflows import friendly_range
        from ._core.models import InstrumentRef
        from ._core.exceptions import PyDaraError, InvalidArgumentError
        if on_error not in ('collect', 'raise'):
            raise InvalidArgumentError('on_error must be collect or raise.')
        lookup_policies(on_multiple, on_conflict, has_ins_code=ins_code is not None or
                        isinstance(instrument, (pd.DataFrame, InstrumentRef)) or
                        isinstance(instrument, (list, tuple)))
        spec=selectors(instrument, ins_code=ins_code, symbol=symbol,
                       on_multiple=on_multiple, on_conflict=on_conflict)
        lo, hi, cal=friendly_range(start,end,calendar=calendar)
        frames=[]; errors=[]; requests=[]; seen=set()
        for index, selector in enumerate(spec):
            try:
                matches=self.instrument(**selector, on_multiple=on_multiple,
                                        on_conflict=on_conflict, policy=policy)
                selected=codes_from_frame(matches)
                if not selected:
                    requests.append(dict(request_index=index,selector=selector,status='empty',row_count=0))
                    continue
                for code in selected:
                    if code in seen:
                        continue
                    seen.add(code)
                    frame=self.get_history(InstrumentRef.by_ins_code(code),start=lo,end=hi,
                                           adjustment=adjustment,include_jdate=include_jdate,policy=policy)
                    frame.attrs.setdefault('pydara',{})['input_calendar']=cal
                    frames.append(frame)
                    requests.append(dict(request_index=index, ins_code=code,selector=selector,
                                         status='empty' if frame.empty else 'ok',row_count=len(frame)))
            except PyDaraError as exc:
                error=dict(request_index=index,selector=selector,error_code=type(exc).__name__,error_message=str(exc))
                errors.append(error)
                requests.append(dict(**error,status='error',row_count=0))
                if on_error=='raise':
                    raise
        return merged_result(frames, errors, requests, numeric=self.config.numeric,
                             include_jdate=include_jdate,calendar=cal)

    def price(self, instrument=None, *, ins_code=None, on_multiple='all', on_conflict='error',
              on_error='collect', freshness=None, policy=None) -> pd.DataFrame:
        """Fetch latest quotes for an instrument table or one/many ins_codes.

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
        from .price_workflow import prepare, append_quotes, result
        from .frames import quote_row
        from ._core.models import InstrumentRef
        from ._core.exceptions import PyDaraError
        spec=prepare(instrument,ins_code,on_multiple,on_conflict,on_error)
        rows=[];errors=[];requests=[];seen=set()
        for index,selector in enumerate(spec):
            try:
                matches=self.instrument(**selector,on_multiple=on_multiple,on_conflict=on_conflict,policy=policy)
                jobs=append_quotes(rows,matches,seen,None,selector,index)
                if not jobs:
                    requests.append(dict(request_index=index,selector=selector,status='empty'))
                for code,active in jobs:
                    try:
                        q=self.get_quote(InstrumentRef.by_ins_code(code),freshness=freshness,policy=policy)
                        rows.append({**quote_row(q),'is_active':active,'request_index':index,
                                     'input_symbol':selector.get('symbol',code),'status':'ok',
                                     'error_code':None,'error_message':None})
                        requests.append(dict(request_index=index,ins_code=code,status='ok'))
                    except PyDaraError as exc:
                        error=dict(request_index=index,ins_code=code,error_code=type(exc).__name__,error_message=str(exc))
                        errors.append(error);requests.append(dict(**error,status='error'))
                        if on_error=='raise':raise
            except PyDaraError as exc:
                if on_error=='raise':raise
                if not any(e.get('request_index')==index for e in errors):
                    error=dict(request_index=index,selector=selector,error_code=type(exc).__name__,error_message=str(exc))
                    errors.append(error);requests.append(dict(**error,status='error'))
        return result(rows,errors,requests,self.config.numeric)

    def market(self, *, market: Market | str | None=None, include_order_book: bool=False, include_client_types: bool=False, backend: str='auto', policy: FetchPolicy | str | None=None) -> pd.DataFrame:
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
        return workflows.short_market(self, market=market, include_order_book=include_order_book, include_client_types=include_client_types, backend=backend, policy=policy)

    def index_history(self, index: str | int, *, start: DateLike | None=None, end: DateLike | None=None, calendar: str='auto', include_jdate: bool=False, market: Market | str | None=Market.TSE, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
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
        return workflows.short_index_history(self, index=index, start=start, end=end, calendar=calendar, include_jdate=include_jdate, market=market, policy=policy)

    def datasets(self) -> pd.DataFrame:
        'List locally stored response families, without HTTP.'
        return workflows.datasets(self)

    def storage_info(self) -> pd.DataFrame:
        'Inspect local storage health and file sizes, without HTTP.'
        return workflows.storage_info(self)

    def query(self, instrument: InstrumentLike, *, dataset: str='history', start: DateLike | None=None, end: DateLike | None=None, calendar: str='auto', include_jdate: bool=False) -> pd.DataFrame:
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
        return workflows.query(self, instrument=instrument, dataset=dataset, start=start, end=end, calendar=calendar, include_jdate=include_jdate)

    def backup(self, path: str | Path, *, overwrite: bool=False, timeout: float=30.0, flush: bool=True) -> dict:
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
        return workflows.backup(self, path=path, overwrite=overwrite, timeout=timeout, flush=flush)

    def download(self, symbols, *, dataset: str='history', start: DateLike | None=None, end: DateLike | None=None, calendar: str='auto', update: bool=True, store: bool | None=None, on_error: str='collect', checkpoint_dir: str | Path | None=None, resume: bool=True, resume_max_age: float=3600.0, include_jdate: bool=False, progress=None, policy: FetchPolicy | str | None=None) -> BatchFrames:
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
        return workflows.download(self, symbols=symbols, dataset=dataset, start=start, end=end, calendar=calendar, update=update, store=store, on_error=on_error, checkpoint_dir=checkpoint_dir, resume=resume, resume_max_age=resume_max_age, include_jdate=include_jdate, progress=progress, policy=policy)

    def update(self, symbols, *, start: DateLike | None=None, end: DateLike | None=None, calendar: str='auto', on_error: str='collect', checkpoint_dir: str | Path | None=None, resume: bool=False, progress=None) -> BatchFrames:
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
        return workflows.update(self, symbols=symbols, start=start, end=end, calendar=calendar, on_error=on_error, checkpoint_dir=checkpoint_dir, resume=resume, progress=progress)

    def download_market(self, *, dataset: str='history', market: Market | str | None=None, limit: int=100, start: DateLike | None=None, end: DateLike | None=None, calendar: str='auto', dry_run: bool=True, on_error: str='collect', checkpoint_dir: str | Path | None=None) -> pd.DataFrame | BatchFrames:
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
        return workflows.download_market(self, dataset=dataset, market=market, limit=limit, start=start, end=end, calendar=calendar, dry_run=dry_run, on_error=on_error, checkpoint_dir=checkpoint_dir)


class AsyncWorkflowClientMixin:
    """Native network awaits; shared job plan and threaded explicit disk operations."""
    async def clients(self, instrument=None, *, ins_code=None, start=None, end=None, day=None,
                calendar='auto', include_jdate=False, on_multiple='all',
                on_conflict='error', on_error='collect', policy=None) -> pd.DataFrame:
        """Return unified client-type DataFrame; see ``tse.clients`` for full guide."""
        from .history_inputs import selectors, codes_from_frame
        from .clients_inputs import output
        from .instrument_lookup import lookup_policies
        from .workflows import friendly_range
        from .dates import parse_date
        from ._core.models import InstrumentRef
        from ._core.exceptions import PyDaraError, InvalidArgumentError
        if day is not None and (start is not None or end is not None):
            raise InvalidArgumentError('day cannot be combined with start or end.')
        if on_error not in ('collect','raise'):
            raise InvalidArgumentError('on_error must be collect or raise.')
        lookup_policies(on_multiple,on_conflict,has_ins_code=ins_code is not None)
        spec=selectors(instrument,ins_code=ins_code,on_multiple=on_multiple,on_conflict=on_conflict)
        lo,hi,cal=friendly_range(start,end,calendar=calendar)
        one=parse_date(day,calendar=cal,name='day') if day is not None else None
        frames=[];errors=[];requests=[];seen=set()
        for index,selector in enumerate(spec):
            try:
                matches=await self.instrument(**selector,on_multiple=on_multiple,
                                        on_conflict=on_conflict,policy=policy)
                codes=codes_from_frame(matches)
                if not codes:
                    requests.append(dict(request_index=index,selector=selector,status='empty',row_count=0))
                for code in codes:
                    if code in seen:continue
                    seen.add(code)
                    ref=InstrumentRef.by_ins_code(code)
                    if start is not None or end is not None:
                        frame=await self._get_client_type_history(ref,start=lo,end=hi,
                            calendar='gregorian',include_jdate=include_jdate,policy=policy)
                    else:
                        frame=await self._get_client_types(ref,day=one,
                            calendar='gregorian',include_jdate=include_jdate,policy=policy)
                    frames.append(frame)
                    requests.append(dict(request_index=index,ins_code=code,selector=selector,
                        status='empty' if frame.empty else 'ok',row_count=len(frame)))
            except PyDaraError as exc:
                item=dict(request_index=index,selector=selector,error_code=type(exc).__name__,error_message=str(exc))
                errors.append(item);requests.append(dict(**item,status='error',row_count=0))
                if on_error=='raise':raise
        return output(frames,errors,requests,numeric=self.config.numeric,
                      include_jdate=include_jdate,calendar=cal)

    async def history(self, instrument=None, *, ins_code=None, symbol=None, start=None, end=None,
                      calendar='auto', adjustment='none', include_jdate=False, policy=None,
                      on_multiple='all', on_conflict='error', on_error='collect'):
        """Asynchronous counterpart of ``WorkflowClientMixin.history``.

Args:
    instrument (pandas.DataFrame | str | list[str] | None): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied. Default: None.
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
    See signature / actual returned object: Returns one merged DataFrame, including identity columns for multiple instruments. With on_error="collect", consult result.attrs["pydara"]["errors"] for item failures. Dates are inclusive. No missing sessions are inserted.

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
        from .history_inputs import selectors, codes_from_frame, merged_result
        from .instrument_lookup import lookup_policies
        from .workflows import friendly_range
        from ._core.models import InstrumentRef
        from ._core.exceptions import PyDaraError, InvalidArgumentError
        if on_error not in ('collect', 'raise'):
            raise InvalidArgumentError('on_error must be collect or raise.')
        lookup_policies(on_multiple, on_conflict, has_ins_code=ins_code is not None or
                        isinstance(instrument, (pd.DataFrame, InstrumentRef)) or
                        isinstance(instrument, (list, tuple)))
        spec=selectors(instrument, ins_code=ins_code, symbol=symbol,
                       on_multiple=on_multiple, on_conflict=on_conflict)
        lo,hi,cal=friendly_range(start,end,calendar=calendar)
        frames=[]; errors=[]; requests=[]; seen=set()
        for index, selector in enumerate(spec):
            try:
                matches=await self.instrument(**selector, on_multiple=on_multiple,
                                              on_conflict=on_conflict,policy=policy)
                selected=codes_from_frame(matches)
                if not selected:
                    requests.append(dict(request_index=index,selector=selector,status='empty',row_count=0))
                    continue
                for code in selected:
                    if code in seen:continue
                    seen.add(code)
                    frame=await self.get_history(InstrumentRef.by_ins_code(code),start=lo,end=hi,
                                                 adjustment=adjustment,include_jdate=include_jdate,policy=policy)
                    frame.attrs.setdefault('pydara',{})['input_calendar']=cal
                    frames.append(frame)
                    requests.append(dict(request_index=index,ins_code=code,selector=selector,
                                         status='empty' if frame.empty else 'ok',row_count=len(frame)))
            except PyDaraError as exc:
                error=dict(request_index=index,selector=selector,error_code=type(exc).__name__,error_message=str(exc))
                errors.append(error)
                requests.append(dict(**error,status='error',row_count=0))
                if on_error=='raise':raise
        return merged_result(frames,errors,requests,numeric=self.config.numeric,
                             include_jdate=include_jdate,calendar=cal)

    async def price(self, instrument=None, *, ins_code=None, on_multiple='all', on_conflict='error',
              on_error='collect', freshness=None, policy=None) -> pd.DataFrame:
        """Fetch latest quotes for an instrument table or one/many ins_codes.

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
        from .price_workflow import prepare, append_quotes, result
        from .frames import quote_row
        from ._core.models import InstrumentRef
        from ._core.exceptions import PyDaraError
        spec=prepare(instrument,ins_code,on_multiple,on_conflict,on_error)
        rows=[];errors=[];requests=[];seen=set()
        for index,selector in enumerate(spec):
            try:
                matches=await self.instrument(**selector,on_multiple=on_multiple,on_conflict=on_conflict,policy=policy)
                jobs=append_quotes(rows,matches,seen,None,selector,index)
                if not jobs:
                    requests.append(dict(request_index=index,selector=selector,status='empty'))
                for code,active in jobs:
                    try:
                        q=await self.get_quote(InstrumentRef.by_ins_code(code),freshness=freshness,policy=policy)
                        rows.append({**quote_row(q),'is_active':active,'request_index':index,
                                     'input_symbol':selector.get('symbol',code),'status':'ok',
                                     'error_code':None,'error_message':None})
                        requests.append(dict(request_index=index,ins_code=code,status='ok'))
                    except PyDaraError as exc:
                        error=dict(request_index=index,ins_code=code,error_code=type(exc).__name__,error_message=str(exc))
                        errors.append(error);requests.append(dict(**error,status='error'))
                        if on_error=='raise':raise
            except PyDaraError as exc:
                if on_error=='raise':raise
                if not any(e.get('request_index')==index for e in errors):
                    error=dict(request_index=index,selector=selector,error_code=type(exc).__name__,error_message=str(exc))
                    errors.append(error);requests.append(dict(**error,status='error'))
        return result(rows,errors,requests,self.config.numeric)

    async def market(self, *, market=None, include_order_book=False, include_client_types=False, backend='auto', policy=None):
        """Simple alias for get_market_watch; no financial analysis.
        
        Args:
            market (Any): Market selection or filtering constraint.
            include_order_book (Any): Input for the market operation.
            include_client_types (Any): Input for the market operation.
            backend (Any): Input for the market operation.
            policy (Any): Fetch policy controlling network and cached/offline behavior.
        
        Notes:
            This coroutine must be awaited.
        
        Returns:
            Implementation-defined result or generator output; see the calling API."""
        return await self.get_market_watch(market=market,include_order_book=include_order_book,include_client_types=include_client_types,backend=backend,policy=policy)

    async def index_history(self,index,*,start=None,end=None,calendar='auto',include_jdate=False,market=Market.TSE,policy=None):
        """Simple index-history alias with explicit auto-calendar policy.
        
        Args:
            index (Any): Input for the index_history operation.
            start (Any): Optional beginning of the requested date range.
            end (Any): Optional end of the requested date range.
            calendar (Any): Calendar used to parse or format dates.
            include_jdate (Any): Input for the index_history operation.
            market (Any): Market selection or filtering constraint.
            policy (Any): Fetch policy controlling network and cached/offline behavior.
        
        Notes:
            This coroutine must be awaited.
        
        Returns:
            Implementation-defined result or generator output; see the calling API."""
        lo,hi,cal=workflows.friendly_range(start,end,calendar=calendar)
        if index=='\u0634\u0627\u062e\u0635 \u06a9\u0644' and market in (Market.TSE,'TSE'):index='32097828799138957'
        frame=await self.get_index_history(index,start=lo,end=hi,include_jdate=include_jdate,market=market,policy=policy)
        frame.attrs.setdefault('pydara',{})['input_calendar']=cal
        return frame

    async def datasets(self) -> pd.DataFrame:
        """List locally stored response families, without HTTP.
        
        Notes:
            This coroutine must be awaited.
        
        Returns:
            pd.DataFrame: Result of the datasets operation; refer to its public API contract for schema details."""
        import asyncio
        return await asyncio.to_thread(workflows.datasets,self)

    async def storage_info(self) -> pd.DataFrame:
        """Inspect local storage health and file sizes, without HTTP.
        
        Notes:
            This coroutine must be awaited.
        
        Returns:
            pd.DataFrame: Result of the storage_info operation; refer to its public API contract for schema details."""
        import asyncio
        return await asyncio.to_thread(workflows.storage_info,self)

    async def query(self,instrument,*,dataset='history',start=None,end=None,calendar='auto',include_jdate=False):
        """Read locally stored data only. Never a live request; cached results retain time and stale flags.
        
        Args:
            instrument (Any): Instrument name or explicit instrument reference; ambiguity is not silently resolved.
            dataset (Any): Input for the query operation.
            start (Any): Optional beginning of the requested date range.
            end (Any): Optional end of the requested date range.
            calendar (Any): Calendar used to parse or format dates.
            include_jdate (Any): Input for the query operation.
        
        Notes:
            This coroutine must be awaited.
        
        Returns:
            Implementation-defined result or generator output; see the calling API.
        
        Raises:
            InvalidArgumentError: When the corresponding validation or operation fails."""
        from .config import FetchPolicy
        from pydara.tse._core.exceptions import InvalidArgumentError
        lo,hi,_=workflows.friendly_range(start,end,calendar=calendar)
        if dataset=='history':return await self.load_stored_history(instrument,start=lo,end=hi,include_jdate=include_jdate)
        if dataset not in workflows.DATASETS:raise InvalidArgumentError('Unknown dataset.')
        method,ranged=workflows.DATASETS[dataset]
        kwargs={'policy':FetchPolicy.offline(allow_stale=True)}
        if ranged:kwargs.update(start=lo,end=hi,include_jdate=include_jdate)
        elif lo or hi:raise InvalidArgumentError('This snapshot dataset has no range filter.')
        return await getattr(self,method)(instrument,**kwargs)

    async def backup(self,path,*,overwrite=False,timeout=30.0,flush=True):
        """Explicit SQLite backup with WAL consistency, integrity check and timeout. Does not change the original database.
        
        Args:
            path (Any): Local file or database path.
            overwrite (Any): Input for the backup operation.
            timeout (Any): Maximum wait time in seconds.
            flush (Any): Input for the backup operation.
        
        Notes:
            This coroutine must be awaited.
        
        Returns:
            Implementation-defined result or generator output; see the calling API.
        
        Raises:
            InvalidArgumentError: When the corresponding validation or operation fails."""
        import asyncio
        from .config import positive
        from pydara.tse._core.exceptions import InvalidArgumentError
        positive('timeout',timeout)
        if not isinstance(flush,bool):raise InvalidArgumentError('flush must be bool.')
        if flush:await self.flush(timeout=timeout,raise_on_error=True)
        return await asyncio.to_thread(workflows.backup,self,path,overwrite=overwrite,timeout=timeout,flush=False)

    async def download(self,symbols,*,dataset='history',start=None,end=None,calendar='auto',update=True,store=None,on_error='collect',checkpoint_dir=None,resume=True,resume_max_age=3600.0,include_jdate=False,progress=None,policy=None) -> BatchFrames:
        """Ordered data job with reports and opt-in disk checkpoints. Uses existing bounded network budget; partial success is explicit.
        
        Args:
            symbols (Any): Input for the download operation.
            dataset (Any): Input for the download operation.
            start (Any): Optional beginning of the requested date range.
            end (Any): Optional end of the requested date range.
            calendar (Any): Calendar used to parse or format dates.
            update (Any): Input for the download operation.
            store (Any): Input for the download operation.
            on_error (Any): Policy for handling errors in multi-item requests.
            checkpoint_dir (Any): Input for the download operation.
            resume (Any): Input for the download operation.
            resume_max_age (Any): Input for the download operation.
            include_jdate (Any): Input for the download operation.
            progress (Any): Input for the download operation.
            policy (Any): Fetch policy controlling network and cached/offline behavior.
        
        Notes:
            This coroutine must be awaited.
        
        Returns:
            BatchFrames: Result of the download operation; refer to its public API contract for schema details."""
        return await workflows.adownload(self,symbols,dataset=dataset,start=start,end=end,calendar=calendar,update=update,store=store,on_error=on_error,checkpoint_dir=checkpoint_dir,resume=resume,resume_max_age=resume_max_age,include_jdate=include_jdate,progress=progress,policy=policy)

    async def update(self,symbols,*,start=None,end=None,calendar='auto',on_error='collect',checkpoint_dir=None,resume=False,progress=None):
        """Update raw histories with overlap/correction handling. Default resume=False checks anew rather than reusing a job snapshot.
        
        Args:
            symbols (Any): Input for the update operation.
            start (Any): Optional beginning of the requested date range.
            end (Any): Optional end of the requested date range.
            calendar (Any): Calendar used to parse or format dates.
            on_error (Any): Policy for handling errors in multi-item requests.
            checkpoint_dir (Any): Input for the update operation.
            resume (Any): Input for the update operation.
            progress (Any): Input for the update operation.
        
        Notes:
            This coroutine must be awaited.
        
        Returns:
            Implementation-defined result or generator output; see the calling API."""
        return await self.download(symbols,dataset='history',start=start,end=end,calendar=calendar,update=True,on_error=on_error,checkpoint_dir=checkpoint_dir,resume=resume,progress=progress)

    async def download_market(self,*,dataset='history',market=None,limit=100,start=None,end=None,calendar='auto',dry_run=True,on_error='collect',checkpoint_dir=None):
        """Plan bounded downloads for the current watch universe. dry_run=True performs only watch retrieval; historical universe is not reconstructed.
        
        Args:
            dataset (Any): Input for the download_market operation.
            market (Any): Market selection or filtering constraint.
            limit (Any): Optional maximum result count, where supported.
            start (Any): Optional beginning of the requested date range.
            end (Any): Optional end of the requested date range.
            calendar (Any): Calendar used to parse or format dates.
            dry_run (Any): Input for the download_market operation.
            on_error (Any): Policy for handling errors in multi-item requests.
            checkpoint_dir (Any): Input for the download_market operation.
        
        Notes:
            This coroutine must be awaited.
        
        Returns:
            Implementation-defined result or generator output; see the calling API.
        
        Raises:
            InvalidArgumentError: When the corresponding validation or operation fails."""
        from .providers.market import positive_int
        from pydara.tse._core.models import InstrumentRef
        from pydara.tse._core.exceptions import InvalidArgumentError
        positive_int(limit,'limit',10000)
        if not isinstance(dry_run,bool) or dataset not in workflows.DATASETS:raise InvalidArgumentError('Invalid download plan arguments.')
        workflows.friendly_range(start,end,calendar=calendar)
        watch=await self.get_market_watch(market=market)
        selected=watch[['ins_code','symbol']].head(limit).copy()
        selected['dataset']=dataset;selected['planned']=True
        selected.attrs['pydara']={'universe':'current_observed_watch','not_historical_universe':True,'limit':limit,'truncated':len(watch)>limit}
        if dry_run:return selected
        return await self.download([InstrumentRef.by_ins_code(str(v)) for v in selected.ins_code],dataset=dataset,start=start,end=end,calendar=calendar,on_error=on_error,checkpoint_dir=checkpoint_dir)

# Aliases share the exact method signature and execution path.
WorkflowClientMixin.download_many = WorkflowClientMixin.download
AsyncWorkflowClientMixin.download_many = AsyncWorkflowClientMixin.download
