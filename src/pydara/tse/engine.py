"""Routing and caching shared by sync/async runners; persistence never owns success."""
from __future__ import annotations
from collections import OrderedDict
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
import asyncio
import threading
import sqlite3
import warnings

from platformdirs import user_data_dir

from pydara.tse._core.exceptions import (
    ClosedClientError, ConfigurationError, OfflineDataUnavailableError,
    StaleDataError, StaleDataWarning, StorageError, UnsupportedCapabilityError,
)
from pydara.tse._core.models import FlushReport, StorageStatus
from .config import ClientConfig, FetchPolicy, FreshnessPolicy, coerce_policy
from .providers.public import validate_payload
from .storage.sqlite import acquire_store


def cache_path(directory):
    """Use the PyDara filename, retaining access to an existing legacy cache."""
    directory = Path(directory)
    current = directory / "pydara.sqlite3"
    legacy = directory / "dara.sqlite3"
    return legacy if not current.exists() and legacy.is_file() else current


def default_cache_path():
    """Determine default cache path.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    current = cache_path(user_data_dir("pydara", appauthor=False))
    legacy = Path(user_data_dir("tse-dara", appauthor=False)) / "dara.sqlite3"
    return legacy if not current.exists() and legacy.is_file() else current


def build_config(config, source, mode, storage, data_dir, numeric=None):
    """Build config.
    
    Args:
        config (Any): Input for the build_config operation.
        source (Any): Input for the build_config operation.
        mode (Any): Selected operating or fetching mode.
        storage (Any): Input for the build_config operation.
        data_dir (Any): Input for the build_config operation.
        numeric (Any): Numeric conversion or output representation setting.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        ConfigurationError: When the corresponding validation or operation fails.
        UnsupportedCapabilityError: When the corresponding validation or operation fails."""
    if config is not None and not isinstance(config, ClientConfig):
        raise ConfigurationError("config must be ClientConfig.")
    config = config or ClientConfig()
    if storage is not None and not isinstance(storage, bool):
        raise ConfigurationError("storage must be bool or None.")
    st = config.storage
    if storage is not None:
        st = replace(st, enabled=storage)
    if data_dir is not None:
        if not isinstance(data_dir, (str, Path)) or isinstance(data_dir, str) and not data_dir.strip():
            raise ConfigurationError("data_dir must be a nonempty string or pathlib.Path.")
        st = replace(st, path=cache_path(data_dir))
    config = replace(config, source=config.source if source is None else source, mode=config.mode if mode is None else mode, storage=st)
    if numeric is not None:
        config = replace(config, numeric=numeric)
    if config.source != "public":
        raise UnsupportedCapabilityError("Authenticated official API is not implemented in this release.")
    return config


class Core:
    """Coordinate transport, configuration and persistent resources.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    def __init__(self, config, namespace="public"):
        """Initialize the instance and its configured state.
        
        Args:
            config (Any): Input for the __init__ operation.
            namespace (Any): Storage or frame metadata namespace."""
        self.config, self.namespace = config, namespace
        self.closed = False
        self.memory = OrderedDict()
        self.memory_bytes = 0
        self.lock = threading.RLock()
        self.store = None
        if config.storage.enabled:
            path = Path(config.storage.path) if config.storage.path is not None else \
                default_cache_path()
            self.store = acquire_store(config.storage, path.absolute())

    def check(self):
        """Check the requested value.
        
        Raises:
            ClosedClientError: When the corresponding validation or operation fails."""
        if self.closed:
            raise ClosedClientError("Client is closed; construct a new client.")

    def policy(self, spec, policy=None, freshness=None):
        """Perform the policy operation.
        
        Args:
            spec (Any): Request or schema specification.
            policy (Any): Fetch policy controlling network and cached/offline behavior.
            freshness (Any): Optional freshness criteria for returned data.
        
        Returns:
            Implementation-defined result or generator output; see the calling API.
        
        Raises:
            ConfigurationError: When the corresponding validation or operation fails."""
        self.check()
        policy = coerce_policy(policy)
        if freshness is not None and not isinstance(freshness, FreshnessPolicy):
            raise ConfigurationError("freshness must be FreshnessPolicy.")
        policy = policy or FetchPolicy()
        mode = policy.mode or self.config.mode
        fp = freshness if spec.endpoint_id == "quote.latest" else None
        fp = fp or policy.freshness or FreshnessPolicy(max_age=timedelta(seconds=spec.cache_seconds))
        max_age = fp.max_age if fp.max_age is not None else timedelta(seconds=spec.cache_seconds)
        return mode, replace(fp, max_age=max_age)

    def remember(self, packet):
        """Perform the remember operation.
        
        Args:
            packet (Any): Response packet received from a provider."""
        with self.lock:
            old = self.memory.pop(packet.cache_key, None)
            if old:
                self.memory_bytes -= len(old.content)
            self.memory[packet.cache_key] = packet
            self.memory_bytes += len(packet.content)
            while len(self.memory) > 256 or self.memory_bytes > 16 * 1024 * 1024:
                _, old = self.memory.popitem(last=False)
                self.memory_bytes -= len(old.content)

    def cached_memory(self, key):
        """Perform the cached memory operation.
        
        Args:
            key (Any): Input for the cached_memory operation.
        
        Returns:
            Implementation-defined result or generator output; see the calling API."""
        with self.lock:
            packet = self.memory.get(key)
            if packet is not None:
                self.memory.move_to_end(key)
            return packet

    def admitted(self, packet, spec, fp, *, allow_stale=False):
        """Perform the admitted operation.
        
        Args:
            packet (Any): Response packet received from a provider.
            spec (Any): Request or schema specification.
            fp (Any): Input for the admitted operation.
            allow_stale (Any): Input for the admitted operation.
        
        Returns:
            Implementation-defined result or generator output; see the calling API."""
        if packet is None:
            return None
        age = max(timedelta(0), datetime.now(UTC) - packet.fetched_at)
        fresh = age <= fp.max_age
        if not fresh and not (allow_stale and fp.allow_stale):
            return None
        if not fresh and fp.max_stale is not None and age > fp.max_stale:
            return None
        validate_payload(packet, spec, self.namespace)
        return replace(packet, from_cache=True, is_stale=not fresh)

    def accept_network(self, packet, spec):
        """Perform the accept network operation.
        
        Args:
            packet (Any): Response packet received from a provider.
            spec (Any): Request or schema specification.
        
        Returns:
            Implementation-defined result or generator output; see the calling API."""
        validate_payload(packet, spec, self.namespace)
        # Memory packets are immutable; mutations to returned frames cannot corrupt autosave.
        if self.store:
            try:
                receipt_id = self.store.submit(packet)
            except (StorageError, OSError, sqlite3.Error) as exc:
                receipt_id = self.store.reject_submission(packet, 'enqueue:' + type(exc).__name__)
            packet = replace(packet, receipt_id=receipt_id)
        self.remember(packet)
        return packet

    def disk(self, key, *, required=False):
        """Perform the disk operation.
        
        Args:
            key (Any): Input for the disk operation.
            required (Any): Input for the disk operation.
        
        Returns:
            Implementation-defined result or generator output; see the calling API.
        
        Raises:
            OfflineDataUnavailableError: When the corresponding validation or operation fails.
            StorageError: When the corresponding validation or operation fails."""
        if not self.store:
            return None
        try:
            future = self.store.request_read(key)
            if future is None:
                if required:
                    raise StorageError("The bounded local reader is busy with another request.")
                return None
            timeout = self.config.storage.offline_read_timeout if required else self.config.storage.read_timeout
            return future.result(timeout=timeout)
        except (Exception,) as exc:
            if required:
                raise OfflineDataUnavailableError("Local data is unavailable or cannot be read.") from exc
            return None

    async def adisk(self, key, *, required=False):
        """Perform the adisk operation.
        
        Args:
            key (Any): Input for the adisk operation.
            required (Any): Input for the adisk operation.
        
        Notes:
            This coroutine must be awaited.
        
        Returns:
            Implementation-defined result or generator output; see the calling API.
        
        Raises:
            OfflineDataUnavailableError: When the corresponding validation or operation fails.
            StorageError: When the corresponding validation or operation fails."""
        if not self.store:
            return None
        try:
            future = self.store.request_read(key)
            if future is None:
                if required:
                    raise StorageError("The bounded local reader is busy with another request.")
                return None
            timeout = self.config.storage.offline_read_timeout if required else self.config.storage.read_timeout
            # Shield prevents cancelling a shared reader used by another request.
            return await asyncio.wait_for(asyncio.shield(asyncio.wrap_future(future)), timeout)
        except Exception as exc:
            if required:
                raise OfflineDataUnavailableError("Local data is unavailable or cannot be read.") from exc
            return None

    def finish_quote(self, quote, freshness, policy):
        """Finalize quote.
        
        Args:
            quote (Any): Input for the finish_quote operation.
            freshness (Any): Optional freshness criteria for returned data.
            policy (Any): Fetch policy controlling network and cached/offline behavior.
        
        Returns:
            Implementation-defined result or generator output; see the calling API.
        
        Raises:
            StaleDataError: When the corresponding validation or operation fails."""
        policy = coerce_policy(policy)
        fp = freshness or (policy.freshness if policy else None)
        if fp and fp.max_source_age is not None:
            stamp = quote.source_timestamp
            age = None if stamp is None else datetime.now(UTC) - stamp
            if age is None or age < -timedelta(minutes=5) or age > fp.max_source_age:
                raise StaleDataError("Source timestamp does not satisfy max_source_age.")
        if quote.meta.is_stale:
            try:
                warnings.warn("Returning explicitly permitted cached data; this is not a live quote.",
                              StaleDataWarning, stacklevel=3)
            except StaleDataWarning:
                pass
        return quote

    def status(self):
        """Return status for the requested value.
        
        Returns:
            Implementation-defined result or generator output; see the calling API."""
        if self.store:
            return self.store.status()
        return StorageStatus(enabled=False, health="disabled", path=None, pending_jobs=0,
            pending_bytes=0, persisted_jobs=0, failed_jobs=0, skipped_jobs=0,
            last_commit_at=None, last_error=None)

    @staticmethod
    def empty_report():
        """Create an empty report.
        
        Returns:
            Implementation-defined result or generator output; see the calling API."""
        import pandas as pd
        return FlushReport(complete=True, queued_at_start=0, persisted=0, failed=0, skipped=0,
                           pending=0, elapsed_seconds=0.0, last_error=None, receipts=pd.DataFrame())

    def flush(self, timeout=5.0, raise_on_error=True):
        """Explicitly wait up to timeout seconds for queued persistence. With raise_on_error=True incomplete or failed storage raises StorageError/StorageFlushTimeout. Normal automatic saving never waits for this call.
        
        Args:
            timeout (Any): Maximum wait time in seconds.
            raise_on_error (Any): Input for the flush operation.
        
        Returns:
            Implementation-defined result or generator output; see the calling API."""
        return self.store.flush(timeout, raise_on_error) if self.store else self.empty_report()

    def release(self, timeout=1.0):
        """Perform the release operation.
        
        Args:
            timeout (Any): Maximum wait time in seconds.
        
        Returns:
            Implementation-defined result or generator output; see the calling API."""
        if self.closed:
            return self.empty_report()
        self.closed = True
        with self.lock:
            self.memory.clear()
            self.memory_bytes = 0
        return self.store.release(timeout) if self.store else self.empty_report()
