# PyDara

Source release **0.7.3a6**. PyDara is a modular Python library for financial data.
The PyPI distribution is named **`pydara`**; its Python import is **`pydara`**.
The currently implemented public module is **`pydara.tse`**, providing TSETMC
quotes, instrument lookup, history, market data, sync/async workflows, Pandas
outputs, versioned SQLite storage and typed file exports.

## Install

Requires Python 3.12 or newer. The following PyPI command is for the previously published 0.6.0a2 release:

```console
python -m pip install --upgrade pydara==0.6.0a2
```

Optional Excel, Parquet and notebook support:

```console
python -m pip install --upgrade "pydara[files,notebook]==0.6.0a2"
```

For a local release bundle, activate your Python environment and run
`python install.py` (`--core-only` omits optional file/notebook dependencies).
Restart the Jupyter kernel after installation or upgrade.

## Install this GitHub source version

The source snapshot in this repository is **0.7.3a6**. To install it:

```console
git clone https://github.com/H-Saberi/pydara.git
cd pydara
python -m pip install .
```

For file exports and notebooks, use `python -m pip install ".[files,notebook]"`.
The local bundle installer requires a built wheel; a source checkout can be
installed directly with pip as shown above. GitHub publication does not publish
a new release to PyPI.

## Use

```python
from pydara import tse

# Synthetic teaching data; no external request.
sample = tse.load_sample()
reference = tse.api_reference('assets')

# Real data: network access or an eligible cache entry is required.
matches = tse.assets(symbol="فولاد", on_multiple="all")
history = tse.history("فولاد", start="1403-01-01", end="1403-12-30")
```

```python
from pydara.tse import Client, AsyncClient
from pydara.tse.exceptions import PyDaraError
```

Instrument lookup defaults to all matching rows. `on_multiple="first"` returns
the first source-ordered match; `"error"` rejects ambiguity.
`on_conflict="error"` checks supplied constraints. `"ins_code"` explicitly
prioritizes a supplied instrument code.

## Scope and data contracts

The TSE module includes public quotes/history, market watch, client types,
indices, reported trades/books/states/thresholds, ownership/share counts,
adjustment events, source-adjusted chart data, fund/NAV data, messages and
options. Availability depends on the source endpoint. The separate futures
exchange gateway is experimental. Current catalog coverage is not a complete
historical instrument registry. Source-adjusted data does not certify total
return or point-in-time history.

Analysis, ML, Bitcoin, exchange rates, gold and other countries' markets are
planned extensions. They are not implemented modules in this release.

Importing `pydara` creates no network connection, database or worker thread.
Explicit offline use is `tse.FetchPolicy.offline(allow_stale=True)`.
A queued storage receipt is not durable storage. Preserve the JSON sidecar
when copying a CSV PyDara archive.

## Upgrade to 0.6.0a2

The distribution, source package and Python import are all named `pydara`.
Use `from pydara import tse` or `import pydara.tse` in every application and notebook.
Exceptions are under `pydara.tse.exceptions`, with `PyDaraError` as the base error.
New frame metadata uses `frame.attrs['pydara']`; new archives use `pydara-frame`.
New caches use the `pydara` application directory and `pydara.sqlite3` filename.
Existing cache databases and archives can still be read; legacy identifiers are
handled only for compatibility. Existing databases are not deleted or renamed.
See [migration instructions](docs/MIGRATION_FA.md).

## Documentation and development

- [Persian guide](README_FA.md)
- [API reference](docs/API_REFERENCE.md)
- [Roadmap](docs/ROADMAP_FA.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)

```console
python -m pip install -e ".[test,files]" build twine
python tools/generate_api_reference.py
python -m build --wheel --outdir dist
python tools/update_bundle.py
python -m pytest -q
```

Offline/synthetic tests verify local contracts and do not certify live source
accuracy or endpoint availability. The code is MIT licensed; data rights are
separate from the code license.


## Plural facade (0.6.0a9)
`from pydara import tse` — `tse.assets()`, `tse.prices(assets=...)`, `tse.history(assets=...)`, `tse.traders(assets=...)`. No-argument assets enumerates only currently observed market-watch securities, not a complete historical registry. Public one-word DataFrame columns do not change cached schemas.

## Version 0.7.0: six coherent DataFrame functions

Use `tse.markets()` -> `tse.assets(markets=...)` -> `tse.prices(assets=...)`, `tse.history(assets=...)`, `tse.traders(assets=...)`, `tse.orders(assets=...)`. `tse.prices(markets=...)` retrieves the current observed bulk watch. Its one-word `change`, `return` (fraction), `returnpct` (percent) columns compare closing price to previous reference price, not dividend-adjusted total return. `orders()` exposes up to five *reported* best-depth levels. Market/identity sources and timestamps are not necessarily atomic; see `attrs['pydara']`.

Release 0.7.0 is not on PyPI. Install from the local wheel or run `python install.py` from the extracted project folder.


PyDara 0.7.2: `tse.assets(markets=tse.markets("TSE"), symbol=["فولاد", "وبملت"])` selects multiple named assets. The former `market=` keyword is no longer accepted by `assets()`; use `markets=`. If a market identifier is unavailable in both provider watch formats, the call raises rather than guessing.


### 0.7.3a1: incomplete market labels
`assets(markets=...)` reads the observed watch without server-side market filtering, returns only rows whose market matches a verified label, and records excluded unknown labels in `DataFrame.attrs["pydara"]["unknown_market_rows_excluded"]`. It does not claim complete historical coverage.

## Market-qualified watch and bulk quotes (0.7.3a2)

Use `tse.markets("TSE")`, `tse.assets(markets=selected)` and
`tse.prices(assets=assets)` for a market-to-asset-to-quote workflow.
The documented server-side exchange selector is used for market-scoped watch
requests; labels derived from that selector are marked as such, and
contradictory responses are not force-classified. Without selection, unknown
markets remain unknown. A large selected assets DataFrame uses one bulk watch
first, then per-code fallback for codes absent from the snapshot. This is an
observed current watch, not a certified complete listing or historical registry.

### Reported intraday executions

`tse.trades(assets=selected, start="1405-07-01", end="1405-07-22", starttime="09:00", endtime="12:30")` returns a Pandas DataFrame of source-reported executions. Inputs may be an assets DataFrame or explicit `ins_code` identifiers. Date strings may be Jalali or Gregorian; filtering clock times are Tehran local. No complete-tape guarantee is made. The output keeps one-word columns and structured metadata at `df.attrs["pydara"]`.


## PyDara 0.7.3a5 — controlled trades batches
`tse.trades()` defaults to `maxassets=20` and `progress=True`. Increase `maxassets` explicitly for larger work. Supply `checkpoint="./trades_checkpoints"` to persist successful per-instrument responses as JSON; reusing the same path and request parameters resumes without fetching completed instruments. `workers=1` only: the synchronous Client is not thread-safe. Checkpoint files stay on the local machine and are not part of the distributed ZIP.

Bulk `prices(assets=...)` validates closing price and trade date before accepting market-watch rows. Up to 20 individual quote repairs per call by default (`max_quote_fallback` controls the bound); remaining rows are explicitly marked unresolved in `df.attrs["pydara"]`.
