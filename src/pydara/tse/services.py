"""Operation helpers. No HTTP, files, event loops, or implicit inference here."""
from datetime import datetime
from collections.abc import Sequence

from pydara.tse._core.exceptions import (
    InvalidArgumentError, MissingValueError, UnsupportedCapabilityError, UnsupportedQuoteUnitError,
)
from pydara.tse._core.models import InstrumentRef, Market, QuoteUnit
from .providers.public import search_spec, parse_search


def search_plan(query, *, market=None, include_inactive=True, limit=None, namespace="public"):
    """Search plan.
    
    Args:
        query (Any): Instrument or market search text.
        market (Any): Market selection or filtering constraint.
        include_inactive (Any): Whether inactive instruments should be retained.
        limit (Any): Optional maximum result count, where supported.
        namespace (Any): Storage or frame metadata namespace.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails.
        UnsupportedCapabilityError: When the corresponding validation or operation fails."""
    if market is not None and not isinstance(market, Market):
        raise InvalidArgumentError("market must be a Market enum.")
    if not isinstance(include_inactive, bool):
        raise InvalidArgumentError("include_inactive must be bool.")
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0):
        raise InvalidArgumentError("limit must be a positive integer or None.")
    spec = search_spec(query)
    packet = yield spec
    records = parse_search(packet, spec, namespace)
    if market is not None:
        records = [r for r in records if r.market == market]
    if not include_inactive:
        # Unknown validity is not silently interpreted as active.
        if any(r.is_active is None for r in records):
            raise UnsupportedCapabilityError("This response does not verify active/inactive identity.")
        records = [r for r in records if r.is_active]
    return records[:limit] if limit is not None else records


def price_value(quote, field):
    """Perform the price value operation.
    
    Args:
        quote (Any): Input for the price_value operation.
        field (Any): Requested data field.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails.
        MissingValueError: When the corresponding validation or operation fails.
        UnsupportedQuoteUnitError: When the corresponding validation or operation fails."""
    column = {"last": "last_price", "closing": "closing_price",
              "previous_reference": "previous_reference_price"}.get(field)
    if column is None:
        raise InvalidArgumentError("field must be last, closing, or previous_reference.")
    if quote.instrument.quote_unit != QuoteUnit.PRICE:
        raise UnsupportedQuoteUnitError("Quote units are not verified; inspect get_quote() instead.")
    value = getattr(quote, column)
    if value is None:
        raise MissingValueError(f"No {column} was reported.")
    return value


def validate_batch(instruments, on_error):
    """Validate and return an ordered immutable batch before any network I/O.

    Lists/tuples, pandas Series/Index and one-dimensional NumPy arrays are
    accepted. Strings, sets, mappings, DataFrames and null items are rejected.
    """
    import numpy as np
    import pandas as pd
    if isinstance(instruments, (pd.Series, pd.Index)):
        if isinstance(instruments, pd.MultiIndex):
            raise InvalidArgumentError("Select one symbol column, not a MultiIndex.")
        instruments = instruments.tolist()
    elif isinstance(instruments, np.ndarray):
        if instruments.ndim != 1:
            raise InvalidArgumentError("A symbol array must be one-dimensional.")
        instruments = instruments.tolist()
    if isinstance(instruments, (str, bytes)) or not isinstance(instruments, Sequence) or not len(instruments):
        raise InvalidArgumentError("Use a nonempty ordered list, Series, Index or 1D array of symbols.")
    if not isinstance(on_error, str) or on_error not in ("raise", "collect"):
        raise InvalidArgumentError("on_error must be raise or collect.")
    if len(instruments) > 10000:
        raise InvalidArgumentError("A batch is limited to 10000 inputs; split larger requests explicitly.")
    result = tuple(instruments)
    for position, item in enumerate(result):
        if not isinstance(item, (str, InstrumentRef)) or isinstance(item, str) and not item.strip():
            raise InvalidArgumentError(f"Invalid symbol at position {position}; nulls and numeric IDs are not inferred.")
    return result


