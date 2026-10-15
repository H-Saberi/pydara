## 0.7.3a6 — Bulk quote completeness safeguards

- Validate positive closing price and valid trading date for selected bulk-watch quotes.
- Repair at most 20 incomplete/missing symbols via individual quotes by default; configure `max_quote_fallback` to opt into a different bound.
- Preserve unresolved rows as incomplete, not as synthetic prices; report deferred/failed repairs in DataFrame attrs.
- Preserve quote source and market provenance; avoid changing cache or SQLite schemas.
- Live data accuracy and all supported Python versions are not independently verified.

## 0.7.3a3

- Treat nonpositive closing prices as unavailable when calculating price returns, avoiding false -100% changes on untraded contracts.
- Preserve known assets market labels in prices() by exact inscode matching, without overriding conflicting provider labels; record fill and conflict counts in DataFrame.attrs.
- Add regression tests for bulk and individual quote paths.

## 0.7.3a2 — Verified market selection and bulk-price performance (unpublished)

- Query TSETMC's documented server market-watch selector for TSE/IFB instead of discarding all rows when `flow` is absent from the unfiltered JSON response. Mark market labels sourced from the request selector explicitly in `quality_flags` and `DataFrame.attrs['pydara']`; no name/type heuristics are used.
- If the source contradicts its selected market, refuse to infer unlabeled membership and retain only correctly labeled rows. Legacy fallback remains available for providers rejecting a filtered request.
- Preserve unfiltered `assets()` rows with unknown markets. Report incomplete coverage, unknown rows and selection provenance; do not label a snapshot a complete historical registry.
- For `prices(assets=...)` with a large DataFrame, use one source bulk watch and request individual quotes only for codes absent there, rather than requesting each price separately. Preserve explicit freshness handling and source/cache policy.
- Add regression tests for source selector, missing/contradictory labels, bulk prices and public names; preserve older unfiltered offline caches. No changes to storage schemas, caches or users' data.
- Offline synthetic tests do **not** certify live coverage, availability, or consistency of the source's market-selector behavior.

## 0.7.3a1
- Fix `assets(markets=...)` when the watch includes instruments with missing market labels: select verified matches and record excluded unknowns in DataFrame metadata. No market inference, storage migrations, or cache deletion.

## 0.7.2 - Local handoff (unpublished)

- `assets()` accepts lists of symbols, deduplicates repeated names, and retains scalar symbols and multiple `ins_code` support.
- Removed redundant `market` keyword from `assets()`; use `markets` for strings, lists, or `markets()` DataFrames.
- When the current watch lacks market identity for filtered listings, attempt the supported legacy watch backend. Never infer missing market labels.
- Added regression tests and refreshed API documentation. No change to saved cache/SQLite schema.

## 0.7.0 — Unified market-to-asset workflows (local; NOT published on PyPI)
- Added `markets()` for TSE/IFB reported overview enriched with observed breadth, verified best-limit queue counts and client-type aggregates; independent component provenance and errors retained.
- Extended `assets(markets=...)` for a market DataFrame, code or list; unrestricted selection still covers only current observed watch, NOT historical completeness.
- Extended `prices()` for bulk current-watch data and `change`, `return`, `returnpct` (unadjusted close/previous-reference price returns), and reported queue volumes when verifiable. Missing price/book values remain missing.
- Added `orders()` with bulk/selected asset lists, 1..5 depth levels, side filters, reported history updates and one-word-column DataFrame output.
- Kept `history()` and `traders()` as the existing unified asset-oriented interfaces, and preserved storage/cache schemas, identity/batch policy contracts and lower-level sync/async clients.
- Expanded Docstrings, refreshed docs/examples, updated packaging and targeted offline tests; live-source accuracy NOT verified.

## 0.6.0a9 — Plural TSE facade (local, unpublished)
- Public `assets`, `prices`, `history`, `traders` with `assets` input for the last three.
- `assets()` lists the current observed watch; accepts market, sector and other verifiable filters.
- Presentation-only one-word DataFrame column aliases (storage/cache schemas unchanged).
- Legacy private implementation retained where required by client internals; not published as module-level public names.
- Coverage caveat: observed watch is not complete historical registry; live market not verified.

## 0.6.0a8 (local; not published)

- Added unified sync/async `clients()` with instrument table or one/many ins_codes, date selection, identity and batch-error policies.
- Renamed **only** the public clients() DataFrame columns to one-word identifiers. Kept internal and persistent schemas intact.
- Removed four obsolete public client-type entrypoints; retained private data engines for existing operations.
- Documented source-vs-derived and timestamp limitations.

