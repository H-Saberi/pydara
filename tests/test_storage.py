from dataclasses import replace
from datetime import datetime, timedelta, UTC
from decimal import Decimal
import sqlite3
import threading
import time
import warnings

import httpx
import pytest

from pydara.tse import Client, ClientConfig, NetworkConfig, StorageConfig, FetchPolicy, FreshnessPolicy
from pydara.tse.samples import sample_client, sample_transport
from pydara.tse.exceptions import *

FOLAD = "\u0641\u0648\u0644\u0627\u062f"
STALE = FetchPolicy(mode="offline", freshness=FreshnessPolicy(allow_stale=True))


def test_default_is_lazy_and_flush_makes_durable(tmp_path):
    p=tmp_path/'cache'
    with sample_client(storage=True,data_dir=p) as c:
        assert not p.exists()
        assert c.storage_status().health == "not_started"
        q=c.get_quote(FOLAD)
        report=c.flush()
        assert report.complete
        assert (p/'pydara.sqlite3').is_file()
        assert c.get_write_receipt(q.meta.storage_receipt_id).state == "persisted"
        assert c.storage_status().pending_bytes == 0


def test_storage_disabled_never_creates_directory(tmp_path):
    p=tmp_path/'disabled'
    with sample_client(data_dir=p,storage=False) as c:
        c.get_quote(FOLAD)
        assert c.flush().complete
        assert c.storage_status().enabled is False
    assert not p.exists()


def test_offline_round_trip_sends_no_network(tmp_path):
    with sample_client(storage=True,data_dir=tmp_path) as c:
        expected=c.get_quote(FOLAD)
        c.flush()
    with sample_client(storage=True,data_dir=tmp_path,mode="offline") as c:
        with pytest.warns(StaleDataWarning):
            q=c.get_quote(FOLAD,policy=STALE)
        assert q.last_price == expected.last_price
        assert q.meta.from_cache and q.meta.is_stale
        assert q.retrieved_at == expected.retrieved_at
        assert q.meta.available_at == expected.meta.available_at
        assert c.request_count == 0


def test_offline_without_cache_never_networks(tmp_path):
    with sample_client(storage=True,data_dir=tmp_path,mode="offline") as c:
        with pytest.raises(OfflineDataUnavailableError):
            c.get_quote(FOLAD,policy=STALE)
        assert c.request_count == 0


def test_no_silent_offline_stale(tmp_path):
    with sample_client(storage=True,data_dir=tmp_path) as c:
        c.get_quote(FOLAD);c.flush()
    with sample_client(storage=True,data_dir=tmp_path,mode="offline") as c:
        with pytest.raises(StaleDataError):
            c.get_quote(FOLAD)


def test_duplicate_payload_not_duplicated_but_fetch_log_preserved(tmp_path):
    with sample_client(storage=True,data_dir=tmp_path) as c:
        c.get_quote(FOLAD);c.get_quote(FOLAD);c.flush()
    with sqlite3.connect(tmp_path/'pydara.sqlite3') as db:
        n=db.execute("select count(*) from response_versions where endpoint_id='quote.latest'").fetchone()[0]
        fetches=db.execute("select count(*) from observations where cache_key like '%quote.latest%'").fetchone()[0]
    assert n==1
    assert fetches==2


def test_store_failure_does_not_break_quote(tmp_path,monkeypatch):
    with sample_client(storage=True,data_dir=tmp_path) as c:
        def fail(packet):raise OSError("disk full simulated")
        monkeypatch.setattr(c._core.store,"_write",fail)
        with warnings.catch_warnings():
            warnings.simplefilter("error",StorageWarning)
            q=c.get_quote(FOLAD)
            report=c.flush(raise_on_error=False)
        assert q.last_price == Decimal('1234.5')
        assert not report.complete
        assert report.failed > 0
        with pytest.raises(StorageError):c.flush()


def test_unwritable_path_continues(tmp_path):
    path=tmp_path/'is_file';path.write_text('x')
    with sample_client(storage=True,data_dir=path) as c:
        q=c.get_quote(FOLAD)
        report=c.flush(raise_on_error=False)
        assert q.last_price is not None and not report.complete


def test_queue_full_is_visible_not_blocking(tmp_path,monkeypatch):
    gate=threading.Event()
    cfg=ClientConfig(storage=StorageConfig(queue_max_jobs=1),
        network=NetworkConfig(requests_per_second=1_000_000,max_retries=0))
    with Client(config=cfg,data_dir=tmp_path,transport=sample_transport()) as c:
        real=c._core.store._write
        def block(packet):
            gate.wait(2)
            return real(packet)
        monkeypatch.setattr(c._core.store,'_write',block)
        start=time.monotonic()
        try:
            q=c.get_quote(FOLAD)
            assert time.monotonic()-start < 1
            assert q.last_price is not None
            assert c.storage_status().skipped_jobs >= 1
        finally:gate.set()
        report=c.flush(raise_on_error=False)
        assert report.skipped>=1 and not report.complete


