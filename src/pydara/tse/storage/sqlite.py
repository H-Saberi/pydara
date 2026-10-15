"""Bounded, best-effort persistence isolated from normal data retrieval.

One writer coordinator per absolute DB path per process. No disk I/O in submit().
Queued jobs are memory-only until committed; abrupt process exit can lose them.
"""
from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
import os
from pathlib import Path
import sqlite3
import threading
import time
import uuid
import warnings
from concurrent.futures import Future
from weakref import WeakValueDictionary

from pydara.tse._core.exceptions import (
    ConfigurationError, StorageError, StorageFlushTimeout, StorageWarning, UnknownReceiptError,
)
from pydara.tse._core.models import FlushReport, StorageStatus, WriteReceipt
from ..config import StorageConfig, positive
from ..transport import Packet

_REGISTRY = WeakValueDictionary()
_REGISTRY_LOCK = threading.Lock()
SCHEMA_VERSION = 1
SCHEMA = """
CREATE TABLE IF NOT EXISTS response_versions (
    cache_key TEXT NOT NULL, payload_hash TEXT NOT NULL,
    endpoint_id TEXT NOT NULL, payload BLOB NOT NULL,
    first_observed_at TEXT NOT NULL, parser_version TEXT NOT NULL,
    PRIMARY KEY (cache_key, payload_hash)
);
CREATE TABLE IF NOT EXISTS observations (
    request_id TEXT PRIMARY KEY, cache_key TEXT NOT NULL,
    payload_hash TEXT NOT NULL, fetched_at TEXT NOT NULL, committed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS latest_response (
    cache_key TEXT PRIMARY KEY, payload_hash TEXT NOT NULL,
    fetched_at TEXT NOT NULL, request_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_observations_key_time ON observations(cache_key, fetched_at);
"""


def safe_warn(message):
    # A user's warnings-as-errors policy must not turn autosave failure into fetch failure.
    """Perform the safe warn operation.
    
    Args:
        message (Any): Input for the safe_warn operation."""
    try:
        warnings.warn(message, StorageWarning, stacklevel=3)
    except Exception:
        pass


def acquire_store(config: StorageConfig, path: Path):
    """Perform the acquire store operation.
    
    Args:
        config (StorageConfig): Input for the acquire_store operation.
        path (Path): Local file or database path.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        ConfigurationError: When the corresponding validation or operation fails."""
    key = os.path.normcase(os.path.abspath(path))
    with _REGISTRY_LOCK:
        store = _REGISTRY.get(key)
        if store is None:
            store = ResponseStore(config, Path(key))
            _REGISTRY[key] = store
        elif replace(store.config, path=None) != replace(config, path=None):
            raise ConfigurationError("Clients sharing a DB path must use the same storage settings.")
        with store.condition:
            store.leases += 1
        return store


