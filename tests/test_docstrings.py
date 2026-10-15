"""Guard the source documentation coverage needed for a future API guide."""
import ast
from pathlib import Path


def test_every_defined_callable_and_class_has_a_docstring():
    source = Path(__file__).resolve().parents[1] / 'src' / 'pydara'
    missing = []
    for path in source.rglob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if not ast.get_docstring(node):
                    missing.append(f'{path.relative_to(source)}:{node.lineno}:{node.name}')
    assert not missing, '\n'.join(missing)


def test_key_public_docstrings_are_exposed_at_runtime():
    from pydara import tse
    from pydara.tse import Client, AsyncClient
    assert tse.__doc__
    for cls in (Client, AsyncClient):
        assert cls.__doc__
        for name in ('get_quote', 'get_history', 'search_instruments'):
            assert getattr(cls, name).__doc__


def test_primary_facade_help_includes_inputs_values_and_examples():
    from pydara import tse
    import inspect
    for name in ('markets','assets','prices','history','traders','orders'):
        doc = inspect.getdoc(getattr(tse, name))
        for section in ('Args:', 'Returns:', 'Examples:'):
            assert section in doc, (name, section)
        for param in inspect.signature(getattr(tse, name)).parameters:
            assert f'{param} (' in doc or f'{param}, ' in doc, (name, param)


def test_client_price_and_history_explain_arguments():
    from pydara.tse import Client, AsyncClient
    for cls in (Client, AsyncClient):
        for name in ('history', 'price', 'instrument'):
            doc = getattr(cls, name).__doc__
            assert doc and 'Args:' in doc and 'Returns:' in doc, (cls.__name__, name)