def test_byte_limit(tmp_path):
    cfg=ClientConfig(storage=StorageConfig(queue_max_bytes=1),
        network=NetworkConfig(requests_per_second=1_000_000,max_retries=0))
    with Client(config=cfg,data_dir=tmp_path,transport=sample_transport()) as c:
        assert c.get_price(FOLAD)==Decimal('1234.5')
        assert c.storage_status().skipped_jobs==3
        assert c.storage_status().pending_bytes==0


def test_flush_timeout_is_explicit(tmp_path,monkeypatch):
    gate=threading.Event()
    with sample_client(storage=True,data_dir=tmp_path) as c:
        real=c._core.store._write
        def block(p):gate.wait(2);return real(p)
        monkeypatch.setattr(c._core.store,'_write',block)
        try:
            c.get_quote(FOLAD)
            with pytest.raises(StorageFlushTimeout):c.flush(timeout=.01)
        finally:gate.set()
        assert c.flush().complete


def test_two_clients_share_writer(tmp_path):
    with sample_client(storage=True,data_dir=tmp_path) as a:
        with sample_client(storage=True,data_dir=tmp_path) as b:
            assert a._core.store is b._core.store
            a.get_quote(FOLAD);b.get_quote(FOLAD)
        assert a.get_price(FOLAD) == Decimal('1234.5')
        assert a.flush().complete


def test_cache_checksum_checked(tmp_path):
    with sample_client(storage=True,data_dir=tmp_path) as c:
        c.get_quote(FOLAD);c.flush()
    with sqlite3.connect(tmp_path/'pydara.sqlite3') as db:
        db.execute("update response_versions set payload=?",(b'{}',))
    with sample_client(storage=True,data_dir=tmp_path,mode='offline') as c:
        with pytest.raises(OfflineDataUnavailableError):c.get_quote(FOLAD,policy=STALE)


def test_sample_cache_is_never_live_cache(tmp_path):
    with sample_client(storage=True,data_dir=tmp_path) as c:
        c.get_quote(FOLAD);c.flush()
    with Client(mode='offline',data_dir=tmp_path) as c:
        with pytest.raises(OfflineDataUnavailableError):c.get_quote(FOLAD,policy=STALE)


def test_optional_disk_read_has_short_wait(tmp_path,monkeypatch):
    event=threading.Event()
    with sample_client(storage=True,data_dir=tmp_path) as c:
        def slow(key):event.wait(2);return None
        monkeypatch.setattr(c._core.store,'read',slow)
        try:
            start=time.monotonic()
            assert c.get_price(FOLAD) == Decimal('1234.5')
            assert time.monotonic()-start < .8
        finally:event.set()


def test_revision_keeps_old_content(tmp_path):
    base=sample_transport(); counter=[0]
    import json
    def handler(r):
        d=json.loads(base.handle_request(r).content)
        if 'closingPriceInfo' in d:
            counter[0]+=1;d['closingPriceInfo']['pDrCotVal']=1200+counter[0]
        return httpx.Response(200,json=d)
    cfg=ClientConfig(network=NetworkConfig(requests_per_second=1_000_000,max_retries=0))
    with Client(config=cfg,data_dir=tmp_path,transport=httpx.MockTransport(handler)) as c:
        c.get_quote(FOLAD);c.get_quote(FOLAD);c.flush()
    with sqlite3.connect(tmp_path/'pydara.sqlite3') as db:
        assert db.execute("select count(*) from response_versions where endpoint_id='quote.latest'").fetchone()[0]==2


def test_queue_bookkeeping_stays_bounded_when_writer_stalls(tmp_path,monkeypatch):
    from pydara.tse.transport import Packet
    from pydara.tse.providers.public import search_spec
    gate=threading.Event()
    cfg=ClientConfig(storage=StorageConfig(queue_max_jobs=1),
        network=NetworkConfig(requests_per_second=1_000_000,max_retries=0))
    with Client(config=cfg,data_dir=tmp_path,transport=sample_transport()) as c:
        store=c._core.store;real=store._write
        def block(p):gate.wait(3);return real(p)
        monkeypatch.setattr(store,'_write',block)
        try:
            spec=search_spec('test')
            packet=Packet.create(spec,'public',b'{"instrumentSearch":[]}')
            store.submit(packet)
            for _ in range(1500):store.submit(packet)
            assert len(store.pending_sequences)==1
            assert len(store.receipts)<=1024
            assert store.status().pending_jobs==1
            assert store.flush(.01,False).pending==1
        finally:gate.set()
        c.flush(raise_on_error=False)


def test_locked_sqlite_does_not_fail_fetch(tmp_path):
    with sample_client(storage=True,data_dir=tmp_path) as c:
        c.get_quote(FOLAD);c.flush()
        db=sqlite3.connect(tmp_path/'pydara.sqlite3',timeout=.1)
        try:
            db.execute('BEGIN IMMEDIATE')
            start=time.monotonic()
            quote=c.get_quote(FOLAD)
            assert time.monotonic()-start<.8
            assert quote.last_price==Decimal('1234.5')
            report=c.flush(raise_on_error=False)
            assert not report.complete and report.failed>=1
        finally:
            db.rollback();db.close()
