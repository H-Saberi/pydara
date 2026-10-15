"""Namespace, cache and archive compatibility for the naming correction."""
from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from pydara import tse
from pydara.tse import engine
from pydara.tse.storage.codec import freeze, thaw, pack, unpack


def test_new_archives_and_metadata_use_pydara():
    frame = tse.load_sample()
    assert 'pydara' in frame.attrs and 'tse_dara' not in frame.attrs
    frozen = freeze(frame)
    assert frozen.manifest['format'] == 'pydara-frame'
    assert 'pydara' in unpack(frozen.manifest['attrs'])
    pd.testing.assert_frame_equal(thaw(frozen.manifest, frozen.rows), frame)


def test_legacy_archives_are_read_with_current_metadata():
    frame = tse.load_sample()
    frozen = freeze(frame)
    manifest = deepcopy(frozen.manifest)
    manifest['format'] = 'tse-dara-frame'
    manifest['attrs'] = pack({'tse_dara': frame.attrs['pydara']})
    restored = thaw(manifest, frozen.rows)
    pd.testing.assert_frame_equal(restored, frame)
    assert restored.attrs == frame.attrs


def test_save_normalizes_legacy_metadata_without_mutating_input():
    frame = pd.DataFrame({'value': [1]})
    frame.attrs = {'tse_dara': {'schema_id': 'custom'}}
    frozen = freeze(frame)
    assert unpack(frozen.manifest['attrs']) == {'pydara': {'schema_id': 'custom'}}
    assert 'tse_dara' in frame.attrs


def test_explicit_cache_prefers_new_name_and_falls_back_to_existing_legacy(tmp_path):
    assert engine.cache_path(tmp_path) == tmp_path / 'pydara.sqlite3'
    legacy = tmp_path / 'dara.sqlite3'
    legacy.touch()
    assert engine.cache_path(tmp_path) == legacy
    current = tmp_path / 'pydara.sqlite3'
    current.touch()
    assert engine.cache_path(tmp_path) == current


def test_default_cache_preserves_legacy_access_without_creating_directories(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, 'user_data_dir', lambda app, **kw: str(tmp_path / app))
    assert engine.default_cache_path() == tmp_path / 'pydara' / 'pydara.sqlite3'
    assert not (tmp_path / 'pydara').exists()
    legacy = tmp_path / 'tse-dara' / 'dara.sqlite3'
    legacy.parent.mkdir()
    legacy.touch()
    assert engine.default_cache_path() == legacy


@pytest.mark.parametrize('ext', ['csv', 'xlsx', 'parquet'])
def test_legacy_file_metadata_containers_are_accepted(tmp_path, ext):
    if ext == 'parquet':
        pytest.importorskip('pyarrow.parquet')
    frame = tse.load_sample()
    path = tmp_path / ('archive.' + ext)
    tse.save(frame, path)
    if ext == 'csv':
        path.with_name(path.name + '.pydara.json').rename(path.with_name(path.name + '.dara.json'))
    elif ext == 'xlsx':
        ox = pytest.importorskip('openpyxl')
        workbook = ox.load_workbook(path)
        try:
            workbook['_pydara_meta'].title = '_dara_meta'
            workbook.save(path)
        finally:
            workbook.close()
    else:
        pq = pytest.importorskip('pyarrow.parquet')
        table = pq.read_table(path)
        table = table.replace_schema_metadata({b'tse_dara': table.schema.metadata[b'pydara']})
        pq.write_table(table, path)
    restored = tse.load(path)
    pd.testing.assert_frame_equal(restored, frame)
    assert restored.attrs == frame.attrs
