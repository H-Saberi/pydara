"""Validated, immutable configuration. Timeouts are soft OS-level budgets."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import timedelta
from math import isfinite
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydara.tse._core.exceptions import ConfigurationError


def positive(name, value, *, zero=False, integer=False):
    """Require a positive value for the requested value.
    
    Args:
        name (Any): Input for the positive operation.
        value (Any): Input for the positive operation.
        zero (Any): Input for the positive operation.
        integer (Any): Input for the positive operation.
    
    Raises:
        ConfigurationError: When the corresponding validation or operation fails."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigurationError(f"{name} must be numeric.")
    if integer and not isinstance(value, int):
        raise ConfigurationError(f"{name} must be an integer.")
    if not isfinite(value) or value < 0 or (value == 0 and not zero):
        raise ConfigurationError(f"{name} is out of range.")

@dataclass(frozen=True, kw_only=True)
class NetworkConfig:
    """Configure HTTP request limits and retry timing.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    connect_timeout: float = 5.0
    read_timeout: float = 20.0
    operation_timeout: float = 60.0
    max_concurrency: int = 4
    max_retries: int = 2
    requests_per_second: float = 0.5
    request_budget: int = 100
    max_response_bytes: int = 32 * 1024 * 1024
    trust_env: bool = True

    def __post_init__(self):
        """Validate and normalize dataclass fields after initialization.
        
        Raises:
            ConfigurationError: When the corresponding validation or operation fails."""
        if not isinstance(self.trust_env, bool):
            raise ConfigurationError("trust_env must be bool.")
        for k in ("connect_timeout", "read_timeout", "operation_timeout", "requests_per_second"):
            positive(k, getattr(self, k))
        for k in ("max_concurrency", "request_budget", "max_response_bytes"):
            positive(k, getattr(self, k), integer=True)
        positive("max_retries", self.max_retries, zero=True, integer=True)

@dataclass(frozen=True, kw_only=True)
class StorageConfig:
    """Configure local persistence and associated timeouts.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    enabled: bool = True
    backend: Literal["sqlite"] = "sqlite"
    path: str | Path | None = None
    queue_max_jobs: int = 128
    queue_max_bytes: int = 64 * 1024 * 1024
    queue_overflow: Literal["drop_new"] = "drop_new"
    read_timeout: float = 0.05
    offline_read_timeout: float = 30.0
    busy_timeout: float = 0.1
    failure_cooldown: float = 60.0
    raw_capture: bool = True

    def __post_init__(self):
        """Validate and normalize dataclass fields after initialization.
        
        Raises:
            ConfigurationError: When the corresponding validation or operation fails."""
        if not isinstance(self.enabled, bool):
            raise ConfigurationError("enabled must be bool.")
        if self.backend != "sqlite" or self.queue_overflow != "drop_new":
            raise ConfigurationError("Only sqlite and drop_new are supported in this release.")
        if not isinstance(self.raw_capture, bool) or not self.raw_capture:
            raise ConfigurationError("This release uses a response cache; use storage=False to disable it.")
        for k in ("queue_max_jobs", "queue_max_bytes"):
            positive(k, getattr(self, k), integer=True)
        for k in ("read_timeout", "offline_read_timeout", "busy_timeout"):
            positive(k, getattr(self, k))
        positive("failure_cooldown", self.failure_cooldown, zero=True)
        if self.path is not None and not isinstance(self.path, (str, Path)):
            raise ConfigurationError("path must be str or Path.")

