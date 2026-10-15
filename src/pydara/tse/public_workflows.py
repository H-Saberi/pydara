"""Composed public market, quote and order-book DataFrames.

Only source-backed fields are displayed as observations. Calculations use explicit
source fields, retain missing values and keep provenance in ``attrs['pydara']``.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
from collections.abc import Sequence
import pandas as pd
import numpy as np

from ._core.models import InstrumentRef, Market
from ._core.exceptions import InvalidArgumentError, UnsupportedCapabilityError
from .providers.market import market_value
from .instrument_lookup import lookup_policies, normalize_ins_codes
from .history_inputs import selectors


_MARKETS = ('TSE', 'IFB')  # Overview endpoints actually supported by provider.


def markets_filter(value, *, allow_base=False):
    """Validate market codes or the ``markets()`` DataFrame, preserving order.

    Args:
        value (None | str | Market | Sequence | DataFrame): Market identifiers.
        allow_base (bool): Also accept BASE when selecting market-watch assets.

    Returns:
        list[str] | None: Unique canonical market codes; None means no filter.

    Raises:
        InvalidArgumentError: Malformed or empty selection.
        UnsupportedCapabilityError: Unsupported market in the requested workflow.
    """
    if value is None:
        return None
    if isinstance(value, pd.DataFrame):
        if 'market' not in value:
            raise InvalidArgumentError('markets DataFrame requires a market column.')
        values = value['market'].tolist()
    elif isinstance(value, (str, Market)):
        values = [value]
    elif isinstance(value, (list, tuple, set, pd.Series, pd.Index, np.ndarray)):
        if isinstance(value, np.ndarray) and value.ndim != 1:
            raise InvalidArgumentError('Market selection must be one-dimensional.')
        values = list(value)
    else:
        raise InvalidArgumentError('Market selection must be a code, list, or markets DataFrame.')
    if not values:
        raise InvalidArgumentError('Market selection cannot be empty.')
    result = []
    for value in values:
        code = market_value(value).value
        if code not in (*_MARKETS, *(['BASE'] if allow_base else [])):
            raise UnsupportedCapabilityError('Requested market has no supported source endpoint.')
        if code not in result:
            result.append(code)
    return result


def _meta(frame):
    """Copy provider metadata without mutating the input DataFrame."""
    return deepcopy(frame.attrs.get('pydara', {}))


def _error(errors, part, exc, on_error):
    """Record a component failure or propagate it under the fail-fast policy."""
    if on_error == 'raise':
        raise exc
    errors.append({'component': str(part), 'error': type(exc).__name__, 'message': str(exc)})


def _oneword(frame):
    """Return caller-owned columns without underscores and copy provenance."""
    out = frame.rename(columns={c: c.replace('_', '') for c in frame.columns})
    out.attrs = deepcopy(frame.attrs)
    return out


def _safe_sum(df, name):
    """Sum existing participant values exactly; never replace missing with zero."""
    if name not in df:
        return pd.NA
    valid = [value for value in df[name] if pd.notna(value)]
    if not valid:
        return pd.NA
    try:
        return sum((Decimal(str(value)) for value in valid), Decimal(0))
    except (InvalidOperation, TypeError, ValueError):
        return pd.NA


def _queue_flags(watch, books):
    """Enrich watch rows with confirmed observable limit queues or unknowns.

    A queue requires a positive bid/ask at the daily price limit AND explicit
    zero opposite-side volume. Source omission is *not* treated as zero.
    """
    result = watch.copy()
    for field in ('buyqueue', 'sellqueue'):
        result[field] = pd.array([pd.NA] * len(result), dtype='Float64')
    result['queuereported'] = pd.array([False] * len(result), dtype='boolean')
    required = {'ins_code', 'depth', 'bid_price', 'ask_price', 'bid_volume', 'ask_volume'}
    if books is None or not required.issubset(books.columns):
        return result
    if not {'ins_code', 'min_allowed_price', 'max_allowed_price'}.issubset(result.columns):
        return result
    top = books.loc[books['depth'] == 1].drop_duplicates('ins_code', keep='first')
    if top.empty:
        return result
    lookup = top.set_index('ins_code')
    for idx, row in result.iterrows():
        code = row['ins_code']
        if pd.isna(code) or code not in lookup.index:
            continue
        book = lookup.loc[code]
        values = [book[k] for k in ('bid_price', 'ask_price', 'bid_volume', 'ask_volume')]
        minprice, maxprice = row['min_allowed_price'], row['max_allowed_price']
        if any(pd.isna(v) for v in (*values, minprice, maxprice)):
            continue
        bid, ask, buyvol, sellvol = (float(v) for v in values)
        minp, maxp = float(minprice), float(maxprice)
        if minp <= 0 or maxp <= 0 or minp > maxp or buyvol < 0 or sellvol < 0:
            continue
        result.at[idx, 'queuereported'] = True
        result.at[idx, 'buyqueue'] = buyvol if bid == maxp and buyvol > 0 and sellvol == 0 else 0.0
        result.at[idx, 'sellqueue'] = sellvol if ask == minp and sellvol > 0 and buyvol == 0 else 0.0
    return result


def returns(frame):
    """Add close-to-reference ``change``, fractional ``return`` and ``returnpct``.

    Values are unadjusted one-session *price* returns, excluding dividends and
    corporate-action total returns. Missing/nonpositive closing or reference price produces NA.
    """
    out = frame.copy()
    previous = next((c for c in ('previousreferenceprice', 'previousreference', 'prevclose') if c in out), None)
    closing = next((c for c in ('closingprice', 'close') if c in out), None)
    decimal_mode = bool(previous and closing and any(
        isinstance(v, Decimal)
        for col in (previous, closing)
        for v in out[col] if pd.notna(v)
    ))
    for field in ('change', 'return', 'returnpct'):
        out[field] = pd.Series([pd.NA] * len(out), index=out.index,
                               dtype='object' if decimal_mode else 'Float64')
    if previous and closing:
        for i in out.index:
            prev, close = out.at[i, previous], out.at[i, closing]
            if pd.isna(prev) or pd.isna(close):
                continue
            try:
                a, b = Decimal(str(prev)), Decimal(str(close))
                if not a.is_finite() or not b.is_finite() or a <= 0 or b <= 0:
                    continue
                change, ratio = b-a, b/a-Decimal(1)
            except (InvalidOperation, ValueError, TypeError, ZeroDivisionError):
                continue
            out.at[i, 'change'] = change if decimal_mode else float(change)
            out.at[i, 'return'] = ratio if decimal_mode else float(ratio)
            out.at[i, 'returnpct'] = ratio*Decimal(100) if decimal_mode else float(ratio*Decimal(100))
    out.attrs = deepcopy(frame.attrs)
    out.attrs.setdefault('pydara', {})['return_definition'] = 'closingprice/previousreferenceprice - 1 (unadjusted price return; dividends excluded)'
    return out


def market_summary(client, market=None, *, include_breadth=True, include_queues=True,
                   include_traders=True, include_indices=True, on_error='collect', policy=None):
    """Build a market-wide table from independently fetched source components.

    Args:
        client: Existing synchronized data client; no new client is created.
        market (None | str | Market | Sequence): None selects TSE and IFB.
        include_breadth (bool): Count positive/negative/flat closing-price changes.
        include_queues (bool): Count verified limit-order queues where possible.
        include_traders (bool): Include individual buy/sell *values*, if available.
        include_indices (bool): Include overview's source index fields.
        on_error (Literal['collect','raise']): Per-component failure policy.
        policy (FetchPolicy | str | None): Existing fetch/cache policy.

    Returns:
        DataFrame: One row per selected market, with one-word columns and per-
        component provenance/errors in attrs['pydara']. Missing is never zero.
    """
    if on_error not in ('collect', 'raise'):
        raise InvalidArgumentError('on_error must be collect or raise.')
    for name, flag in [('include_breadth', include_breadth), ('include_queues', include_queues),
                       ('include_traders', include_traders), ('include_indices', include_indices)]:
        if not isinstance(flag, bool):
            raise InvalidArgumentError(f'{name} must be bool.')
    selected = markets_filter(market) or list(_MARKETS)
    records, errors, components = [], [], []
    for code in selected:
        row = {'market': code}
        overview = None
        try:
            overview = client.get_market_overview(market=code, policy=policy)
            components.append({'market': code, 'part': 'overview', 'metadata': _meta(overview)})
            if not overview.empty:
                row.update(_oneword(overview).iloc[0].to_dict())
                row['market'] = code
        except Exception as exc:
            _error(errors, f'{code}.overview', exc, on_error)
        if not include_indices:
            for field in ('indexvalue', 'indexchange', 'equalweightindexvalue', 'equalweightindexchange', 'indexunit'):
                row.pop(field, None)
        if include_breadth or include_queues:
            try:
                watch = client.get_market_watch(market=code, include_order_book=include_queues, policy=policy)
                components.append({'market': code, 'part': 'watch', 'metadata': _meta(watch)})
                if include_breadth:
                    prev = pd.to_numeric(watch.get('previous_reference_price', pd.Series(dtype=float)), errors='coerce')
                    close = pd.to_numeric(watch.get('closing_price', pd.Series(dtype=float)), errors='coerce')
                    valid = prev.notna() & close.notna() & (prev > 0)
                    row['positive'] = int((valid & (close > prev)).sum())
                    row['negative'] = int((valid & (close < prev)).sum())
                    row['unchanged'] = int((valid & (close == prev)).sum())
                    row['breadthknown'] = int(valid.sum())
                    if not valid.any():
                        for k in ('positive', 'negative', 'unchanged', 'breadthknown'):
                            row[k] = pd.NA
                if include_queues:
                    books = _book_from_watch(watch)
                    queued = _queue_flags(watch, books)
                    if queued['queuereported'].any():
                        row['buyqueues'] = int((queued['buyqueue'] > 0).sum())
                        row['sellqueues'] = int((queued['sellqueue'] > 0).sum())
                        row['queueknown'] = int(queued['queuereported'].sum())
                    else:
                        row.update(buyqueues=pd.NA, sellqueues=pd.NA, queueknown=pd.NA)
            except Exception as exc:
                _error(errors, f'{code}.watch', exc, on_error)
        if include_traders:
            try:
                trades = client.get_market_client_types(market=code, policy=policy)
                components.append({'market': code, 'part': 'traders', 'metadata': _meta(trades)})
                row['realbuy'] = _safe_sum(trades, 'individual_buy_value')
                row['realsell'] = _safe_sum(trades, 'individual_sell_value')
                if pd.notna(row['realbuy']) and pd.notna(row['realsell']):
                    row['netreal'] = row['realbuy'] - row['realsell']
                else:
                    row['netreal'] = pd.NA
            except Exception as exc:
                _error(errors, f'{code}.traders', exc, on_error)
        records.append(row)
    out = pd.DataFrame.from_records(records)
    for field in ('date','datadate','datatimestamp','fetchedat','sourcetimestamp'):
        if field in out:
            out[field] = pd.to_datetime(out[field], errors='coerce')
    out.attrs['pydara'] = {'schema_id': 'markets.summary', 'coverage_status': 'observed_components_only',
        'markets': selected, 'components': components, 'errors': errors,
        'failed_items': len(errors), 'computed': ['positive','negative','unchanged','buyqueues','sellqueues','netreal'],
        'components_are_simultaneous': False,
        'queue_rule': 'price at exchange limit + positive same-side volume + explicitly zero opposite-side volume; unknown otherwise',
        'realbuy_definition': 'sum of reported individual_buy_value; completeness not independently verified',
        'synthetic': any(c['metadata'].get('synthetic') for c in components),
        'is_stale': any(c['metadata'].get('is_stale') for c in components)}
    return out


def _book_from_watch(watch):
    """Extract up to five level quotes already attached to market-watch rows."""
    rows = []
    for _, r in watch.iterrows():
        for depth in range(1, 6):
            cols = [f'{base}_{depth}' for base in ('bid_price','ask_price','bid_volume','ask_volume')]
            if not all(c in r.index for c in cols):
                continue
            if all(pd.isna(r[c]) for c in cols):
                continue
            rows.append({'ins_code': r['ins_code'], 'depth': depth, **{k: r[f'{k}_{depth}'] for k in ('bid_price','ask_price','bid_volume','ask_volume')}})
    return pd.DataFrame.from_records(rows)


def quote_watch(client, *, markets=None, include_queues=True, policy=None, on_error='collect'):
    """Bulk current-session prices for selected markets; no per-asset HTTP loop."""
    if on_error not in ('collect', 'raise'):
        raise InvalidArgumentError('on_error must be collect or raise.')
    selection = markets_filter(markets, allow_base=True)
    if selection is None:
        raw = client.get_market_watch(include_order_book=include_queues, policy=policy)
    else:
        parts, errors = [], []
        for code in selection:
            try:
                parts.append(client.get_market_watch(market=code,
                    include_order_book=include_queues, policy=policy))
            except Exception as exc:
                _error(errors, code, exc, on_error)
        if not parts:
            raise UnsupportedCapabilityError('All selected market-watch requests failed.')
        raw = pd.concat(parts, ignore_index=True)
        raw.attrs['pydara'] = {
            'components': [_meta(f) for f in parts],
            'errors': errors, 'coverage_status': 'observed_watch_only',
            'synthetic': any(_meta(f).get('synthetic') for f in parts),
            'is_stale': any(_meta(f).get('is_stale') for f in parts),
        }
    if 'ins_code' in raw:
        raw = raw.drop_duplicates('ins_code', keep='first').copy()
    if include_queues:
        raw = _queue_flags(raw, _book_from_watch(raw))
    else:
        raw = raw.copy()
        raw['buyqueue'] = pd.array([pd.NA] * len(raw), dtype='Float64')
        raw['sellqueue'] = pd.array([pd.NA] * len(raw), dtype='Float64')
    out = _oneword(raw)
    out.attrs.setdefault('pydara', {})['coverage_note'] = 'Observed market watch, not all historically listed instruments.'
    return returns(out)


def enrich_quotes(quoted, watch, *, include_queues):
    """Join optional market-watch book metrics, with non-atomicity documented."""
    if not include_queues or 'inscode' not in quoted or 'inscode' not in watch:
        return returns(quoted)
    new = quoted.copy()
    frame = watch.drop_duplicates('inscode').set_index('inscode')
    for c in ('buyqueue', 'sellqueue', 'queuereported', 'volume', 'turnover', 'tradecount'):
        if c in frame:
            new[c] = new['inscode'].map(frame[c])
    for c in ('buyqueue', 'sellqueue'):
        if c not in new:
            new[c] = pd.array([pd.NA] * len(new), dtype='Float64')
    new.attrs = deepcopy(quoted.attrs)
    new.attrs.setdefault('pydara', {})['components'] = [_meta(quoted), _meta(watch)]
    new.attrs['pydara']['components_are_simultaneous'] = False
    return returns(new)


def _source_selectors(assets=None, ins_code=None, on_multiple='all', on_conflict='error'):
    """Validate and normalize scalar or bulk asset references before I/O."""
    lookup_policies(on_multiple, on_conflict, has_ins_code=ins_code is not None)
    if assets is None and ins_code is None:
        return None
    return selectors(assets, ins_code=ins_code, on_multiple=on_multiple, on_conflict=on_conflict)


def books(client, *, assets=None, ins_code=None, day=None, start=None, end=None,
          calendar='auto', include_jdate=False, depth=5, side='all', max_days=31,
          on_multiple='all', on_conflict='error', on_error='collect', markets=None,
          policy=None):
    """Return long-form reported best-limit levels (one row per side and depth).

    Args:
        client: Existing data client.
        assets (DataFrame | str | list[str] | None): Selection from ``assets()``.
        ins_code (str | Sequence[str] | None): One or many explicit identifiers.
        day, start, end (DateLike | None): Single day or inclusive historical window.
        calendar (Literal['auto','jalali','gregorian']): Date string calendar.
        include_jdate (bool): Add Jalali dates if requested.
        depth (int): Source has up to five book levels. Allowed 1..5.
        side (Literal['all','buy','sell']): Select one or both order sides.
        max_days (int): Historical request budget (1..366).
        on_multiple (Literal['all','first','error']): Resolve ambiguous symbols.
        on_conflict (Literal['error','ins_code']): Identity conflict policy.
        on_error (Literal['collect','raise']): Error collection or fail-fast.
        markets (str | Sequence | DataFrame | None): Current bulk book market filter.
        policy (FetchPolicy | str | None): Network/cache policy.

    Returns:
        DataFrame: ``inscode``, ``symbol``, ``date``, ``side``, ``level``,
        ``price``, ``volume``, ``count``, source timestamps and provenance fields.
        A side is absent when its source value is unknown; no missing rows invented.
    """
    if on_error not in ('collect','raise'):
        raise InvalidArgumentError('on_error must be collect or raise.')
    if isinstance(depth,bool) or not isinstance(depth,int) or not 1<=depth<=5:
        raise InvalidArgumentError('depth must be 1..5 (source maximum).')
    if side not in ('all','buy','sell'):
        raise InvalidArgumentError('side must be all, buy or sell.')
    if day is not None and (start is not None or end is not None):
        raise InvalidArgumentError('Use day or start/end, not both.')
    from .friendly import friendly_range
    lo, hi, _ = friendly_range(start, end, calendar=calendar)
    parsed_day, _, _ = friendly_range(day, None, calendar=calendar)
    if lo is not None and hi is None:
        hi = lo
    if lo is None and hi is not None:
        raise InvalidArgumentError('start must be supplied with end.')
    historical = parsed_day is not None or lo is not None
    chosen = _source_selectors(assets, ins_code, on_multiple, on_conflict)
    if historical and chosen is None:
        raise InvalidArgumentError('Historical orders require explicit assets or ins_code.')
    if chosen is not None and markets is not None:
        raise InvalidArgumentError('Specify markets only for a bulk current order-book query.')
    errors, parts, reports = [], [], []
    if chosen is None:
        codes = markets_filter(markets,allow_base=True)
        if codes is None:
            codes = [None]
        for code in codes:
            try:
                f = client.get_market_order_book(market=code, policy=policy)
                parts.append(f)
                reports.append({'selector': code, 'metadata': _meta(f)})
            except Exception as exc:
                _error(errors, code or 'all', exc, on_error)
    else:
        seen = set()
        for selector in chosen:
            try:
                # A symbol may resolve to multiple exchange instruments. The
                # same cardinality policy used by assets() applies here.
                if 'ins_code' in selector:
                    selected_codes = [InstrumentRef.by_ins_code(str(selector['ins_code'])).value]
                else:
                    matched = client.instrument(symbol=selector['symbol'],
                        on_multiple=on_multiple, on_conflict=on_conflict, policy=policy)
                    selected_codes = [str(x) for x in matched['ins_code']]
                for code in selected_codes:
                    if code in seen:
                        continue
                    seen.add(code)
                    identity = InstrumentRef.by_ins_code(code)
                    try:
                        if historical:
                            low = parsed_day or lo
                            high = parsed_day or hi
                            f = client.get_order_book_history(identity, start=low, end=high,
                                calendar='gregorian', include_jdate=include_jdate,
                                max_days=max_days, policy=policy)
                        else:
                            f = client.get_order_book(identity, policy=policy)
                        parts.append(f)
                        reports.append({'selector': str(selector), 'inscode': code, 'metadata': _meta(f)})
                    except Exception as exc:
                        _error(errors, code, exc, on_error)
            except Exception as exc:
                _error(errors, str(selector), exc, on_error)
    data = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    columns = ('ins_code','symbol','date','depth','bid_price','ask_price','bid_volume','ask_volume',
               'bid_order_count','ask_order_count','source_timestamp','fetched_at','jdate')
    output = []
    for _, row in data.iterrows():
        level = row.get('depth', pd.NA)
        if pd.isna(level) or not 1 <= int(level) <= depth:
            continue
        for kind, prefix in [('buy','bid'),('sell','ask')]:
            if side != 'all' and side != kind: continue
            price = row.get(prefix+'_price',pd.NA)
            vol = row.get(prefix+'_volume',pd.NA)
            count = row.get(prefix+'_order_count',pd.NA)
            if pd.isna(price) and pd.isna(vol) and pd.isna(count):
                continue
            record = {k: row.get(k, pd.NA) for k in data.columns if k not in columns and k not in ('bid_price','ask_price','bid_volume','ask_volume','bid_order_count','ask_order_count')}
            record.update(ins_code=row.get('ins_code', pd.NA),symbol=row.get('symbol', pd.NA),
                date=row.get('date',pd.NaT),level=int(level),side=kind,price=price,volume=vol,count=count,
                source_timestamp=row.get('source_timestamp',pd.NaT),fetched_at=row.get('fetched_at',pd.NaT))
            if 'jdate' in row: record['jdate'] = row['jdate']
            output.append(record)
    expected = ['inscode','symbol','date','side','level','price','volume','count','sourcetimestamp','fetchedat']
    out = _oneword(pd.DataFrame.from_records(output))
    for col in expected:
        if col not in out:
            out[col] = pd.Series(dtype='object')
    out = out[[*expected, *[c for c in out if c not in expected]]]
    out.attrs['pydara'] = {'schema_id':'orders.public','requested_items':len(reports)+len(errors),
        'failed_items':len(errors),'errors':errors,'requests':reports,
        'coverage_status':'reported_best_levels_only','max_depth':5,
        'historical':historical,'historical_updates_not_complete_snapshots':historical,
        'synthetic':any(r['metadata'].get('synthetic') for r in reports),
        'is_stale':any(r['metadata'].get('is_stale') for r in reports)}
    return out
