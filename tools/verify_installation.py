"""Check imports/version/APIs only: no TSETMC calls and no local database writes."""
from __future__ import annotations

import argparse
import importlib
from importlib.metadata import version
import json
from pathlib import Path
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="Also require file and notebook extras.")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    expected = json.loads((root / "BUNDLE.json").read_text(encoding="utf-8"))["package_version"]
    try:
        import pydara
        from pydara import tse as data
        actual = version("pydara")
        print("Python:", sys.executable)
        print("pydara:", actual)
        print("Import path:", pydara.__file__)
        if actual != expected or pydara.__version__ != expected:
            raise RuntimeError(f"Expected {expected}, found distribution={actual}, module={pydara.__version__}")
        # Detect unexpected source checkout/PYTHONPATH shadowing the installed wheel.
        module_path = Path(pydara.__file__).resolve()
        if (root / "src").resolve() in module_path.parents:
            raise RuntimeError("The source checkout shadows the installed package. Clear PYTHONPATH and retry.")
        for name in ("Client", "AsyncClient", "get_price", "get_quote", "get_history", "get_history_many",
                     "save", "load", "sync_history", "load_stored_history", "reindex_history",
                     "configure", "get_quote_frame", "schema_info", "validate", "normalize", "load_sample", "api_reference", "get_market_watch", "get_indices", "get_index_history", "watch_market",
                     "markets", "assets", "prices", "history", "traders", "orders", "download", "setup", "get_trades", "get_order_book_history", "get_options",
                     "get_fund_nav_history", "get_adjustments", "coverage", "backup"):
            if not hasattr(data, name):
                raise RuntimeError(f"Missing API: data.{name}")
        dependencies = ["httpx", "pandas", "platformdirs", "tzdata"]
        if args.full:
            dependencies += ["openpyxl", "pyarrow", "ipykernel", "nbformat", "nbclient"]
        for name in dependencies:
            importlib.import_module(name)
            print(name + ":", version(name))
    except Exception as exc:
        print(f"Verification failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print("Imports and public APIs OK. No network request or database access was made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
