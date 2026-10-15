"""Pure TSETMC parsers and operation plans shared by both clients.

Reviewed public identity/quote endpoints plus the daily-history adapter are used. No authenticated endpoint is guessed.
"""
from __future__ import annotations
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from urllib.parse import quote
from zoneinfo import ZoneInfo

from pydara.tse._core.exceptions import (
    AmbiguousInstrumentError, DataQualityError, InvalidArgumentError,
    MissingValueError, PointInTimeUnavailableError, SchemaMismatchError,
    UnknownInstrumentError, UnsupportedCapabilityError,
)
from pydara.tse._core.models import (
    InstrumentRecord, InstrumentRef, Market, QuantityUnit, Quote, QuoteUnit, RecordMeta,
)
from ..transport import Packet, RequestSpec, decode

PARSER_VERSION = "1"
_TRANSLATE = str.maketrans({"\u064a": "\u06cc", "\u0649": "\u06cc", "\u0643": "\u06a9",
                            "\u200c": "", "\u200e": "", "\u200f": ""})


def normalize_symbol(value: str) -> str:
    """Normalize symbol.
    
    Args:
        value (str): Input for the normalize_symbol operation.
    
    Returns:
        str: Result of the normalize_symbol operation; refer to its public API contract for schema details.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails."""
    if not isinstance(value, str) or not value.strip():
        raise InvalidArgumentError("A nonempty symbol/query string is required.")
    if len(value) > 200 or any(ord(c) < 32 for c in value):
        raise InvalidArgumentError("Query is too long or contains control characters.")
    return " ".join(value.translate(_TRANSLATE).strip().split())


def search_spec(query: str) -> RequestSpec:
    """Search spec.
    
    Args:
        query (str): Instrument or market search text.
    
    Returns:
        RequestSpec: Result of the search_spec operation; refer to its public API contract for schema details."""
    value = normalize_symbol(query)
    return RequestSpec("instrument.search", "Instrument/GetInstrumentSearch/" + quote(value, safe=""),
                       "instrumentSearch", 86400.0)


def info_spec(ins_code: str) -> RequestSpec:
    """Perform the info spec operation.
    
    Args:
        ins_code (str): Input for the info_spec operation.
    
    Returns:
        RequestSpec: Result of the info_spec operation; refer to its public API contract for schema details."""
    ref = InstrumentRef.by_ins_code(ins_code)
    return RequestSpec("instrument.info", "Instrument/GetInstrumentInfo/" + ref.value,
                       "instrumentInfo", 86400.0)


def quote_spec(ins_code: str) -> RequestSpec:
    """Perform the quote spec operation.
    
    Args:
        ins_code (str): Input for the quote_spec operation.
    
    Returns:
        RequestSpec: Result of the quote_spec operation; refer to its public API contract for schema details."""
    return RequestSpec("quote.latest", "ClosingPrice/GetClosingPriceInfo/" + ins_code,
                       "closingPriceInfo", 0.0)


