"""Shared wire contracts plus real sync/async HTTP execution. GETs only."""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import threading
import time
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from email.utils import parsedate_to_datetime

import httpx

from pydara.tse._core.exceptions import (
    ApiError, AuthenticationError, NetworkError, OperationTimeoutError,
    PermissionDeniedError, RateLimitError, RequestBudgetExceededError,
    SchemaMismatchError, ServiceUnavailableError,
)
from .config import NetworkConfig

from pydara import __version__

BASE_URL = "https://cdn.tsetmc.com/api/"

@dataclass(frozen=True)
class RequestSpec:
    """Represent request spec data used by the TSE module.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    endpoint_id: str
    path: str
    root: str
    cache_seconds: float

    def key(self, namespace: str) -> str:
        """Perform the key operation.
        
        Args:
            namespace (str): Storage or frame metadata namespace.
        
        Returns:
            str: Result of the key operation; refer to its public API contract for schema details."""
        return namespace + ":" + self.endpoint_id + ":" + self.path

@dataclass(frozen=True)
class Packet:
    """Represent packet data used by the TSE module.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    cache_key: str
    endpoint_id: str
    content: bytes
    fetched_at: datetime
    first_observed_at: datetime
    request_id: str
    payload_hash: str
    from_cache: bool = False
    is_stale: bool = False
    receipt_id: str | None = None
    committed_at: datetime | None = None

    @classmethod
    def create(cls, spec, namespace, content):
        """Create the requested value.
        
        Args:
            spec (Any): Request or schema specification.
            namespace (Any): Storage or frame metadata namespace.
            content (Any): Input for the create operation.
        
        Returns:
            Implementation-defined result or generator output; see the calling API."""
        now = datetime.now(UTC)
        # The hash refers to the exact response bytes, not an invented market revision ID.
        return cls(spec.key(namespace), spec.endpoint_id, content, now, now,
                   uuid.uuid4().hex, hashlib.sha256(content).hexdigest())


def _unique_object(pairs):
    """Process internal unique object data.
    
    Args:
        pairs (Any): Input for the _unique_object operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        SchemaMismatchError: When the corresponding validation or operation fails."""
    out = {}
    for key, value in pairs:
        if key in out:
            raise SchemaMismatchError(f"Duplicate JSON key: {key}")
        out[key] = value
    return out


def decode(packet: Packet, spec: RequestSpec):
    """Decode the requested value.
    
    Args:
        packet (Packet): Response packet received from a provider.
        spec (RequestSpec): Request or schema specification.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        SchemaMismatchError: When the corresponding validation or operation fails."""
    raw = packet.content.lstrip()
    if not raw.startswith(b"{"):
        raise SchemaMismatchError(f"{spec.endpoint_id}: expected a JSON object, not HTML/text.")
    try:
        data = json.loads(packet.content, parse_float=Decimal,
                          parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)),
                          object_pairs_hook=_unique_object)
    except (UnicodeError, ValueError) as exc:
        raise SchemaMismatchError(f"{spec.endpoint_id}: invalid JSON response.") from exc
    if not isinstance(data, dict) or spec.root not in data:
        raise SchemaMismatchError(f"{spec.endpoint_id}: missing root {spec.root!r}.")
    return data[spec.root]


