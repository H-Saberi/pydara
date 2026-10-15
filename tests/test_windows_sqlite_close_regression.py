"""A completed SQLite flush must not outlive its last client on Windows."""
import sqlite3
from pathlib import Path

from pydara.tse.storage.sqlite import acquire_store
from pydara.tse.config import StorageConfig

def test_final_release_waits_for_sqlite_writer(tmp_path):
    cfg = StorageConfig(path=tmp_path / "pydara.sqlite3")
    store = acquire_store(cfg, cfg.path)
    with store.condition:
        store.thread = __import__("threading").Thread(target=store._worker)
        store.thread.start()
    store.release(2)
    assert store.thread is None