def identifier(value) -> str:
    """Perform the identifier operation.
    
    Args:
        value (Any): Input for the identifier operation.
    
    Returns:
        str: Result of the identifier operation; refer to its public API contract for schema details.
    
    Raises:
        SchemaMismatchError: When the corresponding validation or operation fails."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise SchemaMismatchError("An identifier must be a string or integer, never a float.")
    result = str(value)
    if not result.isascii() or not result.isdigit() or int(result) <= 0:
        raise SchemaMismatchError("Invalid numeric instrument identifier.")
    return result


def quote_response_identifier_status(value, requested_code: str) -> str:
    """Verify a quote ID against an already verified requested instrument.

    JSON servers sometimes serialize large numeric identifiers as a floating
    value or scientific-notation string. Such values have weaker identity
    evidence: they may have lost digits, so never replace the canonical code.
    Return a quality flag for those representations.
    """
    expected = identifier(requested_code)
    if value is None or value == "":
        return "quote_response_identifier_missing"
    # The observed TSETMC GetClosingPriceInfo response can use the literal
    # zero as an unavailable/unpopulated identifier. The canonical ins_code
    # was already resolved and checked against GetInstrumentInfo. Zero is
    # accepted ONLY for the quote response and must be surfaced as a warning.
    if type(value) in (int, str, Decimal) and value in (0, "0", Decimal(0)):
        return "quote_response_identifier_zero_placeholder"
    if isinstance(value, bool):
        raise SchemaMismatchError("Boolean is not an instrument identifier.")
    if isinstance(value, (str, int)) and not isinstance(value, bool):
        try:
            actual = identifier(value)
        except SchemaMismatchError:
            if not isinstance(value, str):
                raise
        else:
            if actual != expected:
                raise DataQualityError("Quote belongs to a different instrument.")
            return ""
    if not isinstance(value, (str, float, Decimal)) or isinstance(value, bool):
        raise SchemaMismatchError("Unsupported quote instrument identifier type.")
    try:
        decimal_id = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise SchemaMismatchError("Malformed quote instrument identifier.") from exc
    if not decimal_id.is_finite() or decimal_id < 0 or decimal_id != decimal_id.to_integral_value():
        raise SchemaMismatchError("Nonintegral quote instrument identifier.")
    if decimal_id == 0:
        return "quote_response_identifier_zero_placeholder"
    if decimal_id != Decimal(expected):
        raise DataQualityError("Quote identifier does not match requested instrument.")
    # Float/scientific text is not proof of every original digit.
    return "quote_response_identifier_rounded_or_scientific"


def decimal_value(value, field: str) -> Decimal | None:
    """Perform the decimal value operation.
    
    Args:
        value (Any): Input for the decimal_value operation.
        field (str): Requested data field.
    
    Returns:
        Decimal | None: Result of the decimal_value operation; refer to its public API contract for schema details.
    
    Raises:
        DataQualityError: When the corresponding validation or operation fails.
        SchemaMismatchError: When the corresponding validation or operation fails."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise SchemaMismatchError(f"Invalid numeric field {field}.")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise SchemaMismatchError(f"Invalid numeric field {field}.") from exc
    if not result.is_finite() or result < 0:
        raise DataQualityError(f"Nonfinite or negative value in {field}.")
    return result


def optional_text(value):
    """Perform the optional text operation.
    
    Args:
        value (Any): Input for the optional_text operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        SchemaMismatchError: When the corresponding validation or operation fails."""
    if value is None:
        return None
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        raise SchemaMismatchError("Expected text/code.")
    return str(value)


