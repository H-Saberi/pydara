"""Record the current PyDara wheel checksum without touching user data."""
from pathlib import Path
from hashlib import sha256
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from pydara import __version__

def main():
    wheel = ROOT / 'dist' / f'pydara-{__version__}-py3-none-any.whl'
    if not wheel.is_file():
        raise SystemExit('Build the current PyDara wheel first.')
    manifest = {
        'bundle': 'pydara', 'bundle_revision': 1,
        'package_version': __version__, 'wheel': wheel.relative_to(ROOT).as_posix(),
        'wheel_sha256': sha256(wheel.read_bytes()).hexdigest(),
        'extras': ['files', 'notebook'], 'minimum_python': [3, 12],
        'runtime_code_changed': True,
        'runtime_files_matched': len(list((ROOT / 'src/pydara').rglob('*.py'))),
        'scope': 'PyDara with the TSE data module; no analysis or ML modules yet',
    }
    (ROOT / 'BUNDLE.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(__version__, manifest['wheel_sha256'])

if __name__ == '__main__':
    main()