# 0.6.0a5 — bulk code selectors and simplified instrument API

- Accept ordered scalar or array-like `ins_code` in sync and async `instrument()` and `history()`.
- Validate every explicit code without float conversion; deduplicate and retain original order.
- Preserve lookup multiplicity/conflict policies, history batch metadata and data-fetch policies.
- Remove public `get_instrument` from module, Client, and AsyncClient; retain private single-record resolution for internal operations.
- Add offline regression tests, regenerate API reference, and rebuild the local wheel.
- This version has not been published to PyPI; live exchange accuracy is not certified.

# 0.6.0a2 — consistent pydara naming

- Use `pydara` for the distribution, source package and Python namespace.
- Expose the TSE module as `pydara.tse`.
- Update every current import, example, notebook, tool and reference.
- Use `PyDaraError`, `pydara` frame metadata and the `pydara-frame` archive marker.
- Use pydara cache names for new installations, while retaining legacy cache reads.
- Read existing archives and normalize their metadata to the current name.
- Keep existing SQLite schemas and user databases intact.

The TSE features are retained. Additional markets, analysis and ML remain planned.

# 0.6.0a3 — embedded API documentation

- Add missing class, function, and method docstrings throughout the existing `pydara.tse` implementation.
- Preserve all callable signatures and executable statements; this release is intended as documentation-only.
- Establish a source-code docstring coverage regression test and record the docstring convention for future reference generation.
- Keep market-data coverage, policy semantics, offline behavior, schema compatibility, and planned modules unchanged.
- This local version is not published to PyPI by this change.

## 0.6.0a4 — local build, not published

- Extended sync/async `history()` convenience entry points to accept instrument
  tables, explicit codes, symbol lists and individual symbols.
- Matched `instrument()` ambiguity and identity-conflict controls
  (`on_multiple='all'`, `on_conflict='error'`) without changing underlying
  fetch policy, storage or batch download/checkpoint mechanics.
- Unified multi-instrument rows in one Pandas DataFrame; added request/error
  reporting in `DataFrame.attrs['pydara']` and offline regression tests.
- `get_history()` remains the specialized lower-level API; cleanup of other
  public names is a separate API-change task.

## 0.6.0a6
- Add `tse.price()` and sync/async `Client.price()` for instrument DataFrames or single/bulk `ins_code` selectors.
- Unified quote DataFrame includes `state`, `raw_state`, `is_active`, UTC `fetched_at`, `source_timestamp`, and batch error metadata.
- Preserve quote freshness and source/cache/offline policy without asserting a live exchange timestamp.

## 0.6.0a7 (local, not published)
- Expanded parameter-level Google-style Docstrings for 106 public-facing facade and client methods, including accepted values, defaults, return types, caching caveats, and usage examples for `instrument`, `history`, and `price`.
- Updated generated API catalog/reference and Docstring regression tests. Runtime behavior and public function signatures are unchanged.

## 0.7.1 — Asset selector and request-budget diagnostics
- Restore convenient positional `assets("فولاد")` and `assets("46348559193224090")` selectors without removing `symbol=`, `ins_code=` or the unfiltered catalog path.
- Add regression tests for scalar and multiple `ins_code`, filters, conflicting locators, and network budget exhaustion.
- Document that `RequestBudgetExceededError` is a network protection limit (default 100 requests for the persistent module client), not an unsupported list input; no implicit budget reset or retry is performed.

## 0.7.3a4 — Public intraday executions
- Added `tse.trades()` with `assets` or multiple `ins_code` selectors, Jalali/Gregorian date windows, Tehran-local time filters, and one-word DataFrame columns.
- Default date window uses today's Tehran calendar date. Source timestamps without a verifiable time are excluded from restricted intraday windows.
- Reused existing source-backed trades history, storage and fetch policies. No claims of complete exchange tick coverage.


## PyDara 0.7.3a5 — controlled trades batches
`tse.trades()` defaults to `maxassets=20` and `progress=True`. Increase `maxassets` explicitly for larger work. Supply `checkpoint="./trades_checkpoints"` to persist successful per-instrument responses as JSON; reusing the same path and request parameters resumes without fetching completed instruments. `workers=1` only: the synchronous Client is not thread-safe. Checkpoint files stay on the local machine and are not part of the distributed ZIP.