def capability_frame():
    """Perform the capability frame operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    import pandas as pd
    implemented = ["search_instruments", "get_instrument", "get_quote", "get_price", "get_quotes",
                   "get_quote_frame", "get_instrument_frame", "configure", "get_config",
                   "schema_info", "validate_data", "normalize_data", "select_columns",
                   "frame_metadata", "api_reference", "validate", "normalize", "load_sample",
                   "get_history", "get_history_many", "iter_history", "to_gregorian", "to_jalali",
                   "save_csv", "save_excel", "save_parquet", "save_sqlite", "load",
                   "sync_history", "load_stored_history", "get_history_revisions", "history_status", "reindex_history"]
    implemented += ['get_market_watch', 'get_market_order_book', 'get_market_overview', 'get_market_map',
                    'get_sectors', 'get_sector_instruments', 'get_key_statistics', 'watch_market',
                    'get_market_client_types', 'clients',
                    'get_indices', 'search_indices',
                    'get_index', 'get_index_history', 'get_index_intraday', 'get_index_members',
                    'get_index_impact', 'get_index_history_many']
    implemented += ['get_adjustments', 'get_share_capital_history', 'get_dividends', 'get_adjusted_history', 'get_shareholders', 'get_shareholder_history', 'get_disclosures', 'get_messages', 'get_trades', 'get_order_book', 'get_order_book_history', 'get_instrument_states', 'get_thresholds', 'get_boards', 'get_instruments', 'get_funds', 'get_fund', 'get_fund_nav_history', 'get_options', 'get_futures', 'history', 'market', 'index_history', 'datasets', 'storage_info', 'query', 'backup', 'download', 'update', 'download_market', 'get_trades_many', 'get_order_book_updates', 'export', 'export_many', 'download_many', 'setup', 'check_connection', 'diagnose', 'to_pandas', 'set_date_index', 'select', 'concat', 'coverage', 'missing_sessions', 'compare_sources', 'examples', 'help', 'columns', 'adjustment_source']
    future = ["get_instruments", "get_adjustments", "adjustment_source", "history_as_of", "get_market_watch",
              "get_client_types", "get_index_history", "get_order_book", "get_trades",
              "postgresql_repository", "official_provider"]
    future = [n for n in future if n not in implemented]
    rows = [dict(capability_id=n, provider="public", support_status="implemented_fixture_tested",
                 required_role=None, verified_at=None, limits="bounded request budget; local rate limit",
                 coverage_evidence="source reviewed; live endpoint not tested in this build") for n in implemented]
    rows += [dict(capability_id=n, provider="official" if n == "official_provider" else "public",
                  support_status="planned_not_implemented", required_role=None, verified_at=None,
                  limits=None, coverage_evidence=None) for n in future]
    for row in rows:
        if row["capability_id"] == "save_parquet":
            row["provider"] = "local"
            row["support_status"] = "implemented_requires_pyarrow"
            row["limits"] = "optional pyarrow dependency; run local roundtrip test"
        elif row["capability_id"].startswith("save_") or row["capability_id"] in (
            "load", "load_stored_history", "get_history_revisions", "history_status", "reindex_history",
            "configure", "get_config", "schema_info", "validate_data", "normalize_data",
            "select_columns", "frame_metadata", "api_reference", "validate", "normalize", "load_sample"):
            row["provider"] = "local"
            row["limits"] = "explicit disk operation; supported schemas only"
    for row in rows:
        if row['capability_id']=='get_index_impact':
            row['support_status']='experimental_raw_fields_only'
            row['limits']='total-market effect endpoint; numeric impact mapping not verified'
        if row['capability_id']=='get_index_intraday':
            row['limits']='latest available session only; no arbitrary historic day selection'
        if row['capability_id']=='get_index_members':
            row['limits']='current endpoint membership only; no historical weights/membership'
    local_names = {'history','market','index_history'}
    local_only = {'setup','configure','diagnose','to_pandas','set_date_index','select','concat','coverage','missing_sessions','compare_sources','help','examples','columns','datasets','storage_info','query','backup','export','export_many'}
    for row in rows:
        name=row['capability_id']
        if name in local_only:
            row['provider']='local'
            row['limits']='local operations; network diagnostics require explicit opt-in'
        if name=='check_connection':row['limits']='explicit bounded probe; direct profile requires selection/consent'
        if name=='get_futures':
            row['provider']='tse_exchange'
            row['support_status']='experimental_secondary_gateway'
            row['limits']='separate webgw.tse.ir gateway, not TSETMC; live operation not verified'
        if name=='get_instruments':row['limits']='current observed market-watch universe only; inactive registry unavailable'
        if name in ('get_adjusted_history','adjustment_source'):row['limits']='source chart a=1, method and anchor recorded; no total-return/PIT guarantee'
        if name in ('missing_sessions','coverage'):row['limits']='session truth must be supplied; absence is not a holiday or halt verdict'
        if name=='compare_sources':row['limits']='compares supplied tables only; does not fetch or declare independent sources'
    return pd.DataFrame(rows).astype("string")
