"""One installation for all implemented parts, using the active Python.

Default: local wheel plus its files/notebook extras. No data migration or
network requests to TSETMC. Dependencies may be downloaded by pip.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def load_manifest(root: Path = ROOT) -> dict:
    manifest = json.loads((root / "BUNDLE.json").read_text(encoding="utf-8"))
    wheel = (root / manifest["wheel"]).resolve()
    if not wheel.is_relative_to(root.resolve()) or not wheel.is_file():
        raise ValueError("The bundled wheel is missing or outside this folder.")
    if hashlib.sha256(wheel.read_bytes()).hexdigest() != manifest["wheel_sha256"]:
        raise ValueError("Wheel checksum mismatch. Extract the original ZIP again.")
    return manifest


def build_command(manifest: dict, *, root: Path = ROOT,
                  executable: str = sys.executable, core_only: bool = False,
                  no_index: bool = False, wheelhouse: Path | None = None) -> list[str]:
    wheel = (root / manifest["wheel"]).resolve()
    extras = "" if core_only else "[" + ",".join(manifest["extras"]) + "]"
    # A PEP 508 file URL avoids quoting problems with spaces and non-ASCII paths.
    target = f"pydara{extras} @ {wheel.as_uri()}"
    command = [executable, "-m", "pip", "install", "--upgrade",
               "--upgrade-strategy", "only-if-needed", "--only-binary=:all:"]
    if no_index:
        command.append("--no-index")
    if wheelhouse is not None:
        command += ["--find-links", str(wheelhouse.resolve())]
    command.append(target)
    return command


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true", help="Verify bundle and show command only.")
    parser.add_argument("--core-only", action="store_true",
                        help="Advanced: omit optional Excel/Parquet/notebook dependencies.")
    parser.add_argument("--no-index", action="store_true",
                        help="Advanced: offline install only if dependencies already exist or are in wheelhouse.")
    parser.add_argument("--wheelhouse", type=Path, help="Directory of separately prepared dependency wheels.")
    parser.add_argument("--allow-global", action="store_true", help="Allow an explicitly chosen global interpreter.")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 12):
        print("This bundle requires Python 3.12 or newer. No changes were made.", file=sys.stderr)
        return 2
    isolated = sys.prefix != sys.base_prefix or (Path(sys.prefix) / "conda-meta").is_dir()
    if not args.plan and not args.allow_global and not isolated:
        print("Activate your project Conda/virtual environment first. No changes were made.", file=sys.stderr)
        return 2
    if not args.plan and not args.allow_global:
        active = os.environ.get("CONDA_PREFIX")
        nested = sys.prefix != sys.base_prefix
        if active and not nested and Path(active).resolve() != Path(sys.prefix).resolve():
            print("Active Conda environment and Python disagree. Check 'where python'. No changes were made.", file=sys.stderr)
            return 2
    try:
        manifest = load_manifest()
        command = build_command(manifest, core_only=args.core_only,
                                no_index=args.no_index, wheelhouse=args.wheelhouse)
    except (OSError, ValueError, KeyError) as exc:
        print(f"Invalid bundle: {exc}", file=sys.stderr)
        return 2
    print("Python:", sys.executable, flush=True)
    print("Environment:", sys.prefix, flush=True)
    print("Package version:", manifest["package_version"], flush=True)
    print("Profile:", "core only" if args.core_only else "all implemented parts + Excel/Parquet/notebook dependencies", flush=True)
    print("Command:", subprocess.list2cmdline(command), flush=True)
    if args.plan:
        print("Plan only: pip was not executed and no database was accessed.")
        return 0
    try:
        # shell=False and the selected interpreter are intentional.
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            print("Installation did not complete. Review pip's error above; do not delete your database.", file=sys.stderr)
            return result.returncode
        verify = [sys.executable, str(ROOT / "tools" / "verify_installation.py")]
        if not args.core_only:
            verify.append("--full")
        result = subprocess.run(verify, cwd=ROOT, check=False)
        if result.returncode:
            return result.returncode
    except OSError as exc:
        print(f"Could not run the installer: {exc}", file=sys.stderr)
        return 2
    print("Installation verified. Restart the Jupyter kernel before running examples.")
    print("Do NOT install Parts 1, 2, or 3 separately. All are in this one package.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
