# Sources and evidence for the TSE extended feeds

Reviewed on 2026-10-14. Primary implementation sources help locate routes;
source inspection and synthetic tests DO NOT prove live availability or data completeness.
No reference-project source code or market dataset is included in this patch.
Our fixture rows are original artificial examples, labeled synthetic.

- https://github.com/5j9/tsetmc/blob/af5f4578fe4a21030759c8ed1cef3f72a00834ab/tsetmc/instruments.py
  Instrument and InstrumentOnDate paths: trades, best limits, state, thresholds,
  shareholders, adjustments, dividends, disclosures, source chart a=1.
- https://github.com/5j9/tsetmc/blob/af5f4578fe4a21030759c8ed1cef3f72a00834ab/tsetmc/funds.py
  Fund category codes, registration numbers, detail/stats fields.
- https://github.com/5j9/tsetmc/blob/af5f4578fe4a21030759c8ed1cef3f72a00834ab/tsetmc/general.py
  Board-code table location. The table is parsed, not hardcoded as current truth.
- https://github.com/yghaderi/oxtapus/blob/c0fce0ac2c4f25b5c37018ef702a36330efe7a58/src/oxtapus/providers/tsetmc/endpoint_catalog.toml
  Option-watch route and response envelope.
- https://github.com/yghaderi/oxtapus/blob/c0fce0ac2c4f25b5c37018ef702a36330efe7a58/tests/conftest.py
  Option-pair field names used for comparison, not copied fixture contents.
- https://github.com/BabakEslami/tse-market-data/blob/main/ENDPOINTS.md
  Independently maintained endpoint inventory. Futures route is a distinct TSE
  exchange gateway, not proof of official TSETMC authorization. Kept experimental.
- https://www.python-httpx.org/environment_variables/
  trust_env controls environment proxy and certificate settings. Direct use is explicit.
- https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup
  SQLite backup API is used rather than copying an open DB without its WAL.
- https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.attrs.html
  attrs are supplementary metadata, not sufficient provenance after arbitrary operations.

## Explicit limitations
Public endpoint quotas, historical extent and redistribution rights are not proven
by this implementation. No attempt to evade authorization/rate controls is made.
Financial chart source adjustment is NOT claimed as independently verified total return.
No official-account provider, prediction, analytics, model fitting or order execution
is added. The source-schema uncertainty is retained in metadata and source_fields.
get_instruments is a current-watch projection, not an inactive historical registry.
compare_sources compares two supplied tables; it does not invent independent feeds.
