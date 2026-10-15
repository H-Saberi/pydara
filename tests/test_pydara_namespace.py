"""Contracts for the new modular distribution and its installed public API."""
import ast
import importlib
from importlib.metadata import version
from pathlib import Path
import pkgutil

import pydara
from pydara import tse


def test_only_tse_is_shipped_as_a_public_module():
    assert pydara.__all__ == ["tse", "__version__"]
    assert {m.name for m in pkgutil.iter_modules(pydara.__path__)} == {"tse"}
    assert importlib.import_module("pydara.tse") is tse
    assert version("pydara") == pydara.__version__


def test_new_exception_path_matches_client_errors():
    from pydara.tse.exceptions import InvalidArgumentError
    from pydara.tse._core.exceptions import InvalidArgumentError as InternalError
    assert InvalidArgumentError is InternalError
    assert InvalidArgumentError.__module__.startswith("pydara.tse.")


def test_no_runtime_import_depends_on_old_distribution():
    root = Path(__file__).resolve().parents[1] / "src" / "pydara"
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            assert not any(m.split('.')[0] in {"dara", "tse_dara"} for m in modules), path