@dataclass(frozen=True, kw_only=True)
class FreshnessPolicy:
    """Define age limits and acceptance rules for cached data.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    max_age: timedelta | None = None
    allow_stale: bool = False
    max_stale: timedelta | None = None
    max_source_age: timedelta | None = None

    def __post_init__(self):
        """Validate and normalize dataclass fields after initialization.
        
        Raises:
            ConfigurationError: When the corresponding validation or operation fails."""
        for name in ("max_age", "max_stale", "max_source_age"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, timedelta) or value < timedelta(0)):
                raise ConfigurationError(f"{name} must be a nonnegative timedelta or None.")
        if not isinstance(self.allow_stale, bool):
            raise ConfigurationError("allow_stale must be bool.")

@dataclass(frozen=True, kw_only=True)
class FetchPolicy:
    """Define network, cache and offline fetching behavior.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    mode: Literal["auto", "online", "offline"] | None = None
    freshness: FreshnessPolicy | None = None
    coverage: Literal["raise", "report"] = "report"
    allow_official_offline: bool = False

    def __post_init__(self):
        """Validate and normalize dataclass fields after initialization.
        
        Raises:
            ConfigurationError: When the corresponding validation or operation fails."""
        if self.mode is not None and (not isinstance(self.mode, str) or self.mode not in ("auto", "online", "offline")):
            raise ConfigurationError("Invalid access mode.")
        if not isinstance(self.coverage, str) or self.coverage not in ("raise", "report"):
            raise ConfigurationError("Invalid coverage policy.")
        if not isinstance(self.allow_official_offline, bool):
            raise ConfigurationError("allow_official_offline must be bool.")
        if self.freshness is not None and not isinstance(self.freshness, FreshnessPolicy):
            raise ConfigurationError("freshness must be FreshnessPolicy.")


    @classmethod
    def offline(cls, *, allow_stale: bool = False, max_stale: timedelta | None = None,
                coverage: Literal["raise", "report"] = "report") -> FetchPolicy:
        """No HTTP. Stale cache requires explicit allow_stale=True."""
        return cls(mode="offline", freshness=FreshnessPolicy(
            allow_stale=allow_stale, max_stale=max_stale), coverage=coverage)

    @classmethod
    def fresh(cls, *, coverage: Literal["raise", "report"] = "report") -> FetchPolicy:
        """Force a network read for each request, without stale fallback."""
        return cls(mode="online", freshness=FreshnessPolicy(max_age=timedelta(0)),
                   coverage=coverage)


def coerce_policy(policy: FetchPolicy | str | None) -> FetchPolicy | None:
    """Resolve a documented shorthand; it never silently authorizes stale quotes."""
    if policy is None or isinstance(policy, FetchPolicy):
        return policy
    if isinstance(policy, str) and policy in ("auto", "online", "offline"):
        return FetchPolicy(mode=policy)
    raise ConfigurationError(
        "policy must be FetchPolicy, 'auto', 'online', 'offline', or None. "
        "Use FetchPolicy.offline(allow_stale=True) to explicitly read old cached data.")

@dataclass(frozen=True, kw_only=True)
class ClientConfig:
    """Combine network, storage, freshness and numeric settings.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    source: Literal["public", "official"] = "public"
    mode: Literal["auto", "online", "offline"] = "auto"
    storage: StorageConfig | None = None
    network: NetworkConfig | None = None
    numeric: Literal["analysis", "exact"] = "analysis"
    timezone: str = "Asia/Tehran"
    strict_schema: bool = True

    def __post_init__(self):
        """Validate and normalize dataclass fields after initialization.
        
        Raises:
            ConfigurationError: When the corresponding validation or operation fails."""
        if not isinstance(self.source, str) or not isinstance(self.mode, str) or self.source not in ("public", "official") or self.mode not in ("auto", "online", "offline"):
            raise ConfigurationError("Invalid source or mode.")
        if not isinstance(self.numeric, str) or self.numeric not in ("analysis", "exact"):
            raise ConfigurationError("numeric must be analysis or exact.")
        if not isinstance(self.strict_schema, bool) or not self.strict_schema:
            raise ConfigurationError("This release always requires mandatory response fields.")
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError, TypeError) as exc:
            raise ConfigurationError("Unknown timezone.") from exc
        if self.storage is None:
            object.__setattr__(self, "storage", StorageConfig())
        if self.network is None:
            object.__setattr__(self, "network", NetworkConfig())
        if not isinstance(self.storage, StorageConfig) or not isinstance(self.network, NetworkConfig):
            raise ConfigurationError("Use StorageConfig and NetworkConfig.")
