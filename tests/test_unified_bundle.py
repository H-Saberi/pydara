"""Packaging-only checks; network access is forbidden by the shared conftest."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('dara_bundle_installer', ROOT/'install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def test_exact_manifest_wheel_used_even_with_older_wheels():
    manifest=installer.load_manifest()
    wheels=[ROOT/manifest['wheel']]
    assert wheels[0].is_file()
    assert manifest['runtime_code_changed'] is True
    assert hashlib.sha256(wheels[0].read_bytes()).hexdigest()==manifest['wheel_sha256']


def test_runtime_source_matches_bundled_wheel():
    manifest=installer.load_manifest()
    with ZipFile(ROOT/manifest['wheel']) as z:
        for name in z.namelist():
            if name.startswith('pydara/') and not name.endswith('/'):
                assert (ROOT/'src'/name).read_bytes()==z.read(name)


def test_full_install_is_one_command():
    m=installer.load_manifest()
    cmd=installer.build_command(m, executable='chosen-python')
    assert cmd[:4]==['chosen-python','-m','pip','install']
    assert cmd[-1].startswith('pydara[files,notebook] @ file:')
    assert '--only-binary=:all:' in cmd
    assert cmd.count('install')==1


def test_core_profile_is_explicit():
    cmd=installer.build_command(installer.load_manifest(),core_only=True)
    assert cmd[-1].startswith('pydara @ file:')
    assert '[files' not in cmd[-1]


def test_paths_with_spaces_use_file_uri(tmp_path):
    root=tmp_path/'project with spaces'
    cmd=installer.build_command(installer.load_manifest(),root=root)
    assert 'project%20with%20spaces' in cmd[-1]


def test_no_index_and_wheelhouse_are_explicit(tmp_path):
    cmd=installer.build_command(installer.load_manifest(),no_index=True,wheelhouse=tmp_path)
    assert '--no-index' in cmd and '--find-links' in cmd
    assert str(tmp_path.resolve()) in cmd


def test_tampered_wheel_rejected(tmp_path):
    m=installer.load_manifest()
    (tmp_path/'BUNDLE.json').write_text(json.dumps(m))
    (tmp_path/'dist').mkdir()
    (tmp_path/m['wheel']).write_bytes(b'not the original wheel')
    with pytest.raises(ValueError,match='checksum'):
        installer.load_manifest(tmp_path)


def test_path_escape_rejected(tmp_path):
    m=installer.load_manifest()
    m['wheel']='../outside.whl'
    (tmp_path/'BUNDLE.json').write_text(json.dumps(m))
    with pytest.raises(ValueError,match='outside'):
        installer.load_manifest(tmp_path)


def test_plan_does_not_call_pip(monkeypatch,capsys):
    def forbidden(*a,**k): raise AssertionError('plan invoked subprocess')
    monkeypatch.setattr(subprocess,'run',forbidden)
    assert installer.main(['--plan'])==0
    assert 'Plan only' in capsys.readouterr().out


@pytest.mark.parametrize('name', ['03_history_offline.ipynb','04_history_live.ipynb'])
def test_version_assertions_updated(name):
    nb=json.loads((ROOT/'examples'/name).read_text(encoding='utf-8'))
    code='\n'.join(''.join(c.get('source',[])) for c in nb['cells'] if c['cell_type']=='code')
    from pydara import __version__
    assert f'assert pydara.__version__ == "{__version__}"' in code
    assert 'from dara ' not in code and 'import dara' not in code


def test_all_notebooks_preserved_without_outputs():
    notebooks=sorted((ROOT/'examples').glob('*.ipynb'))
    assert len(notebooks)>=19
    for original in ("01_offline_demo.ipynb", "03_history_offline.ipynb", "09_part3_async.ipynb"):
        assert (ROOT/"examples"/original).is_file()
    for path in notebooks:
        nb=json.loads(path.read_text(encoding='utf-8'))
        for cell in nb['cells']:
            if cell['cell_type']=='code':
                assert cell['outputs']==[] and cell['execution_count'] is None


def test_windows_wrapper_calls_single_installer():
    script=(ROOT/'INSTALL_WINDOWS.bat').read_text()
    assert '%~dp0install.py' in script
    assert 'pip install' not in script
    assert 'rmdir' not in script.lower()


def test_current_migration_guide_describes_public_namespace():
    guide=(ROOT/'docs'/'MIGRATION_FA.md').read_text(encoding='utf-8')
    assert 'from pydara import tse' in guide
    assert 'pydara.tse' in guide
