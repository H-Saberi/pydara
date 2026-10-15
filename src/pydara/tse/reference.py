"""Read the installed public API catalog; never initialize a data client."""
from __future__ import annotations
from importlib.resources import files
import json
import pandas as pd
from pydara.tse._core.exceptions import InvalidArgumentError


def api_reference(name: str | None = None) -> pd.DataFrame:
    """Return signatures, inputs, outputs, errors and dependencies for this release.

    name is an optional exact public function/class name. The catalog includes
    implemented API only; the HTML roadmap has separate not-yet-implemented plans.
    """
    rows = json.loads(files(__package__).joinpath('api_catalog.json').read_text(encoding='utf-8'))
    if name is not None:
        if not isinstance(name, str): raise InvalidArgumentError('name must be a string or None.')
        rows = [r for r in rows if r['name'] == name]
        if not rows: raise InvalidArgumentError(f'Unknown implemented API name: {name!r}.')
    return pd.DataFrame(rows)


def examples(name: str | None = None) -> pd.DataFrame:
    """Runnable usage snippets. Network examples are labeled; no snippet is executed."""
    rows=[
        {'name':'sample','network':False,'code':"from pydara import tse\ndf = tse.load_sample()\ndisplay(tse.select(df))"},
        {'name':'history','network':True,'code':"from pydara import tse\ntse.setup(network='direct')\ndf = tse.history('\u0641\u0648\u0644\u0627\u062f', start='1403-01-01', end='1403-12-30')"},
        {'name':'download','network':True,'code':"result = tse.download(['\u0641\u0648\u0644\u0627\u062f'], start='1403-01-01', end='1403-12-30', checkpoint_dir='pydara_jobs')\ndisplay(result.requests)\ndisplay(result.errors)"},
        {'name':'export','network':False,'code':"tse.export(df, 'history.csv', overwrite=True)\nrestored = tse.load('history.csv')"},
        {'name':'trades','network':True,'code':"trades = tse.get_trades('\u0641\u0648\u0644\u0627\u062f', day='1403-07-01', calendar='jalali')"},
    ]
    if name is not None:
        rows=[r for r in rows if r['name']==name]
        if not rows:raise InvalidArgumentError('Unknown example; call examples() to list them.')
    return pd.DataFrame(rows)


def help(name: str | None = None) -> pd.DataFrame:
    """Persian-aware API catalog, returned as a DataFrame without printing or network."""
    return api_reference(name)


def columns(schema: str = 'daily_bars', *, numeric='analysis') -> pd.DataFrame:
    """Alias for schema_info; no duplicate column registry."""
    from .pandas_tools import schema_info
    return schema_info(schema,numeric=numeric)