def meta(packet: Packet, namespace: str, key: str, source_time=None, flags=(), assumptions=()):
    """Perform the meta operation.
    
    Args:
        packet (Packet): Response packet received from a provider.
        namespace (str): Storage or frame metadata namespace.
        key (str): Input for the meta operation.
        source_time (Any): Input for the meta operation.
        flags (Any): Input for the meta operation.
        assumptions (Any): Input for the meta operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    if namespace == "sample":
        flags = (*flags, "synthetic_sample_not_market_data")
    return RecordMeta(provider="public", endpoint_id=packet.endpoint_id,
        retrieved_at=packet.fetched_at, source_timestamp=source_time,
        row_id=sha256(key.encode()).hexdigest(), observation_id=packet.request_id,
        first_observed_at=packet.first_observed_at, available_at=packet.fetched_at,
        payload_hash=packet.payload_hash, request_id=packet.request_id, scope_id=namespace,
        raw_reference=packet.payload_hash, quality_flags=tuple(dict.fromkeys(flags)), assumptions=tuple(assumptions),
        from_cache=packet.from_cache, is_stale=packet.is_stale,
        committed_at=packet.committed_at, storage_receipt_id=packet.receipt_id)


def instrument_record(row, packet: Packet, namespace: str) -> InstrumentRecord:
    """Perform the instrument record operation.
    
    Args:
        row (Any): Input for the instrument_record operation.
        packet (Packet): Response packet received from a provider.
        namespace (str): Storage or frame metadata namespace.
    
    Returns:
        InstrumentRecord: Result of the instrument_record operation; refer to its public API contract for schema details.
    
    Raises:
        SchemaMismatchError: When the corresponding validation or operation fails."""
    if not isinstance(row, dict):
        raise SchemaMismatchError("Instrument must be a JSON object.")
    for key in ("insCode", "lVal18AFC"):
        if key not in row:
            raise SchemaMismatchError(f"Missing instrument field {key}.")
    code = identifier(row["insCode"])
    raw = row["lVal18AFC"]
    if not isinstance(raw, str) or not raw.strip():
        raise SchemaMismatchError("Instrument has no usable symbol.")
    flow = optional_text(row.get("flow"))
    yval = optional_text(row.get("yVal"))
    market = {"1": Market.TSE, "2": Market.IFB}.get(flow)
    # Explicit, narrow share-type mapping, never a general assertion for derivatives/funds.
    equity = yval in {"300", "303", "309"}
    if yval == "309":
        market = Market.BASE
    valid = row.get("valid", row.get("Valid"))
    active = {0: False, 1: True}.get(valid) if isinstance(valid, (int, bool)) else None
    assumptions = ("IRR/share units from supported equity yVal mapping",) if equity else ()
    flags = () if equity else ("instrument_unit_not_verified",)
    return InstrumentRecord(ins_code=code, symbol=normalize_symbol(raw), raw_symbol=raw,
        name=optional_text(row.get("lVal30")), instrument_id=optional_text(row.get("instrumentID")),
        company_cisin=optional_text(row.get("cIsin")), market=market, raw_flow=flow,
        instrument_type=yval, is_active=active,
        quote_unit=QuoteUnit.PRICE if equity else QuoteUnit.UNKNOWN,
        quantity_unit=QuantityUnit.SHARE if equity else QuantityUnit.UNKNOWN,
        currency="IRR" if equity else None,
        meta=meta(packet, namespace, "instrument:" + code, flags=flags, assumptions=assumptions))


def parse_search(packet, spec, namespace) -> list[InstrumentRecord]:
    """Parse search.
    
    Args:
        packet (Any): Response packet received from a provider.
        spec (Any): Request or schema specification.
        namespace (Any): Storage or frame metadata namespace.
    
    Returns:
        list[InstrumentRecord]: Result of the parse_search operation; refer to its public API contract for schema details.
    
    Raises:
        DataQualityError: When the corresponding validation or operation fails.
        SchemaMismatchError: When the corresponding validation or operation fails."""
    data = decode(packet, spec)
    if not isinstance(data, list):
        raise SchemaMismatchError("instrumentSearch must be a list (including when empty).")
    records = [instrument_record(row, packet, namespace) for row in data]
    seen = {}
    for item in records:
        prior = seen.get(item.ins_code)
        if prior and (prior.symbol != item.symbol or prior.name != item.name):
            raise DataQualityError("Conflicting duplicate instrument identifier in search response.")
        seen[item.ins_code] = item
    return list(seen.values())


def parse_info(packet, spec, namespace):
    """Parse info.
    
    Args:
        packet (Any): Response packet received from a provider.
        spec (Any): Request or schema specification.
        namespace (Any): Storage or frame metadata namespace.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        DataQualityError: When the corresponding validation or operation fails.
        UnknownInstrumentError: When the corresponding validation or operation fails."""
    data = decode(packet, spec)
    if data is None:
        raise UnknownInstrumentError("No instrument information was returned.")
    record = instrument_record(data, packet, namespace)
    if record.ins_code != spec.path.rsplit("/", 1)[1]:
        raise DataQualityError("Response belongs to a different instrument.")
    return record


def validate_payload(packet, spec, namespace):
    """Validate before a response is admitted to either cache or persistence."""
    if spec.endpoint_id.startswith("extra."):
        from .extended import parse_payload
        parse_payload(packet, spec)
    elif spec.endpoint_id.startswith(("market.", "clients.", "indices.")):
        from .market import parse_market_payload
        parse_market_payload(packet, spec)
    elif spec.endpoint_id == "instrument.search":
        parse_search(packet, spec, namespace)
    elif spec.endpoint_id == "instrument.info":
        parse_info(packet, spec, namespace)
    elif spec.endpoint_id == "history.daily":
        from .history import parse_history_rows
        parse_history_rows(packet, spec)
    elif spec.endpoint_id == "quote.latest":
        row = decode(packet, spec)
        if row is None:
            raise MissingValueError("No quote is available for this instrument.")
        if not isinstance(row, dict):
            raise SchemaMismatchError("closingPriceInfo must be an object.")
        for key in ("insCode", "pDrCotVal", "pClosing"):
            if key not in row:
                raise SchemaMismatchError(f"Missing quote field {key}.")
        # TSETMC may leave insCode null/blank in the quote response.
        # The quote URL was constructed from the already validated instrument info.
        # Missing/zero identification is accepted ONLY for this quote route
        # and recorded as a quality flag. Explicit conflicting/nonintegral IDs remain errors.
        quote_response_identifier_status(row["insCode"], spec.path.rsplit("/", 1)[1])
        for key in ("pDrCotVal", "pClosing", "priceYesterday", "priceFirst", "priceMin", "priceMax",
                    "qTotTran5J", "qTotCap", "zTotTran"):
            number = decimal_value(row.get(key), key)
            if key == "zTotTran" and number is not None and number != number.to_integral_value():
                raise DataQualityError("trade_count is not an integer.")
        lo = decimal_value(row.get("priceMin"), "priceMin")
        hi = decimal_value(row.get("priceMax"), "priceMax")
        if lo is not None and hi is not None and hi > 0 and lo > hi:
            raise DataQualityError("Daily low exceeds daily high.")
        parse_source_time(row)
    else:
        raise UnsupportedCapabilityError(f"No parser registered for {spec.endpoint_id}.")


def parse_source_time(row):
    """Parse source time.
    
    Args:
        row (Any): Input for the parse_source_time operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        SchemaMismatchError: When the corresponding validation or operation fails.
        ValueError: When the corresponding validation or operation fails."""
    d, t = row.get("dEven"), row.get("hEven")
    trade_date, stamp = None, None
    if d not in (None, 0, "0", ""):
        try:
            ds = str(d)
            if len(ds) != 8 or not ds.isdigit():
                raise ValueError
            trade_date = datetime.strptime(ds, "%Y%m%d").date()
        except (ValueError, TypeError) as exc:
            raise SchemaMismatchError("dEven is not a Gregorian YYYYMMDD date.") from exc
    if trade_date and t not in (None, ""):
        try:
            ts = str(t)
            if not ts.isdigit() or len(ts) > 6:
                raise ValueError
            tm = datetime.strptime(ts.zfill(6), "%H%M%S").time()
            stamp = datetime.combine(trade_date, tm, ZoneInfo("Asia/Tehran")).astimezone(UTC)
        except (ValueError, TypeError) as exc:
            raise SchemaMismatchError("hEven is not a valid HHMMSS time.") from exc
    return trade_date, stamp


def parse_quote(packet, spec, namespace, instrument):
    """Parse quote.
    
    Args:
        packet (Any): Response packet received from a provider.
        spec (Any): Request or schema specification.
        namespace (Any): Storage or frame metadata namespace.
        instrument (Any): Instrument name or explicit instrument reference; ambiguity is not silently resolved.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        DataQualityError: When the corresponding validation or operation fails."""
    row = decode(packet, spec)
    trade_date, stamp = parse_source_time(row)
    flags = list(instrument.meta.quality_flags)
    code_quality = quote_response_identifier_status(row.get("insCode"), instrument.ins_code)
    if code_quality:
        flags.append(code_quality)
    if stamp is None:
        flags.append("source_time_unknown")
    elif stamp > datetime.now(UTC) + timedelta(minutes=5):
        flags.append("source_time_in_future")
    if trade_date and trade_date != datetime.now(ZoneInfo("Asia/Tehran")).date():
        flags.append("source_date_not_today")
    if packet.is_stale:
        flags.append("stale_cached_response")
    state_obj = row.get("instrumentState")
    raw_state = optional_text(state_obj.get("cEtaval")) if isinstance(state_obj, dict) else None
    values = {key: decimal_value(row.get(source), source) for key, source in {
        "last_price": "pDrCotVal", "closing_price": "pClosing",
        "previous_reference_price": "priceYesterday", "open_price": "priceFirst",
        "high_price": "priceMax", "low_price": "priceMin", "volume": "qTotTran5J",
        "turnover": "qTotCap"}.items()}
    lo, hi = values["low_price"], values["high_price"]
    if lo is not None and hi is not None and hi > 0 and lo > hi:
        raise DataQualityError("Daily low exceeds daily high.")
    count = decimal_value(row.get("zTotTran"), "zTotTran")
    return Quote(instrument=instrument, trade_date=trade_date, **values,
        trade_count=int(count) if count is not None else None,
        turnover_currency=instrument.currency, raw_state=raw_state,
        state=raw_state.strip() if raw_state else None,
        source_timestamp=stamp, retrieved_at=packet.fetched_at,
        meta=meta(packet, namespace, "quote:" + instrument.ins_code + ":" + str(trade_date),
                  source_time=stamp, flags=tuple(dict.fromkeys(flags)),
                  assumptions=instrument.meta.assumptions))


def instrument_plan(instrument, *, market=None, as_of=None, known_at=None, namespace="public"):
    """Perform the instrument plan operation.
    
    Args:
        instrument (Any): Instrument name or explicit instrument reference; ambiguity is not silently resolved.
        market (Any): Market selection or filtering constraint.
        as_of (Any): Requested economic effective date; check endpoint support.
        known_at (Any): Historical knowledge cutoff; check endpoint support.
        namespace (Any): Storage or frame metadata namespace.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        AmbiguousInstrumentError: When the corresponding validation or operation fails.
        DataQualityError: When the corresponding validation or operation fails.
        InvalidArgumentError: When the corresponding validation or operation fails.
        PointInTimeUnavailableError: When the corresponding validation or operation fails.
        UnknownInstrumentError: When the corresponding validation or operation fails.
        UnsupportedCapabilityError: When the corresponding validation or operation fails."""
    if as_of is not None or known_at is not None:
        raise PointInTimeUnavailableError("Historical identity resolution is a later module.")
    if isinstance(instrument, str):
        ref = InstrumentRef.by_symbol(instrument)
    elif isinstance(instrument, InstrumentRef):
        ref = instrument
    else:
        raise InvalidArgumentError("Use a symbol string or InstrumentRef.")
    if market is not None and not isinstance(market, Market):
        raise InvalidArgumentError("market must be a Market enum.")
    if ref.market is not None and market is not None and ref.market != market:
        raise InvalidArgumentError("Conflicting market constraints.")
    wanted_market = market or ref.market
    wanted_symbol = None
    if ref.kind == "isin":
        raise UnsupportedCapabilityError("ISIN lookup is not implemented in this release; use ins_code.")
    if ref.kind == "symbol":
        wanted_symbol = normalize_symbol(ref.value)
        spec = search_spec(wanted_symbol)
        packet = yield spec
        candidates = [r for r in parse_search(packet, spec, namespace)
                      if r.symbol == wanted_symbol and (wanted_market is None or r.market == wanted_market)]
        if not candidates:
            raise UnknownInstrumentError(f"No exact match for {wanted_symbol!r}.")
        if len(candidates) != 1:
            raise AmbiguousInstrumentError("Several exact symbols match; use InstrumentRef.by_ins_code().",
                                           candidates=tuple(r.ins_code for r in candidates))
        ins_code = candidates[0].ins_code
    else:
        ins_code = ref.value
    spec = info_spec(ins_code)
    packet = yield spec
    record = parse_info(packet, spec, namespace)
    if wanted_market is not None and record.market != wanted_market:
        raise UnknownInstrumentError("The instrument does not match the requested market.")
    if wanted_symbol is not None and record.symbol != wanted_symbol:
        raise DataQualityError("Search and instrument information disagree on the symbol.")
    return record


def quote_plan(instrument, *, namespace="public"):
    """Perform the quote plan operation.
    
    Args:
        instrument (Any): Instrument name or explicit instrument reference; ambiguity is not silently resolved.
        namespace (Any): Storage or frame metadata namespace.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    record = yield from instrument_plan(instrument, namespace=namespace)
    spec = quote_spec(record.ins_code)
    packet = yield spec
    return parse_quote(packet, spec, namespace, record)
