"""Build the PyDara wheel, refresh the local bundle, then build its source archive."""
from pathlib import Path
import subprocess
import sys

if __name__ == '__main__':
    root=Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, '-m', 'build', '--wheel', '--outdir', 'dist'], cwd=root, check=True)
    subprocess.run([sys.executable, str(root/'tools/update_bundle.py')], cwd=root, check=True)
    subprocess.run([sys.executable, '-m', 'build', '--sdist', '--outdir', 'dist'], cwd=root, check=True)
