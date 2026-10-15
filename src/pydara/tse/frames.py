"""One Pandas schema implementation shared by sync, async and cached data."""
from __future__ import annotations
from datetime import UTC, datetime
from decimal import Decimal
from math import isfinite
import pandas as pd

from pydara import __version__
from pydara.tse._core.exceptions import InvalidArgumentError, DataQualityError

INSTRUMENT_STRINGS = ["ins_code", "symbol", "raw_symbol", "name", "instrument_id", "company_cisin",
                      "market", "raw_flow", "instrument_type", "currency", "quote_unit", "quantity_unit"]
META_STRINGS = ["source", "endpoint_id", "row_id", "observation_id", "payload_hash",
                "availability_basis", "scope_id", "storage_receipt_id"]
META_TIMES = ["fetched_at", "first_observed_at", "available_at", "source_timestamp"]
QUOTE_NUMBERS = ["last_price", "closing_price", "previous_reference_price", "open_price",
                 "high_price", "low_price", "volume", "turnover"]


def meta_row(m):
    """Perform the meta row operation.
    
    Args:
        m (Any): Input for the meta_row operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    return dict(source=m.provider, endpoint_id=m.endpoint_id, row_id=m.row_id,
                observation_id=m.observation_id, payload_hash=m.payload_hash,
                availability_basis=m.availability_basis, scope_id=m.scope_id,
                storage_receipt_id=m.storage_receipt_id, fetched_at=m.retrieved_at,
                first_observed_at=m.first_observed_at, available_at=m.available_at,
                source_timestamp=m.source_timestamp, from_cache=m.from_cache,
                is_stale=m.is_stale, quality_flags=m.quality_flags)


def instrument_row(r):
    """Perform the instrument row operation.
    
    Args:
        r (Any): Input for the instrument_row operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    return {**{c: getattr(r, c) for c in INSTRUMENT_STRINGS}, "is_active": r.is_active,
            **meta_row(r.meta)}


def cast_frame(rows, strings, times, bools, numbers=(), ints=(), numeric="analysis", extra=()):
    """Cast frame.
    
    Args:
        rows (Any): Input for the cast_frame operation.
        strings (Any): Input for the cast_frame operation.
        times (Any): Input for the cast_frame operation.
        bools (Any): Input for the cast_frame operation.
        numbers (Any): Input for the cast_frame operation.
        ints (Any): Input for the cast_frame operation.
        numeric (Any): Numeric conversion or output representation setting.
        extra (Any): Input for the cast_frame operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        DataQualityError: When the corresponding validation or operation fails.
        InvalidArgumentError: When the corresponding validation or operation fails."""
    if numeric not in {"analysis", "exact"}:
        raise InvalidArgumentError("numeric must be analysis or exact.")
    cols = list(dict.fromkeys([*strings, *times, *bools, *numbers, *ints, *extra]))
    frame = pd.DataFrame(rows, columns=cols)
    for c in strings:
        frame[c] = frame[c].astype("string")
    for c in times:
        frame[c] = pd.to_datetime(frame[c], utc=True).astype("datetime64[ns, UTC]")
    for c in bools:
        frame[c] = frame[c].astype("boolean")
    for c in ints:
        frame[c] = frame[c].astype("Int64")
    for c in numbers:
        if numeric == "analysis":
            frame[c] = frame[c].astype("Float64")
            if any(not isfinite(float(v)) for v in frame[c].dropna()):
                raise DataQualityError(f"{c} overflows Float64; use ClientConfig(numeric='exact').")
        else:
            frame[c] = frame[c].astype(object)
    return frame


def attach(frame, schema, *, coverage="unknown", numeric="analysis"):
    """Attach the requested value.
    
    Args:
        frame (Any): DataFrame to convert, validate, process or store.
        schema (Any): Input for the attach operation.
        coverage (Any): Input for the attach operation.
        numeric (Any): Numeric conversion or output representation setting.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    frame.attrs["pydara"] = dict(schema_id=schema, schema_version="1", package_version=__version__,
        coverage_status=coverage, numeric=numeric,
        note="attrs is convenience metadata; row provenance is also stored as columns.")
    return frame


def instrument_frame(records):
    """Perform the instrument frame operation.
    
    Args:
        records (Any): Input for the instrument_frame operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    frame = cast_frame([instrument_row(r) for r in records], INSTRUMENT_STRINGS+META_STRINGS,
                       META_TIMES, ["is_active", "from_cache", "is_stale"], extra=["quality_flags"])
    return attach(frame, "instruments")


def quote_row(q):
    """Perform the quote row operation.
    
    Args:
        q (Any): Input for the quote_row operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    return {"ins_code": q.instrument.ins_code, "symbol": q.instrument.symbol,
        "currency": q.instrument.currency, "quote_unit": q.instrument.quote_unit,
        "quantity_unit": q.instrument.quantity_unit, "date": q.trade_date,
        "state": q.state, "raw_state": q.raw_state, "timestamp_kind": q.timestamp_kind,
        "trade_count": q.trade_count, **{c: getattr(q, c) for c in QUOTE_NUMBERS}, **meta_row(q.meta)}


def quote_frame(quotes, *, numeric="analysis", batch_rows=None):
    """Perform the quote frame operation.
    
    Args:
        quotes (Any): Input for the quote_frame operation.
        numeric (Any): Numeric conversion or output representation setting.
        batch_rows (Any): Input for the quote_frame operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    strings = ["ins_code", "symbol", "currency", "quote_unit", "quantity_unit", "state",
               "raw_state", "timestamp_kind", *META_STRINGS]
    ints = ["trade_count"]
    rows = [quote_row(q) for q in quotes] if batch_rows is None else batch_rows
    if batch_rows is not None:
        strings += ["input_symbol", "status", "error_code", "error_message"]
        ints += ["request_index"]
    frame = cast_frame(rows, strings, META_TIMES, ["from_cache", "is_stale"],
                       QUOTE_NUMBERS, ints, numeric, extra=["date", "quality_flags"])
    frame["date"] = pd.to_datetime(frame["date"]).astype("datetime64[ns]")
    return attach(frame, "quotes.batch" if batch_rows is not None else "quote", numeric=numeric)
