"""Exact, auditable instrument lookup shared by synchronous and asynchronous facades.

A numeric identifier is never treated as a symbol. An ins_code is the authoritative
lookup key when present; additional constraints are verified against the returned
record. Unknown metadata is not silently claimed to match in strict mode.
"""
from __future__ import annotations

from pydara.tse._core.exceptions import (
    AmbiguousInstrumentError, InvalidArgumentError, UnknownInstrumentError,
    UnsupportedCapabilityError,
)
from pydara.tse._core.models import InstrumentRef, Market
from .providers.public import normalize_symbol

FIELDS = ("ins_code", "instrument_id", "company_cisin", "symbol", "raw_symbol",
          "name", "market", "raw_flow", "instrument_type", "currency", "is_active")
TEXT_FIELDS = {"instrument_id", "company_cisin", "symbol", "raw_symbol", "name",
               "raw_flow", "instrument_type", "currency"}


def normalize_ins_codes(value):
    """Validate a scalar or one-dimensional collection of explicit TSETMC codes.

    Strings are treated as single codes. Duplicate identifiers are removed in
    encounter order; integers are accepted but floating-point IDs are rejected.
    """
    import numpy as np
    import pandas as pd
    if isinstance(value, (list, tuple, pd.Series, pd.Index, np.ndarray)):
        if isinstance(value, np.ndarray) and value.ndim != 1:
            raise InvalidArgumentError('ins_code must be one-dimensional.')
        values = list(value)
        if not values:
            raise InvalidArgumentError('ins_code list must not be empty.')
    else:
        values = [value]
    codes = []
    for item in values:
        if isinstance(item, bool) or not isinstance(item, (str, int, np.integer)):
            raise InvalidArgumentError('ins_code values must be ASCII digit strings or integers.')
        try:
            code = InstrumentRef.by_ins_code(str(item)).value
        except ValueError as exc:
            raise InvalidArgumentError('Invalid ins_code.') from exc
        if code not in codes:
            codes.append(code)
    return tuple(codes)


def constraints(**kwargs):
    """Perform the constraints operation.
    
    Args:
        kwargs: Additional keyword arguments forwarded to the wrapped operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails.
        UnsupportedCapabilityError: When the corresponding validation or operation fails."""
    strict = kwargs.pop("strict", True)
    if type(strict) is not bool:
        raise InvalidArgumentError("strict must be True or False.")
    provided = {key: value for key, value in kwargs.items() if value is not None}
    if not provided:
        raise InvalidArgumentError("Supply at least one instrument identity or search constraint.")
    if "ins_code" in provided:
        value = provided["ins_code"]
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise InvalidArgumentError("ins_code must be a positive ASCII digit string or integer.")
        try:
            provided["ins_code"] = InstrumentRef.by_ins_code(str(value)).value
        except ValueError as exc:
            raise InvalidArgumentError("Invalid ins_code.") from exc
    if "market" in provided:
        value = provided["market"]
        if not isinstance(value, Market):
            if not isinstance(value, str):
                raise InvalidArgumentError("market must be Market or a supported market name.")
            try:
                provided["market"] = Market(value.upper())
            except ValueError as exc:
                raise InvalidArgumentError("Unknown market; use Market.TSE / Market.IFB.") from exc
    if "is_active" in provided and type(provided["is_active"]) is not bool:
        raise InvalidArgumentError("is_active must be True, False or None.")
    for field in TEXT_FIELDS:
        if field in provided:
            value = provided[field]
            if not isinstance(value, str) or not value.strip():
                raise InvalidArgumentError(f"{field} must be a nonempty string.")
            provided[field] = normalize_symbol(value)
    if not any(k in provided for k in ("ins_code", "symbol", "raw_symbol", "name")):
        raise UnsupportedCapabilityError(
            "Searching the entire historical universe by instrument_id/company_cisin/other "
            "metadata is not supported. Supply ins_code, symbol, raw_symbol or name as a locator."
        )
    return provided, strict