class ResponseStore:
    """Encapsulate response store behavior in the TSE module.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    def __init__(self, config: StorageConfig, path: Path):
        """Initialize the instance and its configured state.
        
        Args:
            config (StorageConfig): Input for the __init__ operation.
            path (Path): Local file or database path."""
        self.config, self.path = config, path
        self.condition = threading.Condition(threading.RLock())
        self.jobs = deque()
        self.receipts = OrderedDict()
        self.pending_bytes = 0
        self.pending_jobs = 0
        self.persisted = self.failed = self.skipped = 0
        self.submitted = 0
        self.pending_sequences = set()
        self.leases = 0
        self.thread = None
        self.connection = None  # Only ever used by the writer thread.
        self.last_error = None
        self.last_commit = None
        self.cooldown_end = 0.0
        self.ever_started = False
        self.read_lock = threading.Lock()
        self.read_future = None
        self.read_key = None

    def _terminal(self, seq):
        """Process internal terminal data.
        
        Args:
            seq (Any): Input for the _terminal operation."""
        self.pending_sequences.discard(seq)
        # Receipts are diagnostic snapshots; bounded retention avoids a growing memory leak.
        while len(self.receipts) > 1024:
            old = next((k for k, r in self.receipts.items() if r.state != "queued"), None)
            if old is None:
                break
            self.receipts.pop(old)
        self.condition.notify_all()

    def submit(self, packet: Packet) -> str:
        """Return a receipt without performing disk I/O or waiting for DB locks."""
        with self.condition:
            self.submitted += 1
            seq = self.submitted
            receipt_id = uuid.uuid4().hex
            size = len(packet.content)
            reason = None
            if time.monotonic() < self.cooldown_end:
                reason = "storage_cooldown"
            elif self.pending_jobs >= self.config.queue_max_jobs:
                reason = "queue_job_limit"
            elif self.pending_bytes + size > self.config.queue_max_bytes:
                reason = "queue_byte_limit"
            receipt = WriteReceipt(receipt_id=receipt_id, request_id=packet.request_id,
                state="skipped" if reason else "queued", accepted_at=datetime.now(UTC),
                committed_at=None, rows=1, payload_bytes=size, reason=reason,
                destination=str(self.path), content_hash=packet.payload_hash)
            self.receipts[receipt_id] = receipt
            if reason:
                self.skipped += 1
                self.last_error = reason
                self._terminal(seq)
                # Only the first skip emits a warning; status retains every count.
                if self.skipped == 1:
                    safe_warn("Automatic storage skipped a response; inspect storage_status().")
                return receipt_id
            self.jobs.append((seq, receipt_id, packet))
            self.pending_sequences.add(seq)
            self.pending_bytes += size
            self.pending_jobs += 1
            if self.thread is None:
                self.thread = threading.Thread(target=self._worker, name="pydara-tse-sqlite", daemon=True)
                try:
                    self.thread.start()
                    self.ever_started = True
                except Exception as exc:
                    self.thread = None
                    self.jobs.pop()
                    self.pending_bytes -= size
                    self.pending_jobs -= 1
                    self.failed += 1
                    self.last_error = f"writer_start:{type(exc).__name__}"
                    self.receipts[receipt_id] = replace(receipt, state="failed", reason=self.last_error)
                    self._terminal(seq)
                    safe_warn("Automatic storage writer could not start; data retrieval continues.")
            self.condition.notify_all()
            return receipt_id

    def reject_submission(self, packet: Packet, reason: str) -> str:
        """Record an enqueue failure without performing I/O or masking valid data."""
        with self.condition:
            self.submitted += 1
            receipt_id = uuid.uuid4().hex
            self.failed += 1
            self.last_error = reason
            self.cooldown_end = time.monotonic() + self.config.failure_cooldown
            self.receipts[receipt_id] = WriteReceipt(
                receipt_id=receipt_id, request_id=packet.request_id, state='failed',
                accepted_at=datetime.now(UTC), committed_at=None, rows=0,
                payload_bytes=len(packet.content), reason=reason,
                destination=str(self.path), content_hash=packet.payload_hash)
            self._terminal(self.submitted)
            safe_warn('Automatic storage submission failed; fetched data remains available.')
            return receipt_id

    def _connect(self):
        """Process internal connect data.
        
        Returns:
            Implementation-defined result or generator output; see the calling API.
        
        Raises:
            StorageError: When the corresponding validation or operation fails."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(self.path), timeout=self.config.busy_timeout)
        try:
            version = con.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, SCHEMA_VERSION):
                raise StorageError("Unsupported database schema version; no automatic downgrade.")
            if version == 0:
                # Never adopt an unrelated database containing user tables.
                tables = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                if tables:
                    raise StorageError("Existing database is not a PyDara response store.")
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA synchronous=NORMAL")
            con.executescript(SCHEMA)
            con.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            from .history_store import ensure_schema
            ensure_schema(con)
            return con
        except Exception:
            con.close()
            raise

    def _write(self, packet: Packet):
        """Write the requested value.
        
        Args:
            packet (Packet): Response packet received from a provider.
        
        Returns:
            Implementation-defined result or generator output; see the calling API."""
        if self.connection is None:
            self.connection = self._connect()
        con = self.connection
        committed = datetime.now(UTC)
        # New content versions and their latest pointer commit in one transaction.
        with con:
            con.execute("""INSERT INTO response_versions VALUES (?,?,?,?,?,?)
                ON CONFLICT(cache_key,payload_hash) DO UPDATE SET
                first_observed_at=min(first_observed_at, excluded.first_observed_at)""",
                (packet.cache_key, packet.payload_hash, packet.endpoint_id, packet.content,
                 packet.first_observed_at.isoformat(), "1"))
            con.execute("INSERT OR IGNORE INTO observations VALUES (?,?,?,?,?)",
                (packet.request_id, packet.cache_key, packet.payload_hash,
                 packet.fetched_at.isoformat(), committed.isoformat()))
            con.execute("""INSERT INTO latest_response VALUES (?,?,?,?)
                ON CONFLICT(cache_key) DO UPDATE SET payload_hash=excluded.payload_hash,
                fetched_at=excluded.fetched_at,request_id=excluded.request_id
                WHERE excluded.fetched_at >= latest_response.fetched_at""",
                (packet.cache_key, packet.payload_hash, packet.fetched_at.isoformat(), packet.request_id))
            if packet.endpoint_id == "history.daily":
                from .history_store import persist_packet
                persist_packet(con, packet, committed)
        return committed

    def _worker(self):
        """Process internal worker data.
        
        Returns:
            Implementation-defined result or generator output; see the calling API."""
        active = None
        try:
            while True:
                with self.condition:
                    while not self.jobs and self.leases:
                        self.condition.wait(0.2)
                    if not self.jobs:
                        # No I/O while holding the submit lock, including connection.close().
                        con, self.connection = self.connection, None
                        job = None
                    else:
                        job = self.jobs.popleft()
                if job is None:
                    if con is not None:
                        con.close()
                    with self.condition:
                        if self.jobs or self.leases:
                            continue
                        self.thread = None
                        self.condition.notify_all()
                        return
                seq, receipt_id, packet = job
                active = job
                committed, error = None, None
                try:
                    committed = self._write(packet)
                except Exception as exc:
                    error = f"{type(exc).__name__}: {str(exc)[:180]}"
                    if self.connection is not None:
                        self.connection.close()
                        self.connection = None
                with self.condition:
                    old = self.receipts[receipt_id]
                    self.receipts[receipt_id] = replace(old,
                        state="failed" if error else "persisted", committed_at=committed, reason=error)
                    self.pending_jobs -= 1
                    self.pending_bytes -= len(packet.content)
                    if error:
                        self.failed += 1
                        self.last_error = error
                        self.cooldown_end = time.monotonic() + self.config.failure_cooldown
                    else:
                        self.persisted += 1
                        self.last_commit = committed
                    self._terminal(seq)
                active = None
                if error:
                    safe_warn("Automatic SQLite storage failed; fetched data remains usable. "
                              "Inspect storage_status() or flush(raise_on_error=False).")
        except BaseException:
            con, self.connection = self.connection, None
            if con is not None:
                try:
                    con.close()
                except Exception:
                    pass
            with self.condition:
                remaining = ([active] if active else []) + list(self.jobs)
                self.jobs.clear()
                for seq, rid, packet in remaining:
                    self.receipts[rid] = replace(self.receipts[rid], state="failed", reason="writer_stopped")
                    self.failed += 1
                    self.pending_jobs -= 1
                    self.pending_bytes -= len(packet.content)
                    self._terminal(seq)
                self.last_error = "writer_stopped"
                self.thread = None
                self.condition.notify_all()

    def request_read(self, key: str):
        """At most one daemon disk reader per store; callers have bounded waits."""
        with self.read_lock:
            if self.read_future is not None and not self.read_future.done():
                return self.read_future if self.read_key == key else None
            future = Future()
            self.read_future, self.read_key = future, key
            def work():
                """Perform the work operation."""
                try:
                    future.set_result(self.read(key))
                except BaseException as exc:
                    future.set_exception(exc)
            threading.Thread(target=work, name="pydara-tse-reader", daemon=True).start()
            return future

    def read(self, cache_key: str) -> Packet | None:
        """Explicit offline/fallback read, not performed on the online fast path."""
        if not self.path.is_file():
            return None
        deadline = time.monotonic() + self.config.offline_read_timeout
        con = None
        try:
            con = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True,
                                  timeout=min(self.config.busy_timeout, self.config.offline_read_timeout))
            con.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
            if con.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
                raise StorageError("Unsupported PyDara database version.")
            row = con.execute("""SELECT v.endpoint_id,v.payload,v.first_observed_at,
                    l.payload_hash,l.fetched_at,l.request_id,o.committed_at
                FROM latest_response l JOIN response_versions v
                ON l.cache_key=v.cache_key AND l.payload_hash=v.payload_hash
                JOIN observations o ON l.request_id=o.request_id
                WHERE l.cache_key=?""", (cache_key,)).fetchone()
            if row is None:
                return None
            endpoint, content, first, digest, fetched, request_id, committed = row
            if sha256(content).hexdigest() != digest:
                raise StorageError("Cached response checksum mismatch.")
            return Packet(cache_key, endpoint, content, datetime.fromisoformat(fetched),
                          datetime.fromisoformat(first), request_id, digest,
                          from_cache=True, committed_at=datetime.fromisoformat(committed))
        except (sqlite3.Error, OSError, ValueError) as exc:
            raise StorageError(f"Local response store could not be read ({type(exc).__name__}).") from exc
        finally:
            if con is not None:
                con.close()

    def receipt(self, receipt_id: str) -> WriteReceipt:
        """Perform the receipt operation.
        
        Args:
            receipt_id (str): Input for the receipt operation.
        
        Returns:
            WriteReceipt: Result of the receipt operation; refer to its public API contract for schema details.
        
        Raises:
            UnknownReceiptError: When the corresponding validation or operation fails."""
        with self.condition:
            try:
                return self.receipts[receipt_id]
            except KeyError as exc:
                raise UnknownReceiptError("Receipt is unknown or outside in-memory retention.") from exc

    def status(self) -> StorageStatus:
        """Return status for the requested value.
        
        Returns:
            StorageStatus: Result of the status operation; refer to its public API contract for schema details."""
        with self.condition:
            health = "degraded" if self.failed or self.skipped else ("ok" if self.ever_started else "not_started")
            return StorageStatus(enabled=True, health=health, path=str(self.path),
                pending_jobs=self.pending_jobs, pending_bytes=self.pending_bytes,
                persisted_jobs=self.persisted, failed_jobs=self.failed, skipped_jobs=self.skipped,
                last_commit_at=self.last_commit, last_error=self.last_error)

    def flush(self, timeout=5.0, raise_on_error=True) -> FlushReport:
        """Explicitly wait up to timeout seconds for queued persistence. With raise_on_error=True incomplete or failed storage raises StorageError/StorageFlushTimeout. Normal automatic saving never waits for this call.
        
        Args:
            timeout (Any): Maximum wait time in seconds.
            raise_on_error (Any): Input for the flush operation.
        
        Returns:
            FlushReport: Result of the flush operation; refer to its public API contract for schema details.
        
        Raises:
            cls: When the corresponding validation or operation fails."""
        positive("timeout", timeout, zero=True)
        from dataclasses import asdict
        import pandas as pd
        start = time.monotonic()
        with self.condition:
            target = self.submitted
            queued = self.pending_jobs
            while any(seq <= target for seq in self.pending_sequences):
                remaining = timeout - (time.monotonic() - start)
                if remaining <= 0:
                    break
                self.condition.wait(remaining)
            pending = sum(seq <= target for seq in self.pending_sequences)
            report = FlushReport(complete=pending == 0 and not self.failed and not self.skipped,
                queued_at_start=queued, persisted=self.persisted, failed=self.failed, skipped=self.skipped,
                pending=pending, elapsed_seconds=time.monotonic()-start, last_error=self.last_error,
                receipts=pd.DataFrame([asdict(v) for v in self.receipts.values()]))
        if raise_on_error and not report.complete:
            cls = StorageFlushTimeout if pending else StorageError
            raise cls("Some automatic writes are incomplete, failed, or skipped.", report=report)
        return report

    def release(self, flush_timeout=1.0):
        """Release the lease and wait for the last writer to close SQLite.

        flush() waits for commits, not for the thread to close its connection.
        Windows cannot remove a temporary SQLite file until that close finishes.
        """
        report = self.flush(flush_timeout, False)
        with self.condition:
            self.leases = max(0, self.leases - 1)
            last_lease = self.leases == 0
            writer = self.thread
            self.condition.notify_all()
        if last_lease and writer is not None and writer is not threading.current_thread():
            # Joining happens outside the store lock, allowing the worker to
            # wake, close its SQLite connection and signal its exit.
            writer.join(timeout=max(1.0, flush_timeout))
            if writer.is_alive():
                # Do not report a fully closed store while SQLite may still
                # hold OS handles. The caller can diagnose incomplete close.
                raise StorageFlushTimeout('SQLite writer did not close before timeout.', report=report)
        return report