class Deadline:
    """Encapsulate deadline behavior in the TSE module.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    def __init__(self, seconds: float):
        """Initialize the instance and its configured state.
        
        Args:
            seconds (float): Input for the __init__ operation."""
        self.end = time.monotonic() + seconds

    def remaining(self) -> float:
        """Perform the remaining operation.
        
        Returns:
            float: Result of the remaining operation; refer to its public API contract for schema details.
        
        Raises:
            OperationTimeoutError: When the corresponding validation or operation fails."""
        remaining = self.end - time.monotonic()
        if remaining <= 0:
            raise OperationTimeoutError("The operation exceeded its time budget.")
        return remaining


class HostGate:
    """Process-local reservation gate shared by all PyDara clients of this host."""
    def __init__(self):
        """Initialize the instance and its configured state."""
        self.lock = threading.Lock()
        self.next_at = 0.0

    def reserve(self, interval: float, deadline: Deadline) -> float:
        """Perform the reserve operation.
        
        Args:
            interval (float): Input for the reserve operation.
            deadline (Deadline): Input for the reserve operation.
        
        Returns:
            float: Result of the reserve operation; refer to its public API contract for schema details.
        
        Raises:
            OperationTimeoutError: When the corresponding validation or operation fails."""
        with self.lock:
            now = time.monotonic()
            wait = max(0.0, self.next_at - now)
            if wait >= deadline.remaining():
                raise OperationTimeoutError("Rate-limit waiting exceeds the operation budget.")
            self.next_at = max(now, self.next_at) + interval
            return wait

    def cooldown(self, seconds: float):
        """Perform the cooldown operation.
        
        Args:
            seconds (float): Input for the cooldown operation."""
        with self.lock:
            self.next_at = max(self.next_at, time.monotonic() + seconds)

_HOST_GATE = HostGate()


def retry_after(value: str | None) -> float | None:
    """Calculate retry timing for after.
    
    Args:
        value (str | None): Input for the retry_after operation.
    
    Returns:
        float | None: Result of the retry_after operation; refer to its public API contract for schema details."""
    if value is None:
        return None
    try:
        seconds = float(value)
        return max(0.0, seconds) if math.isfinite(seconds) else None
    except (ValueError, OverflowError):
        try:
            dt = parsedate_to_datetime(value)
            return max(0.0, (dt - datetime.now(UTC)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return None


def status_error(status: int, delay: float | None):
    """Return status for error.
    
    Args:
        status (int): Input for the status_error operation.
        delay (float | None): Input for the status_error operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    if status == 401:
        return AuthenticationError("TSETMC requires authentication.", status_code=status)
    if status == 403:
        return PermissionDeniedError("TSETMC refused this request.", status_code=status)
    if status == 429:
        return RateLimitError("TSETMC rate limit reached.", retry_after=delay)
    if status in {500, 502, 503, 504}:
        return ServiceUnavailableError("TSETMC is temporarily unavailable.", status_code=status)
    return ApiError(f"Unexpected HTTP status {status}; no redirects are followed.", status_code=status)


class WireBase:
    """Encapsulate wire base behavior in the TSE module.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    def __init__(self, config: NetworkConfig, transport=None):
        """Initialize the instance and its configured state.
        
        Args:
            config (NetworkConfig): Input for the __init__ operation.
            transport (Any): Input for the __init__ operation."""
        self.config = config
        self.injected_transport = transport
        # Injected test transports do not consume reservations for the actual server.
        self.gate = HostGate() if transport is not None else _HOST_GATE
        self.requests_sent = 0
        self._budget_lock = threading.Lock()
        self._client = None

    def before_attempt(self, deadline):
        """Perform the before attempt operation.
        
        Args:
            deadline (Any): Input for the before_attempt operation.
        
        Returns:
            Implementation-defined result or generator output; see the calling API.
        
        Raises:
            RequestBudgetExceededError: When the corresponding validation or operation fails."""
        deadline.remaining()
        with self._budget_lock:
            if self.requests_sent >= self.config.request_budget:
                raise RequestBudgetExceededError("This client's network request budget is exhausted.")
            self.requests_sent += 1
        return self.gate.reserve(1.0 / self.config.requests_per_second, deadline)

    def timeout(self, deadline):
        """Perform the timeout operation.
        
        Args:
            deadline (Any): Input for the timeout operation.
        
        Returns:
            Implementation-defined result or generator output; see the calling API."""
        left = deadline.remaining()
        return httpx.Timeout(connect=min(left, self.config.connect_timeout),
                             read=min(left, self.config.read_timeout),
                             write=min(left, self.config.read_timeout), pool=min(left, 5.0))

    def options(self):
        """Perform the options operation.
        
        Returns:
            Implementation-defined result or generator output; see the calling API."""
        return dict(base_url=BASE_URL, follow_redirects=False, trust_env=self.config.trust_env,
                    transport=self.injected_transport,
                    limits=httpx.Limits(max_connections=self.config.max_concurrency,
                                        max_keepalive_connections=self.config.max_concurrency),
                    headers={"Accept": "application/json", "User-Agent": f"pydara/{__version__}"})

    def size_check(self, size):
        """Perform the size check operation.
        
        Args:
            size (Any): Input for the size_check operation.
        
        Raises:
            SchemaMismatchError: When the corresponding validation or operation fails."""
        if size > self.config.max_response_bytes:
            raise SchemaMismatchError("Response exceeds the configured byte limit.")

    def pause(self, attempt, server_delay):
        """Perform the pause operation.
        
        Args:
            attempt (Any): Input for the pause operation.
            server_delay (Any): Input for the pause operation.
        
        Returns:
            Implementation-defined result or generator output; see the calling API."""
        return max(server_delay or 0.0, min(4.0, 0.5 * 2 ** attempt))


class SyncWire(WireBase):
    """Handle synchronous requests and wire response decoding.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    def request(self, spec: RequestSpec, namespace: str, deadline: Deadline) -> Packet:
        """Perform the request operation.
        
        Args:
            spec (RequestSpec): Request or schema specification.
            namespace (str): Storage or frame metadata namespace.
            deadline (Deadline): Input for the request operation.
        
        Returns:
            Packet: Result of the request operation; refer to its public API contract for schema details.
        
        Raises:
            AssertionError: When the corresponding validation or operation fails.
            error: When the corresponding validation or operation fails."""
        if self._client is None:
            self._client = httpx.Client(**self.options())
        for attempt in range(self.config.max_retries + 1):
            wait = self.before_attempt(deadline)
            time.sleep(wait)
            delay = None
            try:
                with self._client.stream("GET", spec.path, timeout=self.timeout(deadline)) as r:
                    delay = retry_after(r.headers.get("Retry-After"))
                    if r.status_code != 200:
                        error = status_error(r.status_code, delay)
                        if r.status_code == 429:
                            self.gate.cooldown(delay if delay is not None else 2.0)
                        raise error
                    chunks, size = [], 0
                    for chunk in r.iter_bytes():
                        deadline.remaining()
                        size += len(chunk)
                        self.size_check(size)
                        chunks.append(chunk)
                return Packet.create(spec, namespace, b"".join(chunks))
            except (httpx.TransportError, RateLimitError, ServiceUnavailableError) as exc:
                error = NetworkError(f"Network request failed ({type(exc).__name__}).") \
                    if isinstance(exc, httpx.TransportError) else exc
                if attempt == self.config.max_retries:
                    raise error from exc
                pause = self.pause(attempt, delay)
                if pause >= deadline.remaining():
                    raise error from exc
                time.sleep(pause)
        raise AssertionError("unreachable")

    def close(self):
        """Close the default client. Explicitly flush first to require durable writes."""
        if self._client is not None:
            self._client.close()


