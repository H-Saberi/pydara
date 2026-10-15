# Implemented API reference

Release 0.7.3a6. Generated from the actual installed Python signatures.
All functions below are implemented; deferred blueprint functions are in ROADMAP_FA.md.
Signatures with reserved arguments document their explicit failure behavior. Do not treat existence as support for every option.

## search_instruments

```python
search_instruments(query: 'str', *, market: 'Market | None' = None, include_inactive: 'bool' = True, limit: 'int | None' = None, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Search symbols without silently selecting the first match. Returns a typed DataFrame, including for no matches. A limit only limits displayed results; it is not a server pagination parameter.

Args:
    query (str): Search expression. A query is not a unique identifier and may match many results.
    market (Market | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: None.
    include_inactive (bool): Whether to include instruments without a reported active status. Default: True.
    limit (int | None): Maximum returned/displayed matches; None retains all eligible rows. Not necessarily remote pagination. Default: None.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Search symbols without silently selecting the first match. Returns a typed DataFrame, including for no matches. A limit only limits displayed results; it is not a server pagination parameter.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|query|str|required|Nonempty text to search. Search does not guess which result the user meant.|
|market|Market \| None|None|TSE/IFB/BASE enum or documented string. Support depends on endpoint; index/overview support TSE/IFB only. None never certifies historical coverage.|
|include_inactive|bool|True|Include inactive/unknown entries. False requires verified active status from the response.|
|limit|int \| None|None|Positive local display limit; None keeps all returned matches. Does not change server paging.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_quote

```python
get_quote(instrument: 'InstrumentLike', *, freshness: 'FreshnessPolicy | None' = None, policy: 'FetchPolicy | str | None' = None) -> 'Quote'
```

Fetch the latest report as an immutable Quote with source and retrieval timestamps. A last report may be from a past trading day. Use an explicit offline policy to permit stale cached data; autosave errors are reported separately.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    freshness (FreshnessPolicy | None): FreshnessPolicy or None: controls tolerance of age for quote data; does not manufacture current market activity. Default: None.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    Quote: See the API reference for columns, metadata and error reporting.

Notes:
    Fetch the latest report as an immutable Quote with source and retrieval timestamps. A last report may be from a past trading day. Use an explicit offline policy to permit stale cached data; autosave errors are reported separately.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|instrument|InstrumentLike|required|Symbol string or explicit InstrumentRef. A bare numeric string is not inferred as ins_code.|
|freshness|FreshnessPolicy \| None|None|Explicit FreshnessPolicy, with precedence over policy freshness for quotes.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** Quote
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_price

```python
get_price(instrument: 'InstrumentLike', *, field: 'str' = 'last', freshness: 'FreshnessPolicy | None' = None, policy: 'FetchPolicy | str | None' = None) -> 'Decimal'
```

Return a Decimal price. field is last, closing or previous_reference. Missing price raises MissingValueError and unverified price units raise UnsupportedQuoteUnitError. Use get_quote/get_quote_frame to retain time and unit metadata.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    field (str): Allowed "last", "closing", "previous_reference" for get_price(). Default: 'last'.
    freshness (FreshnessPolicy | None): FreshnessPolicy or None: controls tolerance of age for quote data; does not manufacture current market activity. Default: None.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    Decimal: See the API reference for columns, metadata and error reporting.

Notes:
    Return a Decimal price. field is last, closing or previous_reference. Missing price raises MissingValueError and unverified price units raise UnsupportedQuoteUnitError. Use get_quote/get_quote_frame to retain time and unit metadata.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|instrument|InstrumentLike|required|Symbol string or explicit InstrumentRef. A bare numeric string is not inferred as ins_code.|
|field|str|'last'|One of 'last', 'closing', 'previous_reference'; not a raw API field name.|
|freshness|FreshnessPolicy \| None|None|Explicit FreshnessPolicy, with precedence over policy freshness for quotes.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** Decimal
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError, MissingValueError, UnsupportedQuoteUnitError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_quotes

```python
get_quotes(instruments: 'Sequence[InstrumentLike] | pd.Series | pd.Index | np.ndarray', *, on_error: 'str' = 'raise', freshness: 'FreshnessPolicy | None' = None, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Fetch an ordered batch to a DataFrame. Accepts list/tuple, Series, Index or a 1D NumPy array. Duplicates and input order are preserved. on_error=collect records per-item errors; raise attaches partial_result to BatchDataError. No concurrency is implied.

Args:
    instruments (Sequence[InstrumentLike] | pd.Series | pd.Index | np.ndarray): Sequence of instrument references, pandas Series/Index, or one-dimensional NumPy array. See batch report for partial errors.
    on_error (str): Allowed: "collect" (record item failures and preserve successful rows) or "raise" (stop and raise). Defaults differ between individual APIs; see Signature. Default: 'raise'.
    freshness (FreshnessPolicy | None): FreshnessPolicy or None: controls tolerance of age for quote data; does not manufacture current market activity. Default: None.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Fetch an ordered batch to a DataFrame. Accepts list/tuple, Series, Index or a 1D NumPy array. Duplicates and input order are preserved. on_error=collect records per-item errors; raise attaches partial_result to BatchDataError. No concurrency is implied.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|instruments|Sequence[InstrumentLike] \| pd.Series \| pd.Index \| np.ndarray|required|Nonempty ordered list/tuple, Pandas Series/Index or a one-dimensional NumPy array. Duplicates preserved; nulls rejected.|
|on_error|str|'raise'|'raise' stops with partial_result; 'collect' records errors without losing other inputs.|
|freshness|FreshnessPolicy \| None|None|Explicit FreshnessPolicy, with precedence over policy freshness for quotes.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError, BatchDataError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_history

```python
get_history(instrument: 'InstrumentLike', *, start: 'DateLike | None' = None, end: 'DateLike | None' = None, calendar: 'Calendar' = 'gregorian', adjustment: 'str' = 'none', series: 'str' = 'listing', as_of: 'datetime | None' = None, policy: 'FetchPolicy | str | None' = None, include_jdate: 'bool' = False) -> 'pd.DataFrame'
```

Daily history, ascending and inclusive, without filling absent rows. Raw is the default. adjustment="source" uses the separate TSETMC chart a=1 response and keeps raw history untouched; inspect method/anchor metadata. It is not a total-return or point-in-time guarantee. Stitched identities and as_of remain unsupported.

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
    Daily history, ascending and inclusive, without filling absent rows. Raw is the default. adjustment="source" uses the separate TSETMC chart a=1 response and keeps raw history untouched; inspect method/anchor metadata. It is not a total-return or point-in-time guarantee. Stitched identities and as_of remain unsupported.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|instrument|InstrumentLike|required|Symbol string or explicit InstrumentRef. A bare numeric string is not inferred as ins_code.|
|start|DateLike \| None|None|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|DateLike \| None|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|Calendar|'gregorian'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|adjustment|str|'none'|Only 'none' is implemented; 'source' raises UnsupportedCapabilityError, never a fabricated adjusted series.|
|series|str|'listing'|Only 'listing' is implemented. 'continuous_verified' requires a verified historical identity chain.|
|as_of|datetime \| None|None|Timezone-aware cutoff for locally stored history; online historical reconstruction is not implemented.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|
|include_jdate|bool|False|Add a textual Jalali date column. It does not change the primary Gregorian date column.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError, UnsupportedCapabilityError, PointInTimeUnavailableError, CoverageError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_history_many

```python
get_history_many(instruments: 'Sequence[InstrumentLike] | pd.Series | pd.Index | np.ndarray', *, start: 'DateLike | None' = None, end: 'DateLike | None' = None, calendar: 'Calendar' = 'gregorian', adjustment: 'str' = 'none', on_error: 'str' = 'raise', policy: 'FetchPolicy | str | None' = None, include_jdate: 'bool' = False) -> 'BatchFrames'
```

Bounded sequential batch. Each input, even repeated/empty, gets a report row.

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
    Bounded sequential batch. Each input, even repeated/empty, gets a report row.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|instruments|Sequence[InstrumentLike] \| pd.Series \| pd.Index \| np.ndarray|required|Nonempty ordered list/tuple, Pandas Series/Index or a one-dimensional NumPy array. Duplicates preserved; nulls rejected.|
|start|DateLike \| None|None|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|DateLike \| None|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|Calendar|'gregorian'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|adjustment|str|'none'|Only 'none' is implemented; 'source' raises UnsupportedCapabilityError, never a fabricated adjusted series.|
|on_error|str|'raise'|'raise' stops with partial_result; 'collect' records errors without losing other inputs.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|
|include_jdate|bool|False|Add a textual Jalali date column. It does not change the primary Gregorian date column.|

**Returns:** BatchFrames
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError, UnsupportedCapabilityError, PointInTimeUnavailableError, CoverageError, BatchDataError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## iter_history

```python
iter_history(instrument: 'InstrumentLike', *, start: 'DateLike', end: 'DateLike', calendar: 'Calendar' = 'gregorian', adjustment: 'str' = 'none', chunk_days: 'int' = 366, policy: 'FetchPolicy | str | None' = None, include_jdate: 'bool' = False) -> 'Iterator[pd.DataFrame]'
```

Yield local calendar chunks. The underlying full HTTP response is NOT streamed.

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
    selected range is empty. Each frame records its actual and chunk range.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|instrument|InstrumentLike|required|Symbol string or explicit InstrumentRef. A bare numeric string is not inferred as ins_code.|
|start|DateLike|required|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|DateLike|required|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|Calendar|'gregorian'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|adjustment|str|'none'|Only 'none' is implemented; 'source' raises UnsupportedCapabilityError, never a fabricated adjusted series.|
|chunk_days|int|366|Positive calendar-day span for local output chunks. Not server-side streaming or pagination.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|
|include_jdate|bool|False|Add a textual Jalali date column. It does not change the primary Gregorian date column.|

**Returns:** Iterator[pd.DataFrame]
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## to_gregorian

```python
to_gregorian(value: 'DateLike', *, calendar: 'Calendar' = 'jalali') -> 'date'
```

Convert an accepted date to its Gregorian representation.

Args:
    value (DateLike): Input for the to_gregorian operation.
    calendar (Calendar): Calendar used to parse or format dates.

Returns:
    date: Result of the to_gregorian operation; refer to its public API contract for schema details.

Raises:
    InvalidArgumentError: When the corresponding validation or operation fails.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|value|DateLike|required|Input date or identifier; use the documented constructor to state its kind.|
|calendar|Calendar|'jalali'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|

**Returns:** date
**Errors:** InvalidArgumentError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## to_jalali

```python
to_jalali(value: 'DateLike') -> 'str'
```

Convert an accepted date to its Jalali representation.

Args:
    value (DateLike): Input for the to_jalali operation.

Returns:
    str: Result of the to_jalali operation; refer to its public API contract for schema details.

Raises:
    InvalidArgumentError: When the corresponding validation or operation fails.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|value|DateLike|required|Input date or identifier; use the documented constructor to state its kind.|

**Returns:** str
**Errors:** InvalidArgumentError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## capabilities

```python
capabilities() -> 'pd.DataFrame'
```

Return the implemented, conditional and deferred capability matrix. A source-reviewed endpoint is not a live-service guarantee.

|Parameter|Type|Default|Meaning|
|---|---|---|---|

**Returns:** pd.DataFrame
**Errors:** 
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** True

## storage_status

```python
storage_status() -> 'StorageStatus'
```

Return in-memory storage counters without querying the database. Queued work is not durable until committed.

|Parameter|Type|Default|Meaning|
|---|---|---|---|

**Returns:** StorageStatus
**Errors:** 
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** True

## get_write_receipt

```python
get_write_receipt(receipt_id: 'str') -> 'WriteReceipt'
```

Read the receipt status for this process. Unknown IDs raise UnknownReceiptError. A queued receipt does not prove disk durability.

Args:
    receipt_id (str): See the function signature and related source validation for the accepted structure.

Returns:
    WriteReceipt: See the API reference for columns, metadata and error reporting.

Notes:
    Read the receipt status for this process. Unknown IDs raise UnknownReceiptError. A queued receipt does not prove disk durability.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|receipt_id|str|required|Receipt identifier created in this running process, not a reusable authentication token.|

**Returns:** WriteReceipt
**Errors:** UnknownReceiptError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** True

## flush

```python
flush(*, timeout: 'float' = 5.0, raise_on_error: 'bool' = True) -> 'FlushReport'
```

Explicitly wait up to timeout seconds for queued persistence. With raise_on_error=True incomplete or failed storage raises StorageError/StorageFlushTimeout. Normal automatic saving never waits for this call.

Args:
    timeout (float): See the function signature and related source validation for the accepted structure. Default: 5.0.
    raise_on_error (bool): See the function signature and related source validation for the accepted structure. Default: True.

Returns:
    FlushReport: See the API reference for columns, metadata and error reporting.

Notes:
    Explicitly wait up to timeout seconds for queued persistence. With raise_on_error=True incomplete or failed storage raises StorageError/StorageFlushTimeout. Normal automatic saving never waits for this call.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|timeout|float|5.0|Bounded seconds for the explicit storage wait; not an exchange availability guarantee.|
|raise_on_error|bool|True|Whether detected errors should raise instead of only returning a report.|

**Returns:** FlushReport
**Errors:** StorageError, StorageFlushTimeout, ConfigurationError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** True

## close

```python
close(*, flush_timeout: 'float' = 1.0) -> 'FlushReport'
```

Close the default client. Explicitly flush first to require durable writes.

Args:
    flush_timeout (float): See the function signature and related source validation for the accepted structure. Default: 1.0.

Returns:
    FlushReport: See the API reference for columns, metadata and error reporting.

Notes:
    Close the default client. Explicitly flush first to require durable writes.
    
        The selected configuration is retained; configure() can replace it after close.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|flush_timeout|float|1.0|Maximum seconds to attempt flushing on close; inspect the returned complete flag.|

**Returns:** FlushReport
**Errors:** ConfigurationError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## get_quote_frame

```python
get_quote_frame(instrument: 'InstrumentLike', *, freshness: 'FreshnessPolicy | None' = None, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

A one-row Pandas quote with the same checks as get_quote; no second HTTP call.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    freshness (FreshnessPolicy | None): FreshnessPolicy or None: controls tolerance of age for quote data; does not manufacture current market activity. Default: None.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    A one-row Pandas quote with the same checks as get_quote; no second HTTP call.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|instrument|InstrumentLike|required|Symbol string or explicit InstrumentRef. A bare numeric string is not inferred as ins_code.|
|freshness|FreshnessPolicy \| None|None|Explicit FreshnessPolicy, with precedence over policy freshness for quotes.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_instrument_frame

```python
get_instrument_frame(instrument: 'InstrumentLike', *, market: 'Market | None' = None, as_of: 'date | None' = None, known_at: 'datetime | None' = None, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Resolve exactly one instrument and return its typed one-row DataFrame.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    market (Market | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: None.
    as_of (date | None): See the function signature and related source validation for the accepted structure. Default: None.
    known_at (datetime | None): See the function signature and related source validation for the accepted structure. Default: None.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Resolve exactly one instrument and return its typed one-row DataFrame.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|instrument|InstrumentLike|required|Symbol string or explicit InstrumentRef. A bare numeric string is not inferred as ins_code.|
|market|Market \| None|None|TSE/IFB/BASE enum or documented string. Support depends on endpoint; index/overview support TSE/IFB only. None never certifies historical coverage.|
|as_of|date \| None|None|Reserved economic identity date; historical identity lookup is explicitly unsupported.|
|known_at|datetime \| None|None|Historical identity knowledge cutoff; reserved and explicitly rejected in this release.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## configure

```python
configure(config: 'ClientConfig | None' = None, *, source: 'str | None' = None, mode: 'str | None' = None, storage: 'bool | None' = None, data_dir: 'str | Path | None' = None, numeric: 'str | None' = None) -> 'ClientConfig'
```

Configure the lazy module-level client without HTTP or creating a database.

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
        ClientConfig defaults (or the explicitly supplied config).

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|config|ClientConfig \| None|None|Immutable ClientConfig; supplied constructor overrides take precedence.|
|source|str \| None|None|Only 'public' is supported; official authentication is not pretended to work.|
|mode|str \| None|None|auto/online/offline; fresh cached responses may be reused in online. FetchPolicy.fresh() bypasses the cache.|
|storage|bool \| None|None|Boolean enabling the default best-effort local response storage, or None to use config.|
|data_dir|str \| Path \| None|None|Directory containing pydara.sqlite3. Does not move or delete old databases.|
|numeric|str \| None|None|'analysis' gives nullable Float64; 'exact' uses Decimal for price/quantity fields. Identifiers always remain text.|

**Returns:** ClientConfig
**Errors:** ConfigurationError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## get_config

```python
get_config() -> 'ClientConfig'
```

Return immutable default settings without creating a Client or any I/O.

|Parameter|Type|Default|Meaning|
|---|---|---|---|

**Returns:** ClientConfig
**Errors:** 
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## save

```python
save(df: 'pd.DataFrame', path: 'str | Path', *, format: 'str | None' = None, dataset: 'str' = 'user_data', metadata: 'bool' = True, overwrite: 'bool' = False, safe_text: 'bool' = True) -> 'WriteReceipt'
```

Save a self-describing snapshot; return only after successful commit.

``metadata=False`` omits df.attrs, not structural type/checksum information.
MultiIndex/unsupported object values are rejected. No network requests.
CSV + sidecar replace is not one filesystem transaction: a crash between
replacements is detected by load's SHA256 check, never silently accepted.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|df|pd.DataFrame|required|An ordinary Pandas DataFrame; input is never modified in place by local helpers.|
|path|str \| Path|required|Nonempty path string or pathlib.Path, not the working cache database for archive exports.|
|format|str \| None|None|csv/excel/parquet/sqlite, or None to infer from the supported file suffix.|
|dataset|str|'user_data'|Name of a stored table archive inside a snapshot SQLite database.|
|metadata|bool|True|Keep dataframe attrs as well as structural schema; False omits attrs, not required type/checksum metadata.|
|overwrite|bool|False|Explicit consent to replace this export path/dataset. Default False.|
|safe_text|bool|True|Protect dangerous formula-like text on export; decoding reverses the protection.|

**Returns:** WriteReceipt
**Errors:** InvalidArgumentError, FileExistsDataError, StorageError, OptionalDependencyError
**Dependencies:** pandas, Python standard library, openpyxl only for Excel, pyarrow only for Parquet, sqlite3 for SQLite
**AsyncClient counterpart:** False

## load

```python
load(path: 'str | Path', *, format: 'str | None' = None, dataset: 'str' = 'user_data', schema=None, verify: 'bool' = True) -> 'pd.DataFrame'
```

Read a PyDara archive and verify its structure/content. This is not a signature.

For arbitrary externally-created files use pandas readers, then validate.
``verify=False`` allows deliberate value edits, not code execution or a
different schema. CSV still requires its sidecar for dtype restoration.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|path|str \| Path|required|Nonempty path string or pathlib.Path, not the working cache database for archive exports.|
|format|str \| None|None|csv/excel/parquet/sqlite, or None to infer from the supported file suffix.|
|dataset|str|'user_data'|Name of a stored table archive inside a snapshot SQLite database.|
|schema|documented in source|None|Name of an implemented structural schema. For load, this argument remains reserved; use None.|
|verify|bool|True|Check archive checksums and structure. Not a cryptographic signature of a trusted sender.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, StorageError, OptionalDependencyError
**Dependencies:** pandas, Python standard library, openpyxl only for Excel, pyarrow only for Parquet, sqlite3 for SQLite
**AsyncClient counterpart:** False

## sync_history

```python
sync_history(instrument: 'InstrumentLike', *, full: 'bool' = False, overlap_days: 'int' = 14, full_refresh_days: 'float' = 7, wait: 'bool' = True, timeout: 'float' = 30.0, on_storage_error: 'str' = 'report') -> 'SyncResult'
```

Explicit reconciliation into the local history index. full=True rechecks old corrections; overlap_days controls the tail window. wait=True may wait for storage. on_storage_error=report preserves fetched data with failure information; raise demands success. SyncResult.data is only this fetch, not the whole database.

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
    Explicit reconciliation into the local history index. full=True rechecks old corrections; overlap_days controls the tail window. wait=True may wait for storage. on_storage_error=report preserves fetched data with failure information; raise demands success. SyncResult.data is only this fetch, not the whole database.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|instrument|InstrumentLike|required|Symbol string or explicit InstrumentRef. A bare numeric string is not inferred as ins_code.|
|full|bool|False|Force a full source-history recheck instead of the calculated tail request.|
|overlap_days|int|14|Positive calendar-day overlap window for rechecking recent corrections.|
|full_refresh_days|float|7|After this many days since a full fetch, the next explicit sync performs a full audit. No scheduler.|
|wait|bool|True|Wait for storage only in explicit sync. False may return queued state, not durable data.|
|timeout|float|30.0|Bounded seconds for the explicit storage wait; not an exchange availability guarantee.|
|on_storage_error|str|'report'|'report' retains downloaded data with a failure report; 'raise' requires successful explicit storage.|

**Returns:** SyncResult
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## load_stored_history

```python
load_stored_history(instrument: 'InstrumentLike', *, start: 'DateLike | None' = None, end: 'DateLike | None' = None, calendar: 'Calendar' = 'gregorian', include_jdate: 'bool' = False, as_of: 'datetime | None' = None) -> 'pd.DataFrame'
```

Read the versioned local history index; never sends HTTP. Dates are inclusive. as_of is a local observation/commit cutoff, not proof of historical public availability. Raises OfflineDataUnavailableError when no usable indexed data exists.

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
    Read the versioned local history index; never sends HTTP. Dates are inclusive. as_of is a local observation/commit cutoff, not proof of historical public availability. Raises OfflineDataUnavailableError when no usable indexed data exists.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|instrument|InstrumentLike|required|Symbol string or explicit InstrumentRef. A bare numeric string is not inferred as ins_code.|
|start|DateLike \| None|None|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|DateLike \| None|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|Calendar|'gregorian'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|include_jdate|bool|False|Add a textual Jalali date column. It does not change the primary Gregorian date column.|
|as_of|datetime \| None|None|Timezone-aware cutoff for locally stored history; online historical reconstruction is not implemented.|

**Returns:** pd.DataFrame
**Errors:** OfflineDataUnavailableError, StorageError, InvalidArgumentError, AmbiguousInstrumentError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** True

## history_status

```python
history_status() -> 'pd.DataFrame'
```

Return per-instrument counts, ranges and latest fetch state from the local index. Explicit disk read; no HTTP. Counts do not certify full market history.

|Parameter|Type|Default|Meaning|
|---|---|---|---|

**Returns:** pd.DataFrame
**Errors:** StorageError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** True

## get_history_revisions

```python
get_history_revisions(instrument: 'InstrumentLike', *, start: 'DateLike | None' = None, end: 'DateLike | None' = None, calendar: 'Calendar' = 'gregorian') -> 'pd.DataFrame'
```

Return locally observed economic revisions in the requested inclusive range. This is local evidence, not all revisions ever published by the exchange.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    start (DateLike | None): Inclusive starting date or None: date, supported date string or pandas.Timestamp. Use calendar for string interpretation. Default: None.
    end (DateLike | None): Inclusive ending date or None: date, supported date string or pandas.Timestamp. No missing trading days are fabricated. Default: None.
    calendar (Calendar): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'gregorian'.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Return locally observed economic revisions in the requested inclusive range. This is local evidence, not all revisions ever published by the exchange.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|instrument|InstrumentLike|required|Symbol string or explicit InstrumentRef. A bare numeric string is not inferred as ins_code.|
|start|DateLike \| None|None|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|DateLike \| None|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|Calendar|'gregorian'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|

**Returns:** pd.DataFrame
**Errors:** StorageError, OfflineDataUnavailableError, InvalidArgumentError, UnsupportedCapabilityError, PointInTimeUnavailableError, CoverageError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** True

## reindex_history

```python
reindex_history() -> 'dict'
```

Explicitly rebuild missing normalized history from cached responses of previous releases, without HTTP. Existing history is not deleted. Return a dictionary report; durable storage can raise StorageError.

|Parameter|Type|Default|Meaning|
|---|---|---|---|

**Returns:** dict
**Errors:** StorageError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** True

## schema_info

```python
schema_info(schema: 'str' = 'daily_bars', *, numeric: 'str' = 'analysis') -> 'pd.DataFrame'
```

Return column names, expected dtypes and meanings for an implemented schema.

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

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|schema|str|'daily_bars'|An implemented schema name returned by capabilities()/the dataset metadata; includes daily_bars, quote, market_watch, client_types, indices, index_history and related new schemas.|
|numeric|str|'analysis'|'analysis' gives nullable Float64; 'exact' uses Decimal for price/quantity fields. Identifiers always remain text.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## validate_data

```python
validate_data(df: 'pd.DataFrame', *, schema: 'str | None' = None, raise_on_error: 'bool' = False, check_order: 'bool' = True) -> 'pd.DataFrame'
```

Report schema/value issues without changing data or contacting TSETMC.

The report columns are severity, rule, column, count, row_positions, message.
row_positions are zero-based positions (not possibly duplicated index labels).
At most ten example positions are kept per rule. Warnings do not certify or
invalidate financial truth. This function is NOT a point-in-time/leakage audit.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|df|pd.DataFrame|required|An ordinary Pandas DataFrame; input is never modified in place by local helpers.|
|schema|str \| None|None|An implemented schema name returned by capabilities()/the dataset metadata; includes daily_bars, quote, market_watch, client_types, indices, index_history and related new schemas.|
|raise_on_error|bool|False|Whether detected errors should raise instead of only returning a report.|
|check_order|bool|True|Report ascending natural-key order violations without sorting input.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, DataQualityError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## normalize_data

```python
normalize_data(df: 'pd.DataFrame', *, schema: 'str' = 'daily_bars', columns: 'Mapping[str, str] | None' = None, calendar: 'Calendar' = 'gregorian', numeric: 'str' = 'analysis', timezone: 'str | None' = None, sort: 'bool' = False) -> 'pd.DataFrame'
```

Normalize only present known fields; never invent source/time/zero values.

``columns`` is an explicit old-name -> standard-name mapping. Date strings
use the explicitly supplied calendar. Naive real timestamps require timezone.
Floating-point identifiers are rejected even when they look integral: original
digits may already be lost. Unknown columns are preserved, rows are not dropped,
duplicate keys are left for validate_data(), and the input/index are preserved
unless sort=True reorders rows. No investment calculation is performed.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|df|pd.DataFrame|required|An ordinary Pandas DataFrame; input is never modified in place by local helpers.|
|schema|str|'daily_bars'|An implemented schema name returned by capabilities()/the dataset metadata; includes daily_bars, quote, market_watch, client_types, indices, index_history and related new schemas.|
|columns|Mapping[str, str] \| None|None|Explicit column list/preset for selection or old-name -> new-name mapping for normalization.|
|calendar|Calendar|'gregorian'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|numeric|str|'analysis'|'analysis' gives nullable Float64; 'exact' uses Decimal for price/quantity fields. Identifiers always remain text.|
|timezone|str \| None|None|Explicit timezone for otherwise-naive real timestamps. Daily dates remain timezone-naive.|
|sort|bool|False|Explicitly reorder normalized rows by request_index/ins_code/date if present. No rows are dropped.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## select_columns

```python
select_columns(df: 'pd.DataFrame', columns: 'Sequence[str] | str' = 'compact') -> 'pd.DataFrame'
```

Select explicit columns, or the documented 'compact'/'full' presentation.

Compact output is a view for users, not a provenance-complete archive. Full
metadata is copied, and any removed evidence columns are listed in it.
Unknown/duplicate column names raise InvalidArgumentError instead of being ignored.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|df|pd.DataFrame|required|An ordinary Pandas DataFrame; input is never modified in place by local helpers.|
|columns|Sequence[str] \| str|'compact'|Explicit column list/preset for selection or old-name -> new-name mapping for normalization.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## frame_metadata

```python
frame_metadata(df: 'pd.DataFrame') -> 'dict'
```

Return a deep copy of df.attrs['pydara']; absent evidence stays unknown.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|df|pd.DataFrame|required|An ordinary Pandas DataFrame; input is never modified in place by local helpers.|

**Returns:** dict
**Errors:** InvalidArgumentError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## api_reference

```python
api_reference(name: 'str | None' = None) -> 'pd.DataFrame'
```

Return signatures, inputs, outputs, errors and dependencies for this release.

name is an optional exact public function/class name. The catalog includes
implemented API only; the HTML roadmap has separate not-yet-implemented plans.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|name|str \| None|None|Optional exact public API name to select from the installed reference.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## validate

```python
validate(df: 'pd.DataFrame', *, schema: 'str', strict: 'bool' = True) -> 'pd.DataFrame'
```

Roadmap-compatible validation entry point.

Returns row_id, rule, severity, message and additional grouped diagnostic
columns. A grouped issue may have no single row_id; count and row_positions
then describe it. strict=True raises DataQualityError with this same report.
This verifies a structural contract, not source correctness or completeness.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|df|pd.DataFrame|required|An ordinary Pandas DataFrame; input is never modified in place by local helpers.|
|schema|str|required|An implemented schema name returned by capabilities()/the dataset metadata; includes daily_bars, quote, market_watch, client_types, indices, index_history and related new schemas.|
|strict|bool|True|Validated setting; see the constructor docstring and configuration source.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, DataQualityError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## normalize

```python
normalize(df: 'pd.DataFrame', *, schema: 'str', source: 'str', strict: 'bool' = True) -> 'pd.DataFrame'
```

Roadmap normalization entry point for already canonical column names.

source='canonical' is the currently reviewed mapping. Raw external API
mappings are not inferred; use normalize_data(columns=...) for an explicit
user mapping and then validate it. All unknown sources fail explicitly.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|df|pd.DataFrame|required|An ordinary Pandas DataFrame; input is never modified in place by local helpers.|
|schema|str|required|Name of an implemented structural schema. For load, this argument remains reserved; use None.|
|source|str|required|Only 'canonical' is supported; raw provider column names are not inferred.|
|strict|bool|True|Validated setting; see the constructor docstring and configuration source.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, DataQualityError, UnsupportedCapabilityError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## load_sample

```python
load_sample(name: 'str' = 'daily_prices_v1') -> 'pd.DataFrame'
```

Load explicit synthetic data with no database access or real network.

Names: daily_prices_v1, quote_v1, market_watch_v1, client_types_v1,
indices_v1 and index_history_v1. These are teaching/test values, never
current market prices, and they cannot become live data through fallback.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|name|str|'daily_prices_v1'|Synthetic fixture: daily_prices_v1, quote_v1, market_watch_v1, client_types_v1, indices_v1 or index_history_v1.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## get_market_watch

```python
get_market_watch(*, market: 'Market | str | None' = None, include_order_book: 'bool' = False, include_client_types: 'bool' = False, show_traded: 'bool' = False, backend: 'str' = 'auto', policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Return the current public market watch as a typed DataFrame. auto falls back to the reviewed legacy text route only when JSON returns a valid empty list. Optional books and client types retain independent provenance; rows are not an atomic snapshot. Empty is not proof of a closed market.

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
    Return the current public market watch as a typed DataFrame. auto falls back to the reviewed legacy text route only when JSON returns a valid empty list. Optional books and client types retain independent provenance; rows are not an atomic snapshot. Empty is not proof of a closed market.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|market|Market \| str \| None|None|TSE/IFB/BASE enum or documented string. Support depends on endpoint; index/overview support TSE/IFB only. None never certifies historical coverage.|
|include_order_book|bool|False|Add reported depth 1..5 columns with separate provenance; no forward fill.|
|include_client_types|bool|False|Fetch and join a separate bulk response by exact ID; timestamps may be absent/different.|
|show_traded|bool|False|Return only rows with a reported positive trade_count. Unknown is not treated as proof of no trading.|
|backend|str|'auto'|auto/json/legacy; auto uses legacy only after valid empty JSON, not after auth/HTTP/schema errors.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError, UnsupportedCapabilityError, PointInTimeUnavailableError, CoverageError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_market_order_book

```python
get_market_order_book(*, market: 'Market | str | None' = None, backend: 'str' = 'auto', policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Return reported best-limit levels for the current watch. This is not the full exchange order book or historical depth. Missing levels are not filled. Source timestamps not reported by the feed remain missing.

Args:
    market (Market | str | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: None.
    backend (str): Allowed "auto", "json", "legacy" where supported; auto fallback is conditional rather than a generic retry on every error. Default: 'auto'.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Return reported best-limit levels for the current watch. This is not the full exchange order book or historical depth. Missing levels are not filled. Source timestamps not reported by the feed remain missing.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|market|Market \| str \| None|None|TSE/IFB/BASE enum or documented string. Support depends on endpoint; index/overview support TSE/IFB only. None never certifies historical coverage.|
|backend|str|'auto'|auto/json/legacy; auto uses legacy only after valid empty JSON, not after auth/HTTP/schema errors.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError, UnsupportedCapabilityError, PointInTimeUnavailableError, CoverageError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_market_overview

```python
get_market_overview(*, market: 'Market | str' = <Market.TSE: 'TSE'>, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Return one row of reported market totals and index values. TSE or IFB only. Activity time and overall data time remain separate.

Args:
    market (Market | str): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: Market.TSE.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Return one row of reported market totals and index values. TSE or IFB only. Activity time and overall data time remain separate.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|market|Market \| str|<Market.TSE: 'TSE'>|TSE/IFB/BASE enum or documented string. Support depends on endpoint; index/overview support TSE/IFB only. None never certifies historical coverage.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError, UnsupportedCapabilityError, PointInTimeUnavailableError, CoverageError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_market_map

```python
get_market_map(*, sector_code: 'str | None' = None, limit: 'int' = 9999, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Return the reported market-map data only; no drawing or computed ranking. The source size parameter can truncate output; coverage is not certified.

Args:
    sector_code (str | None): See the function signature and related source validation for the accepted structure. Default: None.
    limit (int): Maximum returned/displayed matches; None retains all eligible rows. Not necessarily remote pagination. Default: 9999.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Return the reported market-map data only; no drawing or computed ranking. The source size parameter can truncate output; coverage is not certified.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|sector_code|str \| None|None|Exact short sector code returned by get_sectors(), preserving leading zeros.|
|limit|int|9999|Requested server output bound; not a coverage guarantee. Index impact other than the reviewed limit 7 is unverified.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError, UnsupportedCapabilityError, PointInTimeUnavailableError, CoverageError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_sectors

```python
get_sectors(*, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Return sector codes/names with the four source counters preserved as source_c1..source_c4. Their undocumented bucket meanings are not guessed.

Args:
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Return sector codes/names with the four source counters preserved as source_c1..source_c4. Their undocumented bucket meanings are not guessed.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_sector_instruments

```python
get_sector_instruments(sector_code: 'str', *, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Return current related-company quotes for an exact sector code. This is industry grouping, not evidence of corporate ownership.

Args:
    sector_code (str): See the function signature and related source validation for the accepted structure.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Return current related-company quotes for an exact sector code. This is industry grouping, not evidence of corporate ownership.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|sector_code|str|required|Exact short sector code returned by get_sectors(), preserving leading zeros.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_key_statistics

```python
get_key_statistics(*, ins_code: 'str | int | None' = None, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Return all reported parameter-code/value pairs (potentially a large response). ins_code filtering is local after the bulk response. reported_value stays text: undocumented units and metrics are not guessed.

Args:
    ins_code (str | int | None): One positive exchange instrument code as str/int, or an ordered list of codes for instrument(), history() and price(). Codes are identifiers, not company tickers. Default: None.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Return all reported parameter-code/value pairs (potentially a large response). ins_code filtering is local after the bulk response. reported_value stays text: undocumented units and metrics are not guessed.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|ins_code|str \| int \| None|None|Exact positive integer identifier; on bulk key statistics this is a local filter.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_market_client_types

```python
get_market_client_types(*, market: 'Market | str | None' = None, backend: 'str' = 'auto', policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Return the bulk client-type response. With market selected, intersect with current watch identities (one extra component); without a filter, keep every returned ins_code. No date/value/market is guessed when absent.

Args:
    market (Market | str | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: None.
    backend (str): Allowed "auto", "json", "legacy" where supported; auto fallback is conditional rather than a generic retry on every error. Default: 'auto'.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Return the bulk client-type response. With market selected, intersect with current watch identities (one extra component); without a filter, keep every returned ins_code. No date/value/market is guessed when absent.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|market|Market \| str \| None|None|TSE/IFB/BASE enum or documented string. Support depends on endpoint; index/overview support TSE/IFB only. None never certifies historical coverage.|
|backend|str|'auto'|auto/json/legacy; auto uses legacy only after valid empty JSON, not after auth/HTTP/schema errors.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError, UnsupportedCapabilityError, PointInTimeUnavailableError, CoverageError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_indices

```python
get_indices(*, market: 'Market | str | None' = <Market.TSE: 'TSE'>, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Return index codes, names and latest reported values. market=None explicitly requests TSE and IFB catalogs separately. Unit is points, never currency.

Args:
    market (Market | str | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: Market.TSE.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Return index codes, names and latest reported values. market=None explicitly requests TSE and IFB catalogs separately. Unit is points, never currency.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|market|Market \| str \| None|<Market.TSE: 'TSE'>|TSE/IFB/BASE enum or documented string. Support depends on endpoint; index/overview support TSE/IFB only. None never certifies historical coverage.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## search_indices

```python
search_indices(query: 'str', *, market: 'Market | str | None' = <Market.TSE: 'TSE'>, limit: 'int | None' = None, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Search normalized current index names; never choose the first match implicitly. A local limit does not change server pagination.

Args:
    query (str): Search expression. A query is not a unique identifier and may match many results.
    market (Market | str | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: Market.TSE.
    limit (int | None): Maximum returned/displayed matches; None retains all eligible rows. Not necessarily remote pagination. Default: None.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Search normalized current index names; never choose the first match implicitly. A local limit does not change server pagination.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|query|str|required|Nonempty text to search. Search does not guess which result the user meant.|
|market|Market \| str \| None|<Market.TSE: 'TSE'>|TSE/IFB/BASE enum or documented string. Support depends on endpoint; index/overview support TSE/IFB only. None never certifies historical coverage.|
|limit|int \| None|None|Positive local display limit; None keeps all returned matches. Does not change server paging.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError, UnsupportedCapabilityError, PointInTimeUnavailableError, CoverageError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_index

```python
get_index(index: 'str | int | InstrumentRef', *, market: 'Market | str | None' = <Market.TSE: 'TSE'>, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Resolve exactly one index from the current catalog by exact name or code, returning a one-row DataFrame. Ambiguous names raise. Use get_indices(market=None) to inspect available codes.

Args:
    index (str | int | InstrumentRef): Exact index identifier/name; ambiguous results must not be selected silently.
    market (Market | str | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: Market.TSE.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Resolve exactly one index from the current catalog by exact name or code, returning a one-row DataFrame. Ambiguous names raise. Use get_indices(market=None) to inspect available codes.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|index|str \| int \| InstrumentRef|required|Exact index code (string/int/InstrumentRef) or exact normalized catalog name. No first-match guess.|
|market|Market \| str \| None|<Market.TSE: 'TSE'>|TSE/IFB/BASE enum or documented string. Support depends on endpoint; index/overview support TSE/IFB only. None never certifies historical coverage.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError, UnsupportedCapabilityError, PointInTimeUnavailableError, CoverageError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_index_history

```python
get_index_history(index: 'str | int | InstrumentRef', *, market: 'Market | str | None' = <Market.TSE: 'TSE'>, start: 'DateLike | None' = None, end: 'DateLike | None' = None, calendar: 'Calendar' = 'gregorian', include_jdate: 'bool' = False, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Return daily index close/high/low in points, ascending with inclusive date filtering. Open and volume are not invented. A full response is fetched before local filtering.

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
    Return daily index close/high/low in points, ascending with inclusive date filtering. Open and volume are not invented. A full response is fetched before local filtering.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|index|str \| int \| InstrumentRef|required|Exact index code (string/int/InstrumentRef) or exact normalized catalog name. No first-match guess.|
|market|Market \| str \| None|<Market.TSE: 'TSE'>|TSE/IFB/BASE enum or documented string. Support depends on endpoint; index/overview support TSE/IFB only. None never certifies historical coverage.|
|start|DateLike \| None|None|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|DateLike \| None|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|Calendar|'gregorian'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|include_jdate|bool|False|Add a textual Jalali date column. It does not change the primary Gregorian date column.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError, UnsupportedCapabilityError, PointInTimeUnavailableError, CoverageError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_index_intraday

```python
get_index_intraday(index: 'str | int | InstrumentRef', *, market: 'Market | str | None' = <Market.TSE: 'TSE'>, day: 'DateLike | None' = None, calendar: 'Calendar' = 'gregorian', include_jdate: 'bool' = False, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Return index observations for the latest session available from the public endpoint. day=None only; selecting a historical session is not supported and raises before HTTP. Equal-time points preserve source order.

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
    Return index observations for the latest session available from the public endpoint. day=None only; selecting a historical session is not supported and raises before HTTP. Equal-time points preserve source order.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|index|str \| int \| InstrumentRef|required|Exact index code (string/int/InstrumentRef) or exact normalized catalog name. No first-match guess.|
|market|Market \| str \| None|<Market.TSE: 'TSE'>|TSE/IFB/BASE enum or documented string. Support depends on endpoint; index/overview support TSE/IFB only. None never certifies historical coverage.|
|day|DateLike \| None|None|Optional explicit single Gregorian/Jalali day; latest intraday index endpoint only supports None.|
|calendar|Calendar|'gregorian'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|include_jdate|bool|False|Add a textual Jalali date column. It does not change the primary Gregorian date column.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError, UnsupportedCapabilityError, PointInTimeUnavailableError, CoverageError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_index_members

```python
get_index_members(index: 'str | int | InstrumentRef', *, market: 'Market | str | None' = <Market.TSE: 'TSE'>, as_of: 'DateLike | None' = None, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Return current constituent quotes, not historical membership or index weights. as_of is unsupported and raises before HTTP. Quote dates are not membership effective dates.

Args:
    index (str | int | InstrumentRef): Exact index identifier/name; ambiguous results must not be selected silently.
    market (Market | str | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: Market.TSE.
    as_of (DateLike | None): See the function signature and related source validation for the accepted structure. Default: None.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Return current constituent quotes, not historical membership or index weights. as_of is unsupported and raises before HTTP. Quote dates are not membership effective dates.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|index|str \| int \| InstrumentRef|required|Exact index code (string/int/InstrumentRef) or exact normalized catalog name. No first-match guess.|
|market|Market \| str \| None|<Market.TSE: 'TSE'>|TSE/IFB/BASE enum or documented string. Support depends on endpoint; index/overview support TSE/IFB only. None never certifies historical coverage.|
|as_of|DateLike \| None|None|Only None is supported; historical membership raises before HTTP.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError, UnsupportedCapabilityError, PointInTimeUnavailableError, CoverageError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_index_impact

```python
get_index_impact(*, market: 'Market | str' = <Market.TSE: 'TSE'>, limit: 'int' = 7, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

EXPERIMENTAL: fetch the reported total-market index-effect records and preserve every source field in source_fields. impact_points/unit remain unknown until the live economic mapping is verified. This does not compute index impact or address arbitrary indices.

Args:
    market (Market | str): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: Market.TSE.
    limit (int): Maximum returned/displayed matches; None retains all eligible rows. Not necessarily remote pagination. Default: 7.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    EXPERIMENTAL: fetch the reported total-market index-effect records and preserve every source field in source_fields. impact_points/unit remain unknown until the live economic mapping is verified. This does not compute index impact or address arbitrary indices.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|market|Market \| str|<Market.TSE: 'TSE'>|TSE/IFB/BASE enum or documented string. Support depends on endpoint; index/overview support TSE/IFB only. None never certifies historical coverage.|
|limit|int|7|Requested server output bound; not a coverage guarantee. Index impact other than the reviewed limit 7 is unverified.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError, UnsupportedCapabilityError, PointInTimeUnavailableError, CoverageError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## watch_market

```python
watch_market(*, interval: 'float' = 10.0, max_updates: 'int | None' = 10, market: 'Market | str | None' = None, include_order_book: 'bool' = False, include_client_types: 'bool' = False, show_traded: 'bool' = False, backend: 'str' = 'auto') -> 'Iterator[pd.DataFrame]'
```

Yield freshly fetched full snapshots with bounded polling, not WebSocket deltas.

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
    or interrupt execution to stop; exceptions propagate, no infinite retry.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|interval|float|10.0|Polling sleep seconds after the previous returned snapshot; local minimum 1 second, not an exchange limit.|
|max_updates|int \| None|10|Maximum yielded snapshots (default 10); None explicitly opts into indefinite polling.|
|market|Market \| str \| None|None|TSE/IFB/BASE enum or documented string. Support depends on endpoint; index/overview support TSE/IFB only. None never certifies historical coverage.|
|include_order_book|bool|False|Add reported depth 1..5 columns with separate provenance; no forward fill.|
|include_client_types|bool|False|Fetch and join a separate bulk response by exact ID; timestamps may be absent/different.|
|show_traded|bool|False|Return only rows with a reported positive trade_count. Unknown is not treated as proof of no trading.|
|backend|str|'auto'|auto/json/legacy; auto uses legacy only after valid empty JSON, not after auth/HTTP/schema errors.|

**Returns:** Iterator[pd.DataFrame]
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError, UnsupportedCapabilityError, PointInTimeUnavailableError, CoverageError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** True

## get_index_history_many

```python
get_index_history_many(indices: 'Sequence[str | int | InstrumentRef] | pd.Series | pd.Index | np.ndarray', *, market: 'Market | str | None' = <Market.TSE: 'TSE'>, start: 'DateLike | None' = None, end: 'DateLike | None' = None, calendar: 'Calendar' = 'gregorian', include_jdate: 'bool' = False, on_error: 'str' = 'raise', policy: 'FetchPolicy | str | None' = None) -> 'BatchFrames'
```

Sequential ordered batch with data/errors/requests tables. Input duplicates.

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
    partial_result; collect reports per-item errors without claiming completeness.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|indices|Sequence[str \| int \| InstrumentRef] \| pd.Series \| pd.Index \| np.ndarray|required|Ordered index names/codes, including Series/Index or a one-dimensional array; duplicates preserved.|
|market|Market \| str \| None|<Market.TSE: 'TSE'>|TSE/IFB/BASE enum or documented string. Support depends on endpoint; index/overview support TSE/IFB only. None never certifies historical coverage.|
|start|DateLike \| None|None|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|DateLike \| None|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|Calendar|'gregorian'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|include_jdate|bool|False|Add a textual Jalali date column. It does not change the primary Gregorian date column.|
|on_error|str|'raise'|'raise' stops with partial_result; 'collect' records errors without losing other inputs.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** BatchFrames
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError, UnsupportedCapabilityError, PointInTimeUnavailableError, CoverageError, BatchDataError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_adjustments

```python
get_adjustments(instrument: 'InstrumentLike', *, start: 'DateLike | None' = None, end: 'DateLike | None' = None, calendar: 'Calendar' = 'gregorian', include_jdate: 'bool' = False, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Reported price-adjustment events and price ratios. Reasons and complete corporate-action coverage are unknown; this is not a total-return algorithm.

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
    Reported price-adjustment events and price ratios. Reasons and complete corporate-action coverage are unknown; this is not a total-return algorithm.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|instrument|InstrumentLike|required|Symbol string or explicit InstrumentRef. A bare numeric string is not inferred as ins_code.|
|start|DateLike \| None|None|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|DateLike \| None|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|Calendar|'gregorian'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|include_jdate|bool|False|Add a textual Jalali date column. It does not change the primary Gregorian date column.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_share_capital_history

```python
get_share_capital_history(instrument: 'InstrumentLike', *, start: 'DateLike | None' = None, end: 'DateLike | None' = None, calendar: 'Calendar' = 'gregorian', include_jdate: 'bool' = False, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Reported old/new share counts, not legal capital-increase classifications. All observed rows are retained.

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
    Reported old/new share counts, not legal capital-increase classifications. All observed rows are retained.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|instrument|InstrumentLike|required|Symbol string or explicit InstrumentRef. A bare numeric string is not inferred as ins_code.|
|start|DateLike \| None|None|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|DateLike \| None|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|Calendar|'gregorian'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|include_jdate|bool|False|Add a textual Jalali date column. It does not change the primary Gregorian date column.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_dividends

```python
get_dividends(instrument: 'InstrumentLike', *, start: 'DateLike | None' = None, end: 'DateLike | None' = None, calendar: 'Calendar' = 'gregorian', include_jdate: 'bool' = False, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Dividend history from the legacy text route. Payment/ex dates are not inferred; failed or HTML responses raise.

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
    Dividend history from the legacy text route. Payment/ex dates are not inferred; failed or HTML responses raise.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|instrument|InstrumentLike|required|Symbol string or explicit InstrumentRef. A bare numeric string is not inferred as ins_code.|
|start|DateLike \| None|None|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|DateLike \| None|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|Calendar|'gregorian'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|include_jdate|bool|False|Add a textual Jalali date column. It does not change the primary Gregorian date column.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_adjusted_history

```python
get_adjusted_history(instrument: 'InstrumentLike', *, start: 'DateLike | None' = None, end: 'DateLike | None' = None, calendar: 'Calendar' = 'gregorian', include_jdate: 'bool' = False, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Source-adjusted chart history, separate from raw history. Source method tsetmc_chart_a1; anchor is the last returned date. No total-return or point-in-time guarantee. Missing turnover/count/reference price stay missing.

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
    Source-adjusted chart history, separate from raw history. Source method tsetmc_chart_a1; anchor is the last returned date. No total-return or point-in-time guarantee. Missing turnover/count/reference price stay missing.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|instrument|InstrumentLike|required|Symbol string or explicit InstrumentRef. A bare numeric string is not inferred as ins_code.|
|start|DateLike \| None|None|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|DateLike \| None|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|Calendar|'gregorian'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|include_jdate|bool|False|Add a textual Jalali date column. It does not change the primary Gregorian date column.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_shareholders

```python
get_shareholders(instrument: 'InstrumentLike', *, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Latest reported major shareholders. Empty does not prove that no major holders exist.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Latest reported major shareholders. Empty does not prove that no major holders exist.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|instrument|InstrumentLike|required|Symbol string or explicit InstrumentRef. A bare numeric string is not inferred as ins_code.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_shareholder_history

```python
get_shareholder_history(instrument: 'InstrumentLike', holder_id: 'str | int', *, days: 'int' = 90, start: 'DateLike | None' = None, end: 'DateLike | None' = None, calendar: 'Calendar' = 'gregorian', include_jdate: 'bool' = False, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

History of one holder of one instrument; holder_id comes from get_shareholders, not the holding_ref. days is 1..3650; date filtering is local.

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
    History of one holder of one instrument; holder_id comes from get_shareholders, not the holding_ref. days is 1..3650; date filtering is local.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|instrument|InstrumentLike|required|Symbol string or explicit InstrumentRef. A bare numeric string is not inferred as ins_code.|
|holder_id|str \| int|required|Validated setting; see the constructor docstring and configuration source.|
|days|int|90|Validated setting; see the constructor docstring and configuration source.|
|start|DateLike \| None|None|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|DateLike \| None|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|Calendar|'gregorian'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|include_jdate|bool|False|Add a textual Jalali date column. It does not change the primary Gregorian date column.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_disclosures

```python
get_disclosures(instrument: 'InstrumentLike', *, limit: 'int' = 20, start: 'DateLike | None' = None, end: 'DateLike | None' = None, calendar: 'Calendar' = 'gregorian', include_jdate: 'bool' = False, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Disclosure metadata linked by TSETMC. Does not download or parse financial-statement attachments. limit is 1..1000; dates filter the returned subset only.

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
    Disclosure metadata linked by TSETMC. Does not download or parse financial-statement attachments. limit is 1..1000; dates filter the returned subset only.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|instrument|InstrumentLike|required|Symbol string or explicit InstrumentRef. A bare numeric string is not inferred as ins_code.|
|limit|int|20|Positive local display limit; None keeps all returned matches. Does not change server paging.|
|start|DateLike \| None|None|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|DateLike \| None|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|Calendar|'gregorian'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|include_jdate|bool|False|Add a textual Jalali date column. It does not change the primary Gregorian date column.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_messages

```python
get_messages(instrument: 'InstrumentLike', *, start: 'DateLike | None' = None, end: 'DateLike | None' = None, calendar: 'Calendar' = 'gregorian', include_jdate: 'bool' = False, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Reported instrument supervisor messages, with source timestamp and original text.

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
    Reported instrument supervisor messages, with source timestamp and original text.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|instrument|InstrumentLike|required|Symbol string or explicit InstrumentRef. A bare numeric string is not inferred as ins_code.|
|start|DateLike \| None|None|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|DateLike \| None|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|Calendar|'gregorian'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|include_jdate|bool|False|Add a textual Jalali date column. It does not change the primary Gregorian date column.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_trades

```python
get_trades(instrument: 'InstrumentLike', *, day: 'DateLike | None' = None, start: 'DateLike | None' = None, end: 'DateLike | None' = None, calendar: 'Calendar' = 'gregorian', include_jdate: 'bool' = False, max_days: 'int' = 31, cancellation: 'str' = 'as_reported', policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Reported executions, current or per explicit calendar day. Same-second trades are not deduplicated. Cancellation remains unknown; only as_reported is supported. Max 31 days by default, configurable up to 366.

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
    Reported executions, current or per explicit calendar day. Same-second trades are not deduplicated. Cancellation remains unknown; only as_reported is supported. Max 31 days by default, configurable up to 366.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|instrument|InstrumentLike|required|Symbol string or explicit InstrumentRef. A bare numeric string is not inferred as ins_code.|
|day|DateLike \| None|None|Optional explicit single Gregorian/Jalali day; latest intraday index endpoint only supports None.|
|start|DateLike \| None|None|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|DateLike \| None|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|Calendar|'gregorian'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|include_jdate|bool|False|Add a textual Jalali date column. It does not change the primary Gregorian date column.|
|max_days|int|31|Validated setting; see the constructor docstring and configuration source.|
|cancellation|str|'as_reported'|Validated setting; see the constructor docstring and configuration source.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_order_book

```python
get_order_book(instrument: 'InstrumentLike', *, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Current reported best limits (up to five depths), not a full exchange order book. Missing source timestamps stay missing.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Current reported best limits (up to five depths), not a full exchange order book. Missing source timestamps stay missing.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|instrument|InstrumentLike|required|Symbol string or explicit InstrumentRef. A bare numeric string is not inferred as ins_code.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_order_book_history

```python
get_order_book_history(instrument: 'InstrumentLike', *, start: 'DateLike', end: 'DateLike | None' = None, calendar: 'Calendar' = 'gregorian', include_jdate: 'bool' = False, max_days: 'int' = 31, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Historical best-limit updates. Sequence/reference and source position are preserved. No fill-forward or fictional complete snapshots; empty days do not prove holidays.

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
    Historical best-limit updates. Sequence/reference and source position are preserved. No fill-forward or fictional complete snapshots; empty days do not prove holidays.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|instrument|InstrumentLike|required|Symbol string or explicit InstrumentRef. A bare numeric string is not inferred as ins_code.|
|start|DateLike|required|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|DateLike \| None|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|Calendar|'gregorian'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|include_jdate|bool|False|Add a textual Jalali date column. It does not change the primary Gregorian date column.|
|max_days|int|31|Validated setting; see the constructor docstring and configuration source.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_instrument_states

```python
get_instrument_states(instrument: 'InstrumentLike', *, day: 'DateLike | None' = None, calendar: 'Calendar' = 'gregorian', include_jdate: 'bool' = False, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Reported state/price-limit records for one day. No day means the last trading date reported by the quote, not today. Empty is not interpreted as open/unrestricted.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    day (DateLike | None): See the function signature and related source validation for the accepted structure. Default: None.
    calendar (Calendar): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'gregorian'.
    include_jdate (bool): True adds a Jalali date column; False does not. This does not convert the underlying Gregorian date column. Default: False.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Reported state/price-limit records for one day. No day means the last trading date reported by the quote, not today. Empty is not interpreted as open/unrestricted.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|instrument|InstrumentLike|required|Symbol string or explicit InstrumentRef. A bare numeric string is not inferred as ins_code.|
|day|DateLike \| None|None|Optional explicit single Gregorian/Jalali day; latest intraday index endpoint only supports None.|
|calendar|Calendar|'gregorian'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|include_jdate|bool|False|Add a textual Jalali date column. It does not change the primary Gregorian date column.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_thresholds

```python
get_thresholds(instrument: 'InstrumentLike', *, day: 'DateLike | None' = None, calendar: 'Calendar' = 'gregorian', include_jdate: 'bool' = False, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Reported state/price-limit records for one day. No day means the last trading date reported by the quote, not today. Empty is not interpreted as open/unrestricted.

Args:
    instrument (InstrumentLike): Symbol text, InstrumentRef, or a DataFrame returned by tse.assets(); lists of symbols/DataFrames are accepted by history and price. None when ins_code is supplied.
    day (DateLike | None): See the function signature and related source validation for the accepted structure. Default: None.
    calendar (Calendar): Allowed "auto", "gregorian", "jalali" on friendly APIs, depending on function. Date/datetime values represent Gregorian dates; string interpretation follows calendar. Default: 'gregorian'.
    include_jdate (bool): True adds a Jalali date column; False does not. This does not convert the underlying Gregorian date column. Default: False.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Reported state/price-limit records for one day. No day means the last trading date reported by the quote, not today. Empty is not interpreted as open/unrestricted.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|instrument|InstrumentLike|required|Symbol string or explicit InstrumentRef. A bare numeric string is not inferred as ins_code.|
|day|DateLike \| None|None|Optional explicit single Gregorian/Jalali day; latest intraday index endpoint only supports None.|
|calendar|Calendar|'gregorian'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|include_jdate|bool|False|Add a textual Jalali date column. It does not change the primary Gregorian date column.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_boards

```python
get_boards(*, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Board codes from the reviewed reference HTML table. A replaced page raises rather than returning a false empty registry.

Args:
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Board codes from the reviewed reference HTML table. A replaced page raises rather than returning a false empty registry.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_instruments

```python
get_instruments(*, market: 'Market | str | None' = None, include_inactive: 'bool' = False, changed_since: 'DateLike | None' = None, backend: 'str' = 'auto', policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Current observed watch instrument list only. include_inactive=True and changed_since require a historical registry and raise; suspended instruments may still be in the current watch.

Args:
    market (Market | str | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: None.
    include_inactive (bool): Whether to include instruments without a reported active status. Default: False.
    changed_since (DateLike | None): See the function signature and related source validation for the accepted structure. Default: None.
    backend (str): Allowed "auto", "json", "legacy" where supported; auto fallback is conditional rather than a generic retry on every error. Default: 'auto'.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Current observed watch instrument list only. include_inactive=True and changed_since require a historical registry and raise; suspended instruments may still be in the current watch.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|market|Market \| str \| None|None|TSE/IFB/BASE enum or documented string. Support depends on endpoint; index/overview support TSE/IFB only. None never certifies historical coverage.|
|include_inactive|bool|False|Include inactive/unknown entries. False requires verified active status from the response.|
|changed_since|DateLike \| None|None|Validated setting; see the constructor docstring and configuration source.|
|backend|str|'auto'|auto/json/legacy; auto uses legacy only after valid empty JSON, not after auth/HTTP/schema errors.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_funds

```python
get_funds(category: 'str | None' = 'stock', *, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Registered funds by category name/code; None explicitly fetches the ten reviewed categories. registration_no is not an ins_code.

Args:
    category (str | None): See the function signature and related source validation for the accepted structure. Default: 'stock'.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Registered funds by category name/code; None explicitly fetches the ten reviewed categories. registration_no is not an ins_code.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|category|str \| None|'stock'|Validated setting; see the constructor docstring and configuration source.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_fund

```python
get_fund(registration_no: 'str | int', *, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Fund detail as a one-row frame with raw fields retained. Use the registration_no from get_funds.

Args:
    registration_no (str | int): See the function signature and related source validation for the accepted structure.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Fund detail as a one-row frame with raw fields retained. Use the registration_no from get_funds.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|registration_no|str \| int|required|Validated setting; see the constructor docstring and configuration source.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_fund_nav_history

```python
get_fund_nav_history(registration_no: 'str | int', *, start: 'DateLike | None' = None, end: 'DateLike | None' = None, calendar: 'Calendar' = 'gregorian', include_jdate: 'bool' = False, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Reported NAV stats; unit/currency not supplied by source remain unknown, not assumed from stock prices.

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
    Reported NAV stats; unit/currency not supplied by source remain unknown, not assumed from stock prices.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|registration_no|str \| int|required|Validated setting; see the constructor docstring and configuration source.|
|start|DateLike \| None|None|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|DateLike \| None|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|Calendar|'gregorian'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|include_jdate|bool|False|Add a textual Jalali date column. It does not change the primary Gregorian date column.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_options

```python
get_options(underlying: 'InstrumentLike | None' = None, *, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Public option-chain pairs expanded into one row per put/call contract. Underlying filter is optional and local. No option pricing or inferred Greeks.

Args:
    underlying (InstrumentLike | None): See the function signature and related source validation for the accepted structure. Default: None.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Public option-chain pairs expanded into one row per put/call contract. Underlying filter is optional and local. No option pricing or inferred Greeks.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|underlying|InstrumentLike \| None|None|Validated setting; see the constructor docstring and configuration source.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_futures

```python
get_futures(*, source: 'str' = 'tse_exchange', policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Current futures snapshot from the separate public tse.ir exchange gateway (not TSETMC CDN). Source must be tse_exchange. Fields with unverified meanings remain in source_fields. No history or commodity-exchange completeness guarantee.

Args:
    source (str): See the function signature and related source validation for the accepted structure. Default: 'tse_exchange'.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Current futures snapshot from the separate public tse.ir exchange gateway (not TSETMC CDN). Source must be tse_exchange. Fields with unverified meanings remain in source_fields. No history or commodity-exchange completeness guarantee.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|source|str|'tse_exchange'|Only 'public' is supported; official authentication is not pretended to work.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## history

```python
history(assets=None, *, ins_code=None, symbol=None, start=None, end=None, calendar='auto', adjustment='none', include_jdate=False, policy=None, on_multiple='all', on_conflict='error', on_error='collect') -> 'pd.DataFrame'
```

Return unified daily history for symbol, explicit code, instrument DataFrame or list.

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
    >>> data.attrs.get("pydara", {}).get("errors")

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|assets|documented in source|None|Validated setting; see the constructor docstring and configuration source.|
|ins_code|documented in source|None|Exact positive integer identifier; on bulk key statistics this is a local filter.|
|symbol|documented in source|None|Validated setting; see the constructor docstring and configuration source.|
|start|documented in source|None|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|documented in source|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|documented in source|'auto'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|adjustment|documented in source|'none'|Only 'none' is implemented; 'source' raises UnsupportedCapabilityError, never a fabricated adjusted series.|
|include_jdate|documented in source|False|Add a textual Jalali date column. It does not change the primary Gregorian date column.|
|policy|documented in source|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|
|on_multiple|documented in source|'all'|Validated setting; see the constructor docstring and configuration source.|
|on_conflict|documented in source|'error'|Validated setting; see the constructor docstring and configuration source.|
|on_error|documented in source|'collect'|'raise' stops with partial_result; 'collect' records errors without losing other inputs.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** True

## market

```python
market(*, market: 'Market | str | None' = None, include_order_book: 'bool' = False, include_client_types: 'bool' = False, backend: 'str' = 'auto', policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Simple alias for get_market_watch; no financial analysis.

Args:
    market (Market | str | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: None.
    include_order_book (bool): Include order-book observations as available from the provider (not inferred). Default: False.
    include_client_types (bool): Include separate real/legal client types data when the source supports it. Default: False.
    backend (str): Allowed "auto", "json", "legacy" where supported; auto fallback is conditional rather than a generic retry on every error. Default: 'auto'.
    policy (FetchPolicy | str | None): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Simple alias for get_market_watch; no financial analysis.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|market|Market \| str \| None|None|TSE/IFB/BASE enum or documented string. Support depends on endpoint; index/overview support TSE/IFB only. None never certifies historical coverage.|
|include_order_book|bool|False|Add reported depth 1..5 columns with separate provenance; no forward fill.|
|include_client_types|bool|False|Fetch and join a separate bulk response by exact ID; timestamps may be absent/different.|
|backend|str|'auto'|auto/json/legacy; auto uses legacy only after valid empty JSON, not after auth/HTTP/schema errors.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** True

## index_history

```python
index_history(index: 'str | int', *, start: 'DateLike | None' = None, end: 'DateLike | None' = None, calendar: 'str' = 'auto', include_jdate: 'bool' = False, market: 'Market | str | None' = <Market.TSE: 'TSE'>, policy: 'FetchPolicy | str | None' = None) -> 'pd.DataFrame'
```

Simple index-history alias with explicit auto-calendar policy.

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
    Simple index-history alias with explicit auto-calendar policy.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|index|str \| int|required|Exact index code (string/int/InstrumentRef) or exact normalized catalog name. No first-match guess.|
|start|DateLike \| None|None|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|DateLike \| None|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|str|'auto'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|include_jdate|bool|False|Add a textual Jalali date column. It does not change the primary Gregorian date column.|
|market|Market \| str \| None|<Market.TSE: 'TSE'>|TSE/IFB/BASE enum or documented string. Support depends on endpoint; index/overview support TSE/IFB only. None never certifies historical coverage.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** True

## datasets

```python
datasets() -> 'pd.DataFrame'
```

List locally stored response families, without HTTP.

|Parameter|Type|Default|Meaning|
|---|---|---|---|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** True

## storage_info

```python
storage_info() -> 'pd.DataFrame'
```

Inspect local storage health and file sizes, without HTTP.

|Parameter|Type|Default|Meaning|
|---|---|---|---|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** True

## query

```python
query(instrument: 'InstrumentLike', *, dataset: 'str' = 'history', start: 'DateLike | None' = None, end: 'DateLike | None' = None, calendar: 'str' = 'auto', include_jdate: 'bool' = False) -> 'pd.DataFrame'
```

Read locally stored data only. Never a live request; cached results retain time and stale flags.

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
    Read locally stored data only. Never a live request; cached results retain time and stale flags.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|instrument|InstrumentLike|required|Symbol string or explicit InstrumentRef. A bare numeric string is not inferred as ins_code.|
|dataset|str|'history'|Name of a stored table archive inside a snapshot SQLite database.|
|start|DateLike \| None|None|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|DateLike \| None|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|str|'auto'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|include_jdate|bool|False|Add a textual Jalali date column. It does not change the primary Gregorian date column.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** True

## backup

```python
backup(path: 'str | Path', *, overwrite: 'bool' = False, timeout: 'float' = 30.0, flush: 'bool' = True) -> 'dict'
```

Explicit SQLite backup with WAL consistency, integrity check and timeout. Does not change the original database.

Args:
    path (str | Path): See the function signature and related source validation for the accepted structure.
    overwrite (bool): See the function signature and related source validation for the accepted structure. Default: False.
    timeout (float): See the function signature and related source validation for the accepted structure. Default: 30.0.
    flush (bool): See the function signature and related source validation for the accepted structure. Default: True.

Returns:
    dict: See the API reference for columns, metadata and error reporting.

Notes:
    Explicit SQLite backup with WAL consistency, integrity check and timeout. Does not change the original database.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|path|str \| Path|required|Nonempty path string or pathlib.Path, not the working cache database for archive exports.|
|overwrite|bool|False|Explicit consent to replace this export path/dataset. Default False.|
|timeout|float|30.0|Bounded seconds for the explicit storage wait; not an exchange availability guarantee.|
|flush|bool|True|Validated setting; see the constructor docstring and configuration source.|

**Returns:** dict
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** True

## download

```python
download(symbols, *, dataset: 'str' = 'history', start: 'DateLike | None' = None, end: 'DateLike | None' = None, calendar: 'str' = 'auto', update: 'bool' = True, store: 'bool | None' = None, on_error: 'str' = 'collect', checkpoint_dir: 'str | Path | None' = None, resume: 'bool' = True, resume_max_age: 'float' = 3600.0, include_jdate: 'bool' = False, progress=None, policy: 'FetchPolicy | str | None' = None) -> 'BatchFrames'
```

Ordered data job with reports and opt-in disk checkpoints. Uses existing bounded network budget; partial success is explicit.

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
    Ordered data job with reports and opt-in disk checkpoints. Uses existing bounded network budget; partial success is explicit.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|symbols|documented in source|required|Validated setting; see the constructor docstring and configuration source.|
|dataset|str|'history'|Name of a stored table archive inside a snapshot SQLite database.|
|start|DateLike \| None|None|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|DateLike \| None|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|str|'auto'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|update|bool|True|Validated setting; see the constructor docstring and configuration source.|
|store|bool \| None|None|Validated setting; see the constructor docstring and configuration source.|
|on_error|str|'collect'|'raise' stops with partial_result; 'collect' records errors without losing other inputs.|
|checkpoint_dir|str \| Path \| None|None|Validated setting; see the constructor docstring and configuration source.|
|resume|bool|True|Validated setting; see the constructor docstring and configuration source.|
|resume_max_age|float|3600.0|Validated setting; see the constructor docstring and configuration source.|
|include_jdate|bool|False|Add a textual Jalali date column. It does not change the primary Gregorian date column.|
|progress|documented in source|None|Validated setting; see the constructor docstring and configuration source.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** BatchFrames
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** True

## update

```python
update(symbols, *, start: 'DateLike | None' = None, end: 'DateLike | None' = None, calendar: 'str' = 'auto', on_error: 'str' = 'collect', checkpoint_dir: 'str | Path | None' = None, resume: 'bool' = False, progress=None) -> 'BatchFrames'
```

Update raw histories with overlap/correction handling. Default resume=False checks anew rather than reusing a job snapshot.

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
    Update raw histories with overlap/correction handling. Default resume=False checks anew rather than reusing a job snapshot.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|symbols|documented in source|required|Validated setting; see the constructor docstring and configuration source.|
|start|DateLike \| None|None|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|DateLike \| None|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|str|'auto'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|on_error|str|'collect'|'raise' stops with partial_result; 'collect' records errors without losing other inputs.|
|checkpoint_dir|str \| Path \| None|None|Validated setting; see the constructor docstring and configuration source.|
|resume|bool|False|Validated setting; see the constructor docstring and configuration source.|
|progress|documented in source|None|Validated setting; see the constructor docstring and configuration source.|

**Returns:** BatchFrames
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** True

## download_market

```python
download_market(*, dataset: 'str' = 'history', market: 'Market | str | None' = None, limit: 'int' = 100, start: 'DateLike | None' = None, end: 'DateLike | None' = None, calendar: 'str' = 'auto', dry_run: 'bool' = True, on_error: 'str' = 'collect', checkpoint_dir: 'str | Path | None' = None) -> 'pd.DataFrame | BatchFrames'
```

Plan bounded downloads for the current watch universe. dry_run=True performs only watch retrieval; historical universe is not reconstructed.

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
    Plan bounded downloads for the current watch universe. dry_run=True performs only watch retrieval; historical universe is not reconstructed.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|dataset|str|'history'|Name of a stored table archive inside a snapshot SQLite database.|
|market|Market \| str \| None|None|TSE/IFB/BASE enum or documented string. Support depends on endpoint; index/overview support TSE/IFB only. None never certifies historical coverage.|
|limit|int|100|Positive local display limit; None keeps all returned matches. Does not change server paging.|
|start|DateLike \| None|None|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|DateLike \| None|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|str|'auto'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|dry_run|bool|True|Validated setting; see the constructor docstring and configuration source.|
|on_error|str|'collect'|'raise' stops with partial_result; 'collect' records errors without losing other inputs.|
|checkpoint_dir|str \| Path \| None|None|Validated setting; see the constructor docstring and configuration source.|

**Returns:** pd.DataFrame | BatchFrames
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** True

## get_trades_many

```python
get_trades_many(instruments, *, start, end=None, calendar='gregorian', include_jdate=False, on_error='collect', policy=None) -> 'BatchFrames'
```

Trades for multiple inputs with explicit errors, not silent dropping.

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
    Trades for multiple inputs with explicit errors, not silent dropping.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|instruments|documented in source|required|Nonempty ordered list/tuple, Pandas Series/Index or a one-dimensional NumPy array. Duplicates preserved; nulls rejected.|
|start|documented in source|required|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|documented in source|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|documented in source|'gregorian'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|include_jdate|documented in source|False|Add a textual Jalali date column. It does not change the primary Gregorian date column.|
|on_error|documented in source|'collect'|'raise' stops with partial_result; 'collect' records errors without losing other inputs.|
|policy|documented in source|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** BatchFrames
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## get_order_book_updates

```python
get_order_book_updates(instrument, *, start, end=None, calendar='gregorian', include_jdate=False, max_days=31, policy=None) -> 'pd.DataFrame'
```

Historical best-limit updates, not full snapshots.

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
    Historical best-limit updates, not full snapshots.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|instrument|documented in source|required|Symbol string or explicit InstrumentRef. A bare numeric string is not inferred as ins_code.|
|start|documented in source|required|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|documented in source|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|documented in source|'gregorian'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|include_jdate|documented in source|False|Add a textual Jalali date column. It does not change the primary Gregorian date column.|
|max_days|documented in source|31|Validated setting; see the constructor docstring and configuration source.|
|policy|documented in source|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library, HTTPX for network, platformdirs, tzdata, optional best-effort SQLite
**AsyncClient counterpart:** True

## export

```python
export(df: 'pd.DataFrame', path: 'str | Path', *, format: 'str | None' = None, dataset: 'str' = 'user_data', metadata: 'bool' = True, overwrite: 'bool' = False, safe_text: 'bool' = True) -> 'WriteReceipt'
```

Save a self-describing snapshot; return only after successful commit.

``metadata=False`` omits df.attrs, not structural type/checksum information.
MultiIndex/unsupported object values are rejected. No network requests.
CSV + sidecar replace is not one filesystem transaction: a crash between
replacements is detected by load's SHA256 check, never silently accepted.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|df|pd.DataFrame|required|An ordinary Pandas DataFrame; input is never modified in place by local helpers.|
|path|str \| Path|required|Nonempty path string or pathlib.Path, not the working cache database for archive exports.|
|format|str \| None|None|csv/excel/parquet/sqlite, or None to infer from the supported file suffix.|
|dataset|str|'user_data'|Name of a stored table archive inside a snapshot SQLite database.|
|metadata|bool|True|Keep dataframe attrs as well as structural schema; False omits attrs, not required type/checksum metadata.|
|overwrite|bool|False|Explicit consent to replace this export path/dataset. Default False.|
|safe_text|bool|True|Protect dangerous formula-like text on export; decoding reverses the protection.|

**Returns:** WriteReceipt
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## export_many

```python
export_many(value, directory, *, formats=('csv',), group_by='symbol', overwrite=False, on_error='collect') -> 'pd.DataFrame'
```

Export separate files with safe deterministic filenames; no path traversal.
Returns one receipt/error row per group and format. Does not delete other files.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|value|documented in source|required|Input date or identifier; use the documented constructor to state its kind.|
|directory|documented in source|required|Validated setting; see the constructor docstring and configuration source.|
|formats|documented in source|('csv',)|Validated setting; see the constructor docstring and configuration source.|
|group_by|documented in source|'symbol'|Validated setting; see the constructor docstring and configuration source.|
|overwrite|documented in source|False|Explicit consent to replace this export path/dataset. Default False.|
|on_error|documented in source|'collect'|'raise' stops with partial_result; 'collect' records errors without losing other inputs.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## download_many

```python
download_many(symbols, *, dataset: 'str' = 'history', start: 'DateLike | None' = None, end: 'DateLike | None' = None, calendar: 'str' = 'auto', update: 'bool' = True, store: 'bool | None' = None, on_error: 'str' = 'collect', checkpoint_dir: 'str | Path | None' = None, resume: 'bool' = True, resume_max_age: 'float' = 3600.0, include_jdate: 'bool' = False, progress=None, policy: 'FetchPolicy | str | None' = None) -> 'BatchFrames'
```

Ordered data job with reports and opt-in disk checkpoints. Uses existing bounded network budget; partial success is explicit.

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
    Ordered data job with reports and opt-in disk checkpoints. Uses existing bounded network budget; partial success is explicit.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|symbols|documented in source|required|Validated setting; see the constructor docstring and configuration source.|
|dataset|str|'history'|Name of a stored table archive inside a snapshot SQLite database.|
|start|DateLike \| None|None|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|DateLike \| None|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|str|'auto'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|update|bool|True|Validated setting; see the constructor docstring and configuration source.|
|store|bool \| None|None|Validated setting; see the constructor docstring and configuration source.|
|on_error|str|'collect'|'raise' stops with partial_result; 'collect' records errors without losing other inputs.|
|checkpoint_dir|str \| Path \| None|None|Validated setting; see the constructor docstring and configuration source.|
|resume|bool|True|Validated setting; see the constructor docstring and configuration source.|
|resume_max_age|float|3600.0|Validated setting; see the constructor docstring and configuration source.|
|include_jdate|bool|False|Add a textual Jalali date column. It does not change the primary Gregorian date column.|
|progress|documented in source|None|Validated setting; see the constructor docstring and configuration source.|
|policy|FetchPolicy \| str \| None|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** BatchFrames
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** True

## setup

```python
setup(*, network='environment', allow_direct=False, probe=False, storage=None, data_dir=None, mode=None, numeric=None) -> 'ClientConfig'
```

Configure the lazy facade before use. Explicit network='direct' ignores
environment proxy/CA settings but keeps TLS verification. auto requires a probe
and direct consent. Close an already-used default client first; no hidden reset.
Settings are in-process, not silently written into the user's home directory.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|network|documented in source|'environment'|Validated setting; see the constructor docstring and configuration source.|
|allow_direct|documented in source|False|Validated setting; see the constructor docstring and configuration source.|
|probe|documented in source|False|Validated setting; see the constructor docstring and configuration source.|
|storage|documented in source|None|Boolean enabling the default best-effort local response storage, or None to use config.|
|data_dir|documented in source|None|Directory containing pydara.sqlite3. Does not move or delete old databases.|
|mode|documented in source|None|auto/online/offline; fresh cached responses may be reused in online. FetchPolicy.fresh() bypasses the cache.|
|numeric|documented in source|None|'analysis' gives nullable Float64; 'exact' uses Decimal for price/quantity fields. Identifiers always remain text.|

**Returns:** ClientConfig
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## check_connection

```python
check_connection(*, network='environment', allow_direct=False, timeout=10.0) -> 'pd.DataFrame'
```

Probe one reviewed small endpoint with explicit connection profiles.
network: environment/direct/auto. auto tries direct ONLY when allow_direct=True.
Does not alter configuration, disable certificate validation, or expose proxy URLs.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|network|documented in source|'environment'|Validated setting; see the constructor docstring and configuration source.|
|allow_direct|documented in source|False|Validated setting; see the constructor docstring and configuration source.|
|timeout|documented in source|10.0|Bounded seconds for the explicit storage wait; not an exchange availability guarantee.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## diagnose

```python
diagnose(*, live=False, network='environment', allow_direct=False) -> 'pd.DataFrame'
```

Version/dependency report without network by default; no credentials or proxy URLs.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|live|documented in source|False|Validated setting; see the constructor docstring and configuration source.|
|network|documented in source|'environment'|Validated setting; see the constructor docstring and configuration source.|
|allow_direct|documented in source|False|Validated setting; see the constructor docstring and configuration source.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## to_pandas

```python
to_pandas(value, *, copy=True) -> 'pd.DataFrame'
```

Obtain a caller-owned DataFrame; no automatic import of optional engines.
Supports DataFrame, a PyDara object with to_frame(), records, or BatchFrames.data.
Does not invent provenance for external data.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|value|documented in source|required|Input date or identifier; use the documented constructor to state its kind.|
|copy|documented in source|True|Validated setting; see the constructor docstring and configuration source.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## set_date_index

```python
set_date_index(df: 'pd.DataFrame', *, column='date', calendar='gregorian', by=None, sort=True, verify_unique=True) -> 'pd.DataFrame'
```

Use a date or (ins_code,date) index, preserving identifier strings.
Multi-instrument frames automatically retain ins_code in the index.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|df|pd.DataFrame|required|An ordinary Pandas DataFrame; input is never modified in place by local helpers.|
|column|documented in source|'date'|Validated setting; see the constructor docstring and configuration source.|
|calendar|documented in source|'gregorian'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|by|documented in source|None|Validated setting; see the constructor docstring and configuration source.|
|sort|documented in source|True|Explicitly reorder normalized rows by request_index/ins_code/date if present. No rows are dropped.|
|verify_unique|documented in source|True|Validated setting; see the constructor docstring and configuration source.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## select

```python
select(df: 'pd.DataFrame', columns=None, *, symbols=None, start=None, end=None, calendar='auto', date_column='date') -> 'pd.DataFrame'
```

Filter without mutating input. Omitted columns retain all evidence.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|df|pd.DataFrame|required|An ordinary Pandas DataFrame; input is never modified in place by local helpers.|
|columns|documented in source|None|Explicit column list/preset for selection or old-name -> new-name mapping for normalization.|
|symbols|documented in source|None|Validated setting; see the constructor docstring and configuration source.|
|start|documented in source|None|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|documented in source|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|documented in source|'auto'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|date_column|documented in source|'date'|Validated setting; see the constructor docstring and configuration source.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## concat

```python
concat(frames: 'Sequence[pd.DataFrame]', *, verify_keys=None) -> 'pd.DataFrame'
```

Concatenate schema-compatible tables, preserving component provenance.
Unknown schema remains unknown. Raw and adjusted data are never mixed silently.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|frames|Sequence[pd.DataFrame]|required|Validated setting; see the constructor docstring and configuration source.|
|verify_keys|documented in source|None|Validated setting; see the constructor docstring and configuration source.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## coverage

```python
coverage(df: 'pd.DataFrame', *, expected_sessions=None, start=None, end=None, calendar='auto') -> 'pd.DataFrame'
```

Observed coverage only. Holidays/halts cannot be inferred from absent rows.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|df|pd.DataFrame|required|An ordinary Pandas DataFrame; input is never modified in place by local helpers.|
|expected_sessions|documented in source|None|Validated setting; see the constructor docstring and configuration source.|
|start|documented in source|None|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|documented in source|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|documented in source|'auto'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## missing_sessions

```python
missing_sessions(df: 'pd.DataFrame', *, expected_sessions, date_column='date') -> 'pd.DataFrame'
```

Compare to caller-supplied sessions. Missing means no record, not a holiday or halt.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|df|pd.DataFrame|required|An ordinary Pandas DataFrame; input is never modified in place by local helpers.|
|expected_sessions|documented in source|required|Validated setting; see the constructor docstring and configuration source.|
|date_column|documented in source|'date'|Validated setting; see the constructor docstring and configuration source.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## compare_sources

```python
compare_sources(left: 'pd.DataFrame', right: 'pd.DataFrame', *, keys=('ins_code', 'date'), columns=None, atol=0.0, rtol=0.0) -> 'pd.DataFrame'
```

Compare two supplied tables without fetching sources or replacing values.
Currency/adjustment mismatch raises. Differences are evidence, not a verdict.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|left|pd.DataFrame|required|Validated setting; see the constructor docstring and configuration source.|
|right|pd.DataFrame|required|Validated setting; see the constructor docstring and configuration source.|
|keys|documented in source|('ins_code', 'date')|Validated setting; see the constructor docstring and configuration source.|
|columns|documented in source|None|Explicit column list/preset for selection or old-name -> new-name mapping for normalization.|
|atol|documented in source|0.0|Validated setting; see the constructor docstring and configuration source.|
|rtol|documented in source|0.0|Validated setting; see the constructor docstring and configuration source.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## examples

```python
examples(name: 'str | None' = None) -> 'pd.DataFrame'
```

Runnable usage snippets. Network examples are labeled; no snippet is executed.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|name|str \| None|None|Optional exact public API name to select from the installed reference.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## help

```python
help(name: 'str | None' = None) -> 'pd.DataFrame'
```

Persian-aware API catalog, returned as a DataFrame without printing or network.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|name|str \| None|None|Optional exact public API name to select from the installed reference.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## columns

```python
columns(schema: 'str' = 'daily_bars', *, numeric='analysis') -> 'pd.DataFrame'
```

Alias for schema_info; no duplicate column registry.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|schema|str|'daily_bars'|An implemented schema name returned by capabilities()/the dataset metadata; includes daily_bars, quote, market_watch, client_types, indices, index_history and related new schemas.|
|numeric|documented in source|'analysis'|'analysis' gives nullable Float64; 'exact' uses Decimal for price/quantity fields. Identifiers always remain text.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## search

```python
search(query: 'str', *, market: 'Market | None' = None, include_inactive: 'bool' = True, limit: 'int | None' = None, policy=None) -> 'pd.DataFrame'
```

Short alias for search_instruments().

Args:
    query (str): Search expression. A query is not a unique identifier and may match many results.
    market (Market | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: None.
    include_inactive (bool): Whether to include instruments without a reported active status. Default: True.
    limit (int | None): Maximum returned/displayed matches; None retains all eligible rows. Not necessarily remote pagination. Default: None.
    policy (Any): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Short alias for search_instruments().

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|query|str|required|Nonempty text to search. Search does not guess which result the user meant.|
|market|Market \| None|None|TSE/IFB/BASE enum or documented string. Support depends on endpoint; index/overview support TSE/IFB only. None never certifies historical coverage.|
|include_inactive|bool|True|Include inactive/unknown entries. False requires verified active status from the response.|
|limit|int \| None|None|Positive local display limit; None keeps all returned matches. Does not change server paging.|
|policy|documented in source|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## catalog

```python
catalog(*, market: 'Market | str | None' = None, include_inactive: 'bool' = False, changed_since: 'DateLike | None' = None, backend: 'str' = 'auto', policy=None) -> 'pd.DataFrame'
```

Short alias for get_instruments(); current watch coverage limitations remain.

Args:
    market (Market | str | None): Exchange/market filter such as Market.TSE, Market.IFB or an implemented market label; supported values may depend on endpoint. Default: None.
    include_inactive (bool): Whether to include instruments without a reported active status. Default: False.
    changed_since (DateLike | None): See the function signature and related source validation for the accepted structure. Default: None.
    backend (str): Allowed "auto", "json", "legacy" where supported; auto fallback is conditional rather than a generic retry on every error. Default: 'auto'.
    policy (Any): FetchPolicy, shorthand "auto", "online" or "offline", or None (configuration default). Cached and offline data must not be described as live. Default: None.

Returns:
    pd.DataFrame: See the API reference for columns, metadata and error reporting.

Notes:
    Short alias for get_instruments(); current watch coverage limitations remain.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|market|Market \| str \| None|None|TSE/IFB/BASE enum or documented string. Support depends on endpoint; index/overview support TSE/IFB only. None never certifies historical coverage.|
|include_inactive|bool|False|Include inactive/unknown entries. False requires verified active status from the response.|
|changed_since|DateLike \| None|None|Validated setting; see the constructor docstring and configuration source.|
|backend|str|'auto'|auto/json/legacy; auto uses legacy only after valid empty JSON, not after auth/HTTP/schema errors.|
|policy|documented in source|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## assets

```python
assets(selector=None, *, ins_code=None, instrument_id=None, company_cisin=None, symbol=None, raw_symbol=None, name=None, markets=None, raw_flow=None, instrument_type=None, currency=None, is_active=None, industry=None, industry_code=None, strict=True, on_multiple='all', on_conflict='error', policy=None) -> 'pd.DataFrame'
```

List or resolve exchange assets, optionally applying source-supported filters.

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

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|selector|documented in source|None|Validated setting; see the constructor docstring and configuration source.|
|ins_code|documented in source|None|Exact positive integer identifier; on bulk key statistics this is a local filter.|
|instrument_id|documented in source|None|Validated setting; see the constructor docstring and configuration source.|
|company_cisin|documented in source|None|Validated setting; see the constructor docstring and configuration source.|
|symbol|documented in source|None|Validated setting; see the constructor docstring and configuration source.|
|raw_symbol|documented in source|None|Validated setting; see the constructor docstring and configuration source.|
|name|documented in source|None|Optional exact public API name to select from the installed reference.|
|markets|documented in source|None|Validated setting; see the constructor docstring and configuration source.|
|raw_flow|documented in source|None|Validated setting; see the constructor docstring and configuration source.|
|instrument_type|documented in source|None|Validated setting; see the constructor docstring and configuration source.|
|currency|documented in source|None|Validated setting; see the constructor docstring and configuration source.|
|is_active|documented in source|None|Validated setting; see the constructor docstring and configuration source.|
|industry|documented in source|None|Validated setting; see the constructor docstring and configuration source.|
|industry_code|documented in source|None|Validated setting; see the constructor docstring and configuration source.|
|strict|documented in source|True|Validated setting; see the constructor docstring and configuration source.|
|on_multiple|documented in source|'all'|Validated setting; see the constructor docstring and configuration source.|
|on_conflict|documented in source|'error'|Validated setting; see the constructor docstring and configuration source.|
|policy|documented in source|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## prices

```python
prices(assets=None, *, ins_code=None, markets=None, include_queues=True, max_quote_fallback=20, on_multiple='all', on_conflict='error', on_error='collect', freshness=None, policy=None) -> 'pd.DataFrame'
```

Receive latest daily quotes and price returns as a one-word-column DataFrame.

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

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|assets|documented in source|None|Validated setting; see the constructor docstring and configuration source.|
|ins_code|documented in source|None|Exact positive integer identifier; on bulk key statistics this is a local filter.|
|markets|documented in source|None|Validated setting; see the constructor docstring and configuration source.|
|include_queues|documented in source|True|Validated setting; see the constructor docstring and configuration source.|
|max_quote_fallback|documented in source|20|Validated setting; see the constructor docstring and configuration source.|
|on_multiple|documented in source|'all'|Validated setting; see the constructor docstring and configuration source.|
|on_conflict|documented in source|'error'|Validated setting; see the constructor docstring and configuration source.|
|on_error|documented in source|'collect'|'raise' stops with partial_result; 'collect' records errors without losing other inputs.|
|freshness|documented in source|None|Explicit FreshnessPolicy, with precedence over policy freshness for quotes.|
|policy|documented in source|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## traders

```python
traders(assets=None, *, ins_code=None, start=None, end=None, day=None, calendar='auto', include_jdate=False, on_multiple='all', on_conflict='error', on_error='collect', policy=None) -> 'pd.DataFrame'
```

Return individual/institutional traders' observed buy/sell activity.

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

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|assets|documented in source|None|Validated setting; see the constructor docstring and configuration source.|
|ins_code|documented in source|None|Exact positive integer identifier; on bulk key statistics this is a local filter.|
|start|documented in source|None|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|documented in source|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|day|documented in source|None|Optional explicit single Gregorian/Jalali day; latest intraday index endpoint only supports None.|
|calendar|documented in source|'auto'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|include_jdate|documented in source|False|Add a textual Jalali date column. It does not change the primary Gregorian date column.|
|on_multiple|documented in source|'all'|Validated setting; see the constructor docstring and configuration source.|
|on_conflict|documented in source|'error'|Validated setting; see the constructor docstring and configuration source.|
|on_error|documented in source|'collect'|'raise' stops with partial_result; 'collect' records errors without losing other inputs.|
|policy|documented in source|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## markets

```python
markets(market=None, *, include_breadth=True, include_queues=True, include_traders=True, include_indices=True, on_error='collect', policy=None) -> 'pd.DataFrame'
```

Return one row per supported market with summary and observed breadth.

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

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|market|documented in source|None|TSE/IFB/BASE enum or documented string. Support depends on endpoint; index/overview support TSE/IFB only. None never certifies historical coverage.|
|include_breadth|documented in source|True|Validated setting; see the constructor docstring and configuration source.|
|include_queues|documented in source|True|Validated setting; see the constructor docstring and configuration source.|
|include_traders|documented in source|True|Validated setting; see the constructor docstring and configuration source.|
|include_indices|documented in source|True|Validated setting; see the constructor docstring and configuration source.|
|on_error|documented in source|'collect'|'raise' stops with partial_result; 'collect' records errors without losing other inputs.|
|policy|documented in source|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## orders

```python
orders(assets=None, *, ins_code=None, markets=None, day=None, start=None, end=None, calendar='auto', include_jdate=False, depth=5, side='all', max_days=31, on_multiple='all', on_conflict='error', on_error='collect', policy=None) -> 'pd.DataFrame'
```

Fetch reported best bid/ask orders and optional historical updates.

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

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|assets|documented in source|None|Validated setting; see the constructor docstring and configuration source.|
|ins_code|documented in source|None|Exact positive integer identifier; on bulk key statistics this is a local filter.|
|markets|documented in source|None|Validated setting; see the constructor docstring and configuration source.|
|day|documented in source|None|Optional explicit single Gregorian/Jalali day; latest intraday index endpoint only supports None.|
|start|documented in source|None|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|documented in source|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|calendar|documented in source|'auto'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|include_jdate|documented in source|False|Add a textual Jalali date column. It does not change the primary Gregorian date column.|
|depth|documented in source|5|Validated setting; see the constructor docstring and configuration source.|
|side|documented in source|'all'|Validated setting; see the constructor docstring and configuration source.|
|max_days|documented in source|31|Validated setting; see the constructor docstring and configuration source.|
|on_multiple|documented in source|'all'|Validated setting; see the constructor docstring and configuration source.|
|on_conflict|documented in source|'error'|Validated setting; see the constructor docstring and configuration source.|
|on_error|documented in source|'collect'|'raise' stops with partial_result; 'collect' records errors without losing other inputs.|
|policy|documented in source|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## trades

```python
trades(assets=None, *, ins_code=None, start=None, end=None, starttime='00:00:00', endtime='23:59:59', calendar='auto', include_jdate=True, max_days=31, on_multiple='all', on_conflict='error', on_error='collect', policy=None, maxassets=20, progress=True, workers=1, checkpoint=None) -> 'pd.DataFrame'
```

Retrieve source-reported execution records in a Tehran-local date/time window.

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

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|assets|documented in source|None|Validated setting; see the constructor docstring and configuration source.|
|ins_code|documented in source|None|Exact positive integer identifier; on bulk key statistics this is a local filter.|
|start|documented in source|None|Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.|
|end|documented in source|None|Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.|
|starttime|documented in source|'00:00:00'|Validated setting; see the constructor docstring and configuration source.|
|endtime|documented in source|'23:59:59'|Validated setting; see the constructor docstring and configuration source.|
|calendar|documented in source|'auto'|'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.|
|include_jdate|documented in source|True|Add a textual Jalali date column. It does not change the primary Gregorian date column.|
|max_days|documented in source|31|Validated setting; see the constructor docstring and configuration source.|
|on_multiple|documented in source|'all'|Validated setting; see the constructor docstring and configuration source.|
|on_conflict|documented in source|'error'|Validated setting; see the constructor docstring and configuration source.|
|on_error|documented in source|'collect'|'raise' stops with partial_result; 'collect' records errors without losing other inputs.|
|policy|documented in source|None|FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.|
|maxassets|documented in source|20|Validated setting; see the constructor docstring and configuration source.|
|progress|documented in source|True|Validated setting; see the constructor docstring and configuration source.|
|workers|documented in source|1|Validated setting; see the constructor docstring and configuration source.|
|checkpoint|documented in source|None|Validated setting; see the constructor docstring and configuration source.|

**Returns:** pd.DataFrame
**Errors:** InvalidArgumentError, NetworkError, ApiError, SchemaMismatchError, DataQualityError, UnknownInstrumentError, AmbiguousInstrumentError, StaleDataError, OfflineDataUnavailableError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## Client

```python
Client(*, config: 'ClientConfig | None' = None, source: 'str | None' = None, mode: 'str | None' = None, storage: 'bool | None' = None, data_dir: 'str | Path | None' = None, numeric: 'str | None' = None, credentials=None, transport: 'httpx.BaseTransport | None' = None, _namespace: 'str' = 'public')
```

Identity, quotes and raw daily history client. Construct freely; close explicitly or use ``with``.

Part 3 adds file interchange and local reconciliation; adjustments, analytics and ML remain deferred.
``transport`` is a test/development hook, not a TSETMC authentication mechanism.
A Client is not intended for concurrent use from multiple OS threads.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|config|ClientConfig \| None|None|Immutable ClientConfig; supplied constructor overrides take precedence.|
|source|str \| None|None|Only 'public' is supported; official authentication is not pretended to work.|
|mode|str \| None|None|auto/online/offline; fresh cached responses may be reused in online. FetchPolicy.fresh() bypasses the cache.|
|storage|bool \| None|None|Boolean enabling the default best-effort local response storage, or None to use config.|
|data_dir|str \| Path \| None|None|Directory containing pydara.sqlite3. Does not move or delete old databases.|
|numeric|str \| None|None|'analysis' gives nullable Float64; 'exact' uses Decimal for price/quantity fields. Identifiers always remain text.|
|credentials|documented in source|None|Reserved for official provider; any non-None value is rejected.|
|transport|httpx.BaseTransport \| None|None|Explicit HTTPX transport test hook. It must never be used as an auth workaround.|
|_namespace|str|'public'|Internal/testing cache namespace; normally leave unchanged.|

**Returns:** Client
**Errors:** ConfigurationError, UnsupportedCapabilityError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## AsyncClient

```python
AsyncClient(*, config: 'ClientConfig | None' = None, source: 'str | None' = None, mode: 'str | None' = None, storage: 'bool | None' = None, data_dir: 'str | Path | None' = None, numeric: 'str | None' = None, credentials=None, transport: 'httpx.AsyncBaseTransport | None' = None, _namespace: 'str' = 'public')
```

Use within one event loop and async context manager. No hidden asyncio.run().

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|config|ClientConfig \| None|None|Immutable ClientConfig; supplied constructor overrides take precedence.|
|source|str \| None|None|Only 'public' is supported; official authentication is not pretended to work.|
|mode|str \| None|None|auto/online/offline; fresh cached responses may be reused in online. FetchPolicy.fresh() bypasses the cache.|
|storage|bool \| None|None|Boolean enabling the default best-effort local response storage, or None to use config.|
|data_dir|str \| Path \| None|None|Directory containing pydara.sqlite3. Does not move or delete old databases.|
|numeric|str \| None|None|'analysis' gives nullable Float64; 'exact' uses Decimal for price/quantity fields. Identifiers always remain text.|
|credentials|documented in source|None|Reserved for official provider; any non-None value is rejected.|
|transport|httpx.AsyncBaseTransport \| None|None|Explicit HTTPX transport test hook. It must never be used as an auth workaround.|
|_namespace|str|'public'|Internal/testing cache namespace; normally leave unchanged.|

**Returns:** AsyncClient
**Errors:** ConfigurationError, UnsupportedCapabilityError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## ClientConfig

```python
ClientConfig(*, source: "Literal['public', 'official']" = 'public', mode: "Literal['auto', 'online', 'offline']" = 'auto', storage: 'StorageConfig | None' = None, network: 'NetworkConfig | None' = None, numeric: "Literal['analysis', 'exact']" = 'analysis', timezone: 'str' = 'Asia/Tehran', strict_schema: 'bool' = True) -> None
```

Combine network, storage, freshness and numeric settings.

This type is part of the documented implementation; consult field annotations and public API contracts for supported values.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|source|Literal['public', 'official']|'public'|Only 'public' is supported; official authentication is not pretended to work.|
|mode|Literal['auto', 'online', 'offline']|'auto'|auto/online/offline; fresh cached responses may be reused in online. FetchPolicy.fresh() bypasses the cache.|
|storage|StorageConfig \| None|None|Boolean enabling the default best-effort local response storage, or None to use config.|
|network|NetworkConfig \| None|None|Validated setting; see the constructor docstring and configuration source.|
|numeric|Literal['analysis', 'exact']|'analysis'|'analysis' gives nullable Float64; 'exact' uses Decimal for price/quantity fields. Identifiers always remain text.|
|timezone|str|'Asia/Tehran'|Explicit timezone for otherwise-naive real timestamps. Daily dates remain timezone-naive.|
|strict_schema|bool|True|Validated setting; see the constructor docstring and configuration source.|

**Returns:** ClientConfig
**Errors:** ConfigurationError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## NetworkConfig

```python
NetworkConfig(*, connect_timeout: 'float' = 5.0, read_timeout: 'float' = 20.0, operation_timeout: 'float' = 60.0, max_concurrency: 'int' = 4, max_retries: 'int' = 2, requests_per_second: 'float' = 0.5, request_budget: 'int' = 100, max_response_bytes: 'int' = 33554432, trust_env: 'bool' = True) -> None
```

Configure HTTP request limits and retry timing.

This type is part of the documented implementation; consult field annotations and public API contracts for supported values.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|connect_timeout|float|5.0|Validated setting; see the constructor docstring and configuration source.|
|read_timeout|float|20.0|Validated setting; see the constructor docstring and configuration source.|
|operation_timeout|float|60.0|Validated setting; see the constructor docstring and configuration source.|
|max_concurrency|int|4|Validated setting; see the constructor docstring and configuration source.|
|max_retries|int|2|Validated setting; see the constructor docstring and configuration source.|
|requests_per_second|float|0.5|Validated setting; see the constructor docstring and configuration source.|
|request_budget|int|100|Validated setting; see the constructor docstring and configuration source.|
|max_response_bytes|int|33554432|Validated setting; see the constructor docstring and configuration source.|
|trust_env|bool|True|Validated setting; see the constructor docstring and configuration source.|

**Returns:** NetworkConfig
**Errors:** ConfigurationError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## StorageConfig

```python
StorageConfig(*, enabled: 'bool' = True, backend: "Literal['sqlite']" = 'sqlite', path: 'str | Path | None' = None, queue_max_jobs: 'int' = 128, queue_max_bytes: 'int' = 67108864, queue_overflow: "Literal['drop_new']" = 'drop_new', read_timeout: 'float' = 0.05, offline_read_timeout: 'float' = 30.0, busy_timeout: 'float' = 0.1, failure_cooldown: 'float' = 60.0, raw_capture: 'bool' = True) -> None
```

Configure local persistence and associated timeouts.

This type is part of the documented implementation; consult field annotations and public API contracts for supported values.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|enabled|bool|True|Validated setting; see the constructor docstring and configuration source.|
|backend|Literal['sqlite']|'sqlite'|auto/json/legacy; auto uses legacy only after valid empty JSON, not after auth/HTTP/schema errors.|
|path|str \| Path \| None|None|Nonempty path string or pathlib.Path, not the working cache database for archive exports.|
|queue_max_jobs|int|128|Validated setting; see the constructor docstring and configuration source.|
|queue_max_bytes|int|67108864|Validated setting; see the constructor docstring and configuration source.|
|queue_overflow|Literal['drop_new']|'drop_new'|Validated setting; see the constructor docstring and configuration source.|
|read_timeout|float|0.05|Validated setting; see the constructor docstring and configuration source.|
|offline_read_timeout|float|30.0|Validated setting; see the constructor docstring and configuration source.|
|busy_timeout|float|0.1|Validated setting; see the constructor docstring and configuration source.|
|failure_cooldown|float|60.0|Validated setting; see the constructor docstring and configuration source.|
|raw_capture|bool|True|Validated setting; see the constructor docstring and configuration source.|

**Returns:** StorageConfig
**Errors:** ConfigurationError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## FreshnessPolicy

```python
FreshnessPolicy(*, max_age: 'timedelta | None' = None, allow_stale: 'bool' = False, max_stale: 'timedelta | None' = None, max_source_age: 'timedelta | None' = None) -> None
```

Define age limits and acceptance rules for cached data.

This type is part of the documented implementation; consult field annotations and public API contracts for supported values.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|max_age|timedelta \| None|None|Validated setting; see the constructor docstring and configuration source.|
|allow_stale|bool|False|Explicit permission to use old cached data; never relabels it as live.|
|max_stale|timedelta \| None|None|Optional nonnegative timedelta limiting age since response retrieval.|
|max_source_age|timedelta \| None|None|Validated setting; see the constructor docstring and configuration source.|

**Returns:** FreshnessPolicy
**Errors:** ConfigurationError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False

## FetchPolicy

```python
FetchPolicy(*, mode: "Literal['auto', 'online', 'offline'] | None" = None, freshness: 'FreshnessPolicy | None' = None, coverage: "Literal['raise', 'report']" = 'report', allow_official_offline: 'bool' = False) -> None
```

Define network, cache and offline fetching behavior.

This type is part of the documented implementation; consult field annotations and public API contracts for supported values.

|Parameter|Type|Default|Meaning|
|---|---|---|---|
|mode|Literal['auto', 'online', 'offline'] \| None|None|auto/online/offline; fresh cached responses may be reused in online. FetchPolicy.fresh() bypasses the cache.|
|freshness|FreshnessPolicy \| None|None|Explicit FreshnessPolicy, with precedence over policy freshness for quotes.|
|coverage|Literal['raise', 'report']|'report'|'report' preserves unknown/partial coverage; 'raise' requires the available evidence.|
|allow_official_offline|bool|False|Validated setting; see the constructor docstring and configuration source.|

**Returns:** FetchPolicy
**Errors:** ConfigurationError
**Dependencies:** pandas, Python standard library
**AsyncClient counterpart:** False