def _matches(record, field, expected, strict):
    """Process internal matches data.
    
    Args:
        record (Any): Normalized instrument or market record.
        field (Any): Requested data field.
        expected (Any): Input for the _matches operation.
        strict (Any): Input for the _matches operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    actual = getattr(record, field)
    if actual is None:
        return not strict
    if field == "market" or field == "is_active":
        return actual == expected
    if field in TEXT_FIELDS:
        return normalize_symbol(str(actual)) == expected
    return actual == expected


def verify(record, criteria, strict):
    """Perform the verify operation.
    
    Args:
        record (Any): Normalized instrument or market record.
        criteria (Any): Input for the verify operation.
        strict (Any): Input for the verify operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        UnknownInstrumentError: When the corresponding validation or operation fails."""
    mismatches = [field for field, expected in criteria.items()
                  if not _matches(record, field, expected, strict)]
    if mismatches:
        raise UnknownInstrumentError(
            "Instrument found, but supplied criteria do not match or cannot be verified: "
            + ", ".join(sorted(mismatches))
        )
    return record


def candidates_from_search(records, criteria, strict):
    """Exact filter; never pick the first match, even in non-strict mode."""
    matched = [r for r in records if all(_matches(r, field, val, strict)
               for field, val in criteria.items() if field != "ins_code")]
    codes = tuple(dict.fromkeys(r.ins_code for r in matched))
    if not codes:
        raise UnknownInstrumentError("No instrument matches all supplied criteria.")
    if len(codes) > 1:
        raise AmbiguousInstrumentError(
            "More than one instrument matches; provide ins_code or more constraints.",
            candidates=codes,
        )
    return codes[0]


def locator(criteria):
    """Perform the locator operation.
    
    Args:
        criteria (Any): Input for the locator operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails."""
    for field in ("symbol", "raw_symbol", "name"):
        if field in criteria:
            return criteria[field]
    raise InvalidArgumentError("No searchable symbol or name was supplied.")


def lookup_policies(on_multiple="all", on_conflict="error", *, has_ins_code=False):
    """Validate independent cardinality and conflicting-criteria policies."""
    if on_multiple not in ("all", "first", "error") or not isinstance(on_multiple, str):
        raise InvalidArgumentError("on_multiple must be 'all', 'first', or 'error'.")
    if on_conflict not in ("error", "ins_code") or not isinstance(on_conflict, str):
        raise InvalidArgumentError("on_conflict must be 'error' or 'ins_code'.")
    if on_conflict == "ins_code" and not has_ins_code:
        raise InvalidArgumentError("on_conflict='ins_code' requires ins_code.")
    return on_multiple, on_conflict


def matching_codes(records, criteria, strict):
    """Keep all unique exact matches in the source's stable search order."""
    matched = [r for r in records if all(_matches(r, field, val, strict)
               for field, val in criteria.items() if field != "ins_code")]
    return tuple(dict.fromkeys(r.ins_code for r in matched))


def select_codes(codes, on_multiple):
    """Select codes.
    
    Args:
        codes (Any): Input for the select_codes operation.
        on_multiple (Any): Policy for ambiguous or multiple instrument matches.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        AmbiguousInstrumentError: When the corresponding validation or operation fails.
        UnknownInstrumentError: When the corresponding validation or operation fails."""
    if not codes:
        raise UnknownInstrumentError("No instrument matches all supplied criteria.")
    if len(codes) > 1 and on_multiple == "error":
        raise AmbiguousInstrumentError(
            "More than one instrument matches; narrow the criteria or use on_multiple='all'.",
            candidates=codes,
        )
    if on_multiple == "first":
        return codes[:1]
    return codes


def verify_identity(record, criteria, strict, on_conflict):
    """Perform the verify identity operation.
    
    Args:
        record (Any): Normalized instrument or market record.
        criteria (Any): Input for the verify_identity operation.
        strict (Any): Input for the verify_identity operation.
        on_conflict (Any): Policy for conflicting stored or retrieved rows.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    if on_conflict == "ins_code":
        return record
    return verify(record, criteria, strict)