class AsyncWire(WireBase):
    """Handle asynchronous requests and wire response decoding.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    async def request(self, spec: RequestSpec, namespace: str, deadline: Deadline) -> Packet:
        """Perform the request operation.
        
        Args:
            spec (RequestSpec): Request or schema specification.
            namespace (str): Storage or frame metadata namespace.
            deadline (Deadline): Input for the request operation.
        
        Notes:
            This coroutine must be awaited.
        
        Returns:
            Packet: Result of the request operation; refer to its public API contract for schema details.
        
        Raises:
            AssertionError: When the corresponding validation or operation fails.
            OperationTimeoutError: When the corresponding validation or operation fails.
            error: When the corresponding validation or operation fails."""
        if self._client is None:
            self._client = httpx.AsyncClient(**self.options())
        for attempt in range(self.config.max_retries + 1):
            wait = self.before_attempt(deadline)
            await asyncio.sleep(wait)
            delay = None
            try:
                async with asyncio.timeout(deadline.remaining()):
                    async with self._client.stream("GET", spec.path, timeout=self.timeout(deadline)) as r:
                        delay = retry_after(r.headers.get("Retry-After"))
                        if r.status_code != 200:
                            error = status_error(r.status_code, delay)
                            if r.status_code == 429:
                                self.gate.cooldown(delay if delay is not None else 2.0)
                            raise error
                        chunks, size = [], 0
                        async for chunk in r.aiter_bytes():
                            deadline.remaining()
                            size += len(chunk)
                            self.size_check(size)
                            chunks.append(chunk)
                return Packet.create(spec, namespace, b"".join(chunks))
            except TimeoutError as exc:
                raise OperationTimeoutError("The operation exceeded its time budget.") from exc
            except (httpx.TransportError, RateLimitError, ServiceUnavailableError) as exc:
                error = NetworkError(f"Network request failed ({type(exc).__name__}).") \
                    if isinstance(exc, httpx.TransportError) else exc
                if attempt == self.config.max_retries:
                    raise error from exc
                pause = self.pause(attempt, delay)
                if pause >= deadline.remaining():
                    raise error from exc
                await asyncio.sleep(pause)
        raise AssertionError("unreachable")

    async def aclose(self):
        """Perform the aclose operation.
        
        Notes:
            This coroutine must be awaited."""
        if self._client is not None:
            await self._client.aclose()
