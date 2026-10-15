"""Immutable domain models. A numeric string is never implicitly an ins_code."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

from .exceptions import ConfigurationError

class Market(StrEnum):
    """Enumerate supported TSE market identifiers.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    TSE = "TSE"
    IFB = "IFB"
    BASE = "BASE"
    DERIVATIVES = "DERIVATIVES"
    ENERGY = "ENERGY"
    COMMODITY = "COMMODITY"

class QuoteUnit(StrEnum):
    """Enumerate quote value units.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    PRICE = "PRICE"
    PERCENT = "PERCENT"
    INDEX_POINTS = "INDEX_POINTS"
    UNKNOWN = "UNKNOWN"

class QuantityUnit(StrEnum):
    """Enumerate quantity units.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    SHARE = "SHARE"
    CONTRACT = "CONTRACT"
    UNIT = "UNIT"
    MWH = "MWH"
    UNKNOWN = "UNKNOWN"

@dataclass(frozen=True, kw_only=True)
class InstrumentRef:
    """Identify a market instrument explicitly.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    kind: Literal["symbol", "ins_code", "isin"]
    value: str
    market: Market | None = None

    def __post_init__(self):
        """Validate and normalize dataclass fields after initialization.
        
        Raises:
            ConfigurationError: When the corresponding validation or operation fails."""
        if self.kind not in {"symbol", "ins_code", "isin"}:
            raise ConfigurationError("Unknown identifier kind.")
        if not isinstance(self.value, str) or not self.value.strip():
            raise ConfigurationError("Identifier value must be a nonempty string.")
        if self.kind == "ins_code" and (
            not self.value.isascii() or not self.value.isdigit() or int(self.value) <= 0
        ):
            raise ConfigurationError("ins_code must contain positive ASCII digits; keep it a string.")
        if self.market is not None and not isinstance(self.market, Market):
            raise ConfigurationError("market must be a Market enum.")

    @classmethod
    def by_ins_code(cls, value: str, *, market: Market | None = None) -> InstrumentRef:
        """Perform the by ins code operation.
        
        Args:
            value (str): Input for the by_ins_code operation.
            market (Market | None): Market selection or filtering constraint.
        
        Returns:
            InstrumentRef: Result of the by_ins_code operation; refer to its public API contract for schema details."""
        return cls(kind="ins_code", value=value, market=market)

    @classmethod
    def by_symbol(cls, value: str, *, market: Market | None = None) -> InstrumentRef:
        """Perform the by symbol operation.
        
        Args:
            value (str): Input for the by_symbol operation.
            market (Market | None): Market selection or filtering constraint.
        
        Returns:
            InstrumentRef: Result of the by_symbol operation; refer to its public API contract for schema details."""
        return cls(kind="symbol", value=value, market=market)

    @classmethod
    def by_isin(cls, value: str, *, market: Market | None = None) -> InstrumentRef:
        """Perform the by isin operation.
        
        Args:
            value (str): Input for the by_isin operation.
            market (Market | None): Market selection or filtering constraint.
        
        Returns:
            InstrumentRef: Result of the by_isin operation; refer to its public API contract for schema details."""
        return cls(kind="isin", value=value, market=market)

InstrumentLike = str | InstrumentRef

@dataclass(frozen=True, kw_only=True)
class RecordMeta:
    """Carry source and retrieval metadata for a record.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    provider: str
    endpoint_id: str
    retrieved_at: datetime
    source_timestamp: datetime | None
    row_id: str
    observation_id: str
    first_observed_at: datetime
    available_at: datetime
    payload_hash: str
    request_id: str
    scope_id: str
    schema_version: str = "1"
    parser_version: str = "1"
    availability_basis: str = "observed"
    raw_reference: str | None = None
    quality_flags: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    source_published_at: datetime | None = None
    committed_at: datetime | None = None
    from_cache: bool = False
    is_stale: bool = False
    storage_receipt_id: str | None = None

@dataclass(frozen=True, kw_only=True)
class InstrumentRecord:
    """Represent verified instrument identity and source metadata.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    ins_code: str
    symbol: str
    raw_symbol: str
    name: str | None
    instrument_id: str | None
    company_cisin: str | None
    market: Market | None
    raw_flow: str | None
    instrument_type: str | None
    is_active: bool | None
    quote_unit: QuoteUnit
    quantity_unit: QuantityUnit
    currency: str | None
    meta: RecordMeta
    valid_from: date | None = None
    valid_to: date | None = None
    first_trade_date: date | None = None

    def to_frame(self) -> pd.DataFrame:
        """One-row Pandas table without HTTP or disk access."""
        from pydara.tse.frames import instrument_frame
        return instrument_frame([self])

    def to_ref(self) -> InstrumentRef:
        """An explicit exact identifier usable in get_history/get_quote."""
        return InstrumentRef.by_ins_code(self.ins_code)

@dataclass(frozen=True, kw_only=True)
class Quote:
    """Represent a quote and its provenance without assuming live accuracy.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    instrument: InstrumentRecord
    trade_date: date | None
    last_price: Decimal | None
    closing_price: Decimal | None
    previous_reference_price: Decimal | None
    open_price: Decimal | None
    high_price: Decimal | None
    low_price: Decimal | None
    trade_count: int | None
    volume: Decimal | None
    turnover: Decimal | None
    turnover_currency: str | None
    state: str | None
    raw_state: str | None
    source_timestamp: datetime | None
    retrieved_at: datetime
    meta: RecordMeta
    timestamp_kind: str = "unknown"

    def to_frame(self, *, numeric: Literal["analysis", "exact"] = "analysis") -> pd.DataFrame:
        """Return one typed Pandas row; no network, persistence, or mutation."""
        from pydara.tse.frames import quote_frame
        return quote_frame([self], numeric=numeric)

@dataclass(frozen=True, kw_only=True)
class WriteReceipt:
    """Describe a local write attempt and persistence state.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    receipt_id: str
    request_id: str | None
    state: str
    accepted_at: datetime | None
    committed_at: datetime | None
    rows: int
    payload_bytes: int
    reason: str | None
    destination: str | None
    content_hash: str | None

@dataclass(frozen=True, kw_only=True)
class StorageStatus:
    """Describe availability and status of local storage.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    enabled: bool
    health: str
    path: str | None
    pending_jobs: int
    pending_bytes: int
    persisted_jobs: int
    failed_jobs: int
    skipped_jobs: int
    last_commit_at: datetime | None
    last_error: str | None

@dataclass(frozen=True, kw_only=True)
class FlushReport:
    """Summarize pending local writes and their outcomes.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    complete: bool
    queued_at_start: int
    persisted: int
    failed: int
    skipped: int
    pending: int
    elapsed_seconds: float
    last_error: str | None
    receipts: object = field(repr=False)
