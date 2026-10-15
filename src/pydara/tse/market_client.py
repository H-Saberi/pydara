"""Native sync/async public methods backed by shared, pure operation plans."""
from __future__ import annotations
from collections.abc import Sequence, Iterator, AsyncIterator
from datetime import datetime
import asyncio
import time
import pandas as pd
import numpy as np
from pydara.tse._core.models import Market, InstrumentLike, InstrumentRef
from pydara.tse._core.exceptions import (PyDaraError, BatchDataError, InvalidArgumentError)
from .config import FetchPolicy, coerce_policy
from .dates import DateLike, Calendar, parse_range, parse_date
from .history_models import BatchFrames
from .market import (
    market_watch_plan, market_order_book_plan, market_overview_plan,
    market_map_plan, sectors_plan, sector_instruments_plan, key_statistics_plan,
    participant_plan, market_clients_plan, indices_plan, search_indices_plan,
    resolve_index_plan, index_data_plan, index_impact_plan, poll_options,
)
from .providers.market import flag, market_value, flow_of
from .market_schemas import finish_market, empty_market_frame, combine_frames
from .services import validate_batch
from .market_batch import TableBatchBuilder, validate_index_batch

class MarketClientMixin:
    """Provide Market client operations to a client.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    def get_market_watch(self, *, market: Market | str | None = None, include_order_book: bool = False, include_client_types: bool = False, show_traded: bool = False, backend: str = "auto", policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Return the current public market watch as a typed DataFrame. auto falls back to the reviewed legacy text route only when JSON returns a valid empty list. Optional books and client types retain independent provenance; rows are not an atomic snapshot. Empty is not proof of a closed market."""
        frame = self._run(market_watch_plan(market=market, include_order_book=include_order_book, include_client_types=include_client_types, show_traded=show_traded, backend=backend, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_market_order_book(self, *, market: Market | str | None = None, backend: str = "auto", policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Return reported best-limit levels for the current watch. This is not the full exchange order book or historical depth. Missing levels are not filled. Source timestamps not reported by the feed remain missing."""
        frame = self._run(market_order_book_plan(market=market, backend=backend, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_market_overview(self, *, market: Market | str = Market.TSE, policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Return one row of reported market totals and index values. TSE or IFB only. Activity time and overall data time remain separate."""
        frame = self._run(market_overview_plan(market=market, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_market_map(self, *, sector_code: str | None = None, limit: int = 9999, policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Return the reported market-map data only; no drawing or computed ranking. The source size parameter can truncate output; coverage is not certified."""
        frame = self._run(market_map_plan(sector_code=sector_code, limit=limit, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_sectors(self, *, policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Return sector codes/names with the four source counters preserved as source_c1..source_c4. Their undocumented bucket meanings are not guessed."""
        frame = self._run(sectors_plan(namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_sector_instruments(self, sector_code: str, *, policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Return current related-company quotes for an exact sector code. This is industry grouping, not evidence of corporate ownership."""
        frame = self._run(sector_instruments_plan(sector_code, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_key_statistics(self, *, ins_code: str | int | None = None, policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Return all reported parameter-code/value pairs (potentially a large response). ins_code filtering is local after the bulk response. reported_value stays text: undocumented units and metrics are not guessed."""
        frame = self._run(key_statistics_plan(ins_code=ins_code, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def _get_client_types(self, instrument: InstrumentLike, *, day: DateLike | None = None, calendar: Calendar = "gregorian", include_jdate: bool = False, policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Return latest or one specified day of natural/legal counts, volumes and reported values as a DataFrame. Missing values and dates are not inferred. DDD source fields are kept separate from individual/institutional."""
        frame = self._run(participant_plan(instrument, day=day, calendar=calendar, include_jdate=include_jdate, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def _get_client_type_history(self, instrument: InstrumentLike, *, start: DateLike | None = None, end: DateLike | None = None, calendar: Calendar = "gregorian", include_jdate: bool = False, policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Return full available client-type history, then filter locally to inclusive dates, sorted ascending. Current identity does not certify historical identity or point-in-time availability."""
        frame = self._run(participant_plan(instrument, history=True, start=start, end=end, calendar=calendar, include_jdate=include_jdate, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_market_client_types(self, *, market: Market | str | None = None, backend: str = "auto", policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Return the bulk client-type response. With market selected, intersect with current watch identities (one extra component); without a filter, keep every returned ins_code. No date/value/market is guessed when absent."""
        frame = self._run(market_clients_plan(market=market, backend=backend, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_indices(self, *, market: Market | str | None = Market.TSE, policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Return index codes, names and latest reported values. market=None explicitly requests TSE and IFB catalogs separately. Unit is points, never currency."""
        frame = self._run(indices_plan(market=market, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def search_indices(self, query: str, *, market: Market | str | None = Market.TSE, limit: int | None = None, policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Search normalized current index names; never choose the first match implicitly. A local limit does not change server pagination."""
        frame = self._run(search_indices_plan(query, market=market, limit=limit, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_index(self, index: str | int | InstrumentRef, *, market: Market | str | None = Market.TSE, policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Resolve exactly one index from the current catalog by exact name or code, returning a one-row DataFrame. Ambiguous names raise. Use get_indices(market=None) to inspect available codes."""
        frame = self._run(resolve_index_plan(index, market=market, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_index_history(self, index: str | int | InstrumentRef, *, market: Market | str | None = Market.TSE, start: DateLike | None = None, end: DateLike | None = None, calendar: Calendar = "gregorian", include_jdate: bool = False, policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Return daily index close/high/low in points, ascending with inclusive date filtering. Open and volume are not invented. A full response is fetched before local filtering."""
        frame = self._run(index_data_plan(index, kind="history", market=market, start=start, end=end, calendar=calendar, include_jdate=include_jdate, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_index_intraday(self, index: str | int | InstrumentRef, *, market: Market | str | None = Market.TSE, day: DateLike | None = None, calendar: Calendar = "gregorian", include_jdate: bool = False, policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Return index observations for the latest session available from the public endpoint. day=None only; selecting a historical session is not supported and raises before HTTP. Equal-time points preserve source order."""
        frame = self._run(index_data_plan(index, kind="intraday", market=market, day=day, calendar=calendar, include_jdate=include_jdate, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_index_members(self, index: str | int | InstrumentRef, *, market: Market | str | None = Market.TSE, as_of: DateLike | None = None, policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Return current constituent quotes, not historical membership or index weights. as_of is unsupported and raises before HTTP. Quote dates are not membership effective dates."""
        frame = self._run(index_data_plan(index, kind="members", market=market, as_of=as_of, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_index_impact(self, *, market: Market | str = Market.TSE, limit: int = 7, policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """EXPERIMENTAL: fetch the reported total-market index-effect records and preserve every source field in source_fields. impact_points/unit remain unknown until the live economic mapping is verified. This does not compute index impact or address arbitrary indices."""
        frame = self._run(index_impact_plan(market=market, limit=limit, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def watch_market(self, *, interval: float = 10.0, max_updates: int | None = 10,
                     market: Market | str | None = None, include_order_book: bool = False,
                     include_client_types: bool = False, show_traded: bool = False,
                     backend: str = "auto") -> Iterator[pd.DataFrame]:
        """Yield freshly fetched full snapshots with bounded polling, not WebSocket deltas.

        A one-second local lower bound is not an exchange rate-limit promise.
        max_updates=None opts into indefinite polling. Cancel/close the iterator
        or interrupt execution to stop; exceptions propagate, no infinite retry.
        """
        interval, maximum = poll_options(interval, max_updates)
        if self.config.mode == "offline":
            raise InvalidArgumentError("Live polling is disabled in offline mode; use get_market_watch with an explicit offline policy.")
        counter = 0
        while maximum is None or counter < maximum:
            self._core.check()
            frame = self.get_market_watch(
                market=market, include_order_book=include_order_book,
                include_client_types=include_client_types, show_traded=show_traded,
                backend=backend, policy=FetchPolicy.fresh())
            frame.attrs["pydara"]["poll_index"] = counter
            yield frame
            counter += 1
            if maximum is None or counter < maximum:
                time.sleep(interval)

    def _get_client_types_many(self, instruments: Sequence[InstrumentLike] | pd.Series | pd.Index | np.ndarray, *, day: DateLike | None = None, calendar: Calendar = "gregorian", include_jdate: bool = False, on_error: str = "raise", policy: FetchPolicy | str | None = None) -> BatchFrames:
        """Sequential ordered batch with data/errors/requests tables. Input duplicates
        and empty successes have separate request rows. on_error=raise includes
        partial_result; collect reports per-item errors without claiming completeness.
        """
        self._core.check()
        policy = coerce_policy(policy)
        items = validate_batch(instruments, on_error)
        parse_date(day, calendar=calendar, name="day")
        flag(include_jdate, "include_jdate")
        builder = TableBatchBuilder('client_types', len(items), self.config.numeric, include_jdate)
        for position, item in enumerate(items):
            try:
                frame = self._get_client_types(item, day=day, calendar=calendar, include_jdate=include_jdate, policy=policy)
                builder.success(position, item, frame)
            except PyDaraError as exc:
                builder.failure(position, item, exc)
                if on_error == "raise":
                    raise BatchDataError("A batch item failed; inspect partial_result.", partial_result=builder.result()) from exc
        return builder.result()

    def _get_client_type_history_many(self, instruments: Sequence[InstrumentLike] | pd.Series | pd.Index | np.ndarray, *, start: DateLike | None = None, end: DateLike | None = None, calendar: Calendar = "gregorian", include_jdate: bool = False, on_error: str = "raise", policy: FetchPolicy | str | None = None) -> BatchFrames:
        """Sequential ordered batch with data/errors/requests tables. Input duplicates
        and empty successes have separate request rows. on_error=raise includes
        partial_result; collect reports per-item errors without claiming completeness.
        """
        self._core.check()
        policy = coerce_policy(policy)
        items = validate_batch(instruments, on_error)
        parse_range(start, end, calendar=calendar)
        flag(include_jdate, "include_jdate")
        builder = TableBatchBuilder('client_types', len(items), self.config.numeric, include_jdate)
        for position, item in enumerate(items):
            try:
                frame = self._get_client_type_history(item, start=start, end=end, calendar=calendar, include_jdate=include_jdate, policy=policy)
                builder.success(position, item, frame)
            except PyDaraError as exc:
                builder.failure(position, item, exc)
                if on_error == "raise":
                    raise BatchDataError("A batch item failed; inspect partial_result.", partial_result=builder.result()) from exc
        return builder.result()

    def get_index_history_many(self, indices: Sequence[str | int | InstrumentRef] | pd.Series | pd.Index | np.ndarray, *, market: Market | str | None = Market.TSE, start: DateLike | None = None, end: DateLike | None = None, calendar: Calendar = "gregorian", include_jdate: bool = False, on_error: str = "raise", policy: FetchPolicy | str | None = None) -> BatchFrames:
        """Sequential ordered batch with data/errors/requests tables. Input duplicates
        and empty successes have separate request rows. on_error=raise includes
        partial_result; collect reports per-item errors without claiming completeness.
        """
        self._core.check()
        policy = coerce_policy(policy)
        market = market_value(market)
        if market is not None: flow_of(market)
        items = validate_index_batch(indices, on_error)
        parse_range(start, end, calendar=calendar)
        flag(include_jdate, "include_jdate")
        builder = TableBatchBuilder('index_history', len(items), self.config.numeric, include_jdate)
        for position, item in enumerate(items):
            try:
                frame = self.get_index_history(item, market=market, start=start, end=end, calendar=calendar, include_jdate=include_jdate, policy=policy)
                builder.success(position, item, frame)
            except PyDaraError as exc:
                builder.failure(position, item, exc)
                if on_error == "raise":
                    raise BatchDataError("A batch item failed; inspect partial_result.", partial_result=builder.result()) from exc
        return builder.result()

class AsyncMarketClientMixin:
    """Provide asynchronous Market client operations to a client.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    async def get_market_watch(self, *, market: Market | str | None = None, include_order_book: bool = False, include_client_types: bool = False, show_traded: bool = False, backend: str = "auto", policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Return the current public market watch as a typed DataFrame. auto falls back to the reviewed legacy text route only when JSON returns a valid empty list. Optional books and client types retain independent provenance; rows are not an atomic snapshot. Empty is not proof of a closed market."""
        frame = await self._run(market_watch_plan(market=market, include_order_book=include_order_book, include_client_types=include_client_types, show_traded=show_traded, backend=backend, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_market_order_book(self, *, market: Market | str | None = None, backend: str = "auto", policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Return reported best-limit levels for the current watch. This is not the full exchange order book or historical depth. Missing levels are not filled. Source timestamps not reported by the feed remain missing."""
        frame = await self._run(market_order_book_plan(market=market, backend=backend, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_market_overview(self, *, market: Market | str = Market.TSE, policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Return one row of reported market totals and index values. TSE or IFB only. Activity time and overall data time remain separate."""
        frame = await self._run(market_overview_plan(market=market, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_market_map(self, *, sector_code: str | None = None, limit: int = 9999, policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Return the reported market-map data only; no drawing or computed ranking. The source size parameter can truncate output; coverage is not certified."""
        frame = await self._run(market_map_plan(sector_code=sector_code, limit=limit, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_sectors(self, *, policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Return sector codes/names with the four source counters preserved as source_c1..source_c4. Their undocumented bucket meanings are not guessed."""
        frame = await self._run(sectors_plan(namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_sector_instruments(self, sector_code: str, *, policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Return current related-company quotes for an exact sector code. This is industry grouping, not evidence of corporate ownership."""
        frame = await self._run(sector_instruments_plan(sector_code, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_key_statistics(self, *, ins_code: str | int | None = None, policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Return all reported parameter-code/value pairs (potentially a large response). ins_code filtering is local after the bulk response. reported_value stays text: undocumented units and metrics are not guessed."""
        frame = await self._run(key_statistics_plan(ins_code=ins_code, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def _get_client_types(self, instrument: InstrumentLike, *, day: DateLike | None = None, calendar: Calendar = "gregorian", include_jdate: bool = False, policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Return latest or one specified day of natural/legal counts, volumes and reported values as a DataFrame. Missing values and dates are not inferred. DDD source fields are kept separate from individual/institutional."""
        frame = await self._run(participant_plan(instrument, day=day, calendar=calendar, include_jdate=include_jdate, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def _get_client_type_history(self, instrument: InstrumentLike, *, start: DateLike | None = None, end: DateLike | None = None, calendar: Calendar = "gregorian", include_jdate: bool = False, policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Return full available client-type history, then filter locally to inclusive dates, sorted ascending. Current identity does not certify historical identity or point-in-time availability."""
        frame = await self._run(participant_plan(instrument, history=True, start=start, end=end, calendar=calendar, include_jdate=include_jdate, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_market_client_types(self, *, market: Market | str | None = None, backend: str = "auto", policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Return the bulk client-type response. With market selected, intersect with current watch identities (one extra component); without a filter, keep every returned ins_code. No date/value/market is guessed when absent."""
        frame = await self._run(market_clients_plan(market=market, backend=backend, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_indices(self, *, market: Market | str | None = Market.TSE, policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Return index codes, names and latest reported values. market=None explicitly requests TSE and IFB catalogs separately. Unit is points, never currency."""
        frame = await self._run(indices_plan(market=market, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def search_indices(self, query: str, *, market: Market | str | None = Market.TSE, limit: int | None = None, policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Search normalized current index names; never choose the first match implicitly. A local limit does not change server pagination."""
        frame = await self._run(search_indices_plan(query, market=market, limit=limit, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_index(self, index: str | int | InstrumentRef, *, market: Market | str | None = Market.TSE, policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Resolve exactly one index from the current catalog by exact name or code, returning a one-row DataFrame. Ambiguous names raise. Use get_indices(market=None) to inspect available codes."""
        frame = await self._run(resolve_index_plan(index, market=market, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_index_history(self, index: str | int | InstrumentRef, *, market: Market | str | None = Market.TSE, start: DateLike | None = None, end: DateLike | None = None, calendar: Calendar = "gregorian", include_jdate: bool = False, policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Return daily index close/high/low in points, ascending with inclusive date filtering. Open and volume are not invented. A full response is fetched before local filtering."""
        frame = await self._run(index_data_plan(index, kind="history", market=market, start=start, end=end, calendar=calendar, include_jdate=include_jdate, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_index_intraday(self, index: str | int | InstrumentRef, *, market: Market | str | None = Market.TSE, day: DateLike | None = None, calendar: Calendar = "gregorian", include_jdate: bool = False, policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Return index observations for the latest session available from the public endpoint. day=None only; selecting a historical session is not supported and raises before HTTP. Equal-time points preserve source order."""
        frame = await self._run(index_data_plan(index, kind="intraday", market=market, day=day, calendar=calendar, include_jdate=include_jdate, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_index_members(self, index: str | int | InstrumentRef, *, market: Market | str | None = Market.TSE, as_of: DateLike | None = None, policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """Return current constituent quotes, not historical membership or index weights. as_of is unsupported and raises before HTTP. Quote dates are not membership effective dates."""
        frame = await self._run(index_data_plan(index, kind="members", market=market, as_of=as_of, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_index_impact(self, *, market: Market | str = Market.TSE, limit: int = 7, policy: FetchPolicy | str | None = None) -> pd.DataFrame:
        """EXPERIMENTAL: fetch the reported total-market index-effect records and preserve every source field in source_fields. impact_points/unit remain unknown until the live economic mapping is verified. This does not compute index impact or address arbitrary indices."""
        frame = await self._run(index_impact_plan(market=market, limit=limit, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def watch_market(self, *, interval: float = 10.0, max_updates: int | None = 10,
                     market: Market | str | None = None, include_order_book: bool = False,
                     include_client_types: bool = False, show_traded: bool = False,
                     backend: str = "auto") -> AsyncIterator[pd.DataFrame]:
        """Yield freshly fetched full snapshots with bounded polling, not WebSocket deltas.

        A one-second local lower bound is not an exchange rate-limit promise.
        max_updates=None opts into indefinite polling. Cancel/close the iterator
        or interrupt execution to stop; exceptions propagate, no infinite retry.
        """
        interval, maximum = poll_options(interval, max_updates)
        if self.config.mode == "offline":
            raise InvalidArgumentError("Live polling is disabled in offline mode; use get_market_watch with an explicit offline policy.")
        counter = 0
        while maximum is None or counter < maximum:
            self._core.check()
            frame = await self.get_market_watch(
                market=market, include_order_book=include_order_book,
                include_client_types=include_client_types, show_traded=show_traded,
                backend=backend, policy=FetchPolicy.fresh())
            frame.attrs["pydara"]["poll_index"] = counter
            yield frame
            counter += 1
            if maximum is None or counter < maximum:
                await asyncio.sleep(interval)

    async def _get_client_types_many(self, instruments: Sequence[InstrumentLike] | pd.Series | pd.Index | np.ndarray, *, day: DateLike | None = None, calendar: Calendar = "gregorian", include_jdate: bool = False, on_error: str = "raise", policy: FetchPolicy | str | None = None) -> BatchFrames:
        """Sequential ordered batch with data/errors/requests tables. Input duplicates
        and empty successes have separate request rows. on_error=raise includes
        partial_result; collect reports per-item errors without claiming completeness.
        """
        self._core.check()
        policy = coerce_policy(policy)
        items = validate_batch(instruments, on_error)
        parse_date(day, calendar=calendar, name="day")
        flag(include_jdate, "include_jdate")
        builder = TableBatchBuilder('client_types', len(items), self.config.numeric, include_jdate)
        for position, item in enumerate(items):
            try:
                frame = await self._get_client_types(item, day=day, calendar=calendar, include_jdate=include_jdate, policy=policy)
                builder.success(position, item, frame)
            except PyDaraError as exc:
                builder.failure(position, item, exc)
                if on_error == "raise":
                    raise BatchDataError("A batch item failed; inspect partial_result.", partial_result=builder.result()) from exc
        return builder.result()

    async def _get_client_type_history_many(self, instruments: Sequence[InstrumentLike] | pd.Series | pd.Index | np.ndarray, *, start: DateLike | None = None, end: DateLike | None = None, calendar: Calendar = "gregorian", include_jdate: bool = False, on_error: str = "raise", policy: FetchPolicy | str | None = None) -> BatchFrames:
        """Sequential ordered batch with data/errors/requests tables. Input duplicates
        and empty successes have separate request rows. on_error=raise includes
        partial_result; collect reports per-item errors without claiming completeness.
        """
        self._core.check()
        policy = coerce_policy(policy)
        items = validate_batch(instruments, on_error)
        parse_range(start, end, calendar=calendar)
        flag(include_jdate, "include_jdate")
        builder = TableBatchBuilder('client_types', len(items), self.config.numeric, include_jdate)
        for position, item in enumerate(items):
            try:
                frame = await self._get_client_type_history(item, start=start, end=end, calendar=calendar, include_jdate=include_jdate, policy=policy)
                builder.success(position, item, frame)
            except PyDaraError as exc:
                builder.failure(position, item, exc)
                if on_error == "raise":
                    raise BatchDataError("A batch item failed; inspect partial_result.", partial_result=builder.result()) from exc
        return builder.result()

    async def get_index_history_many(self, indices: Sequence[str | int | InstrumentRef] | pd.Series | pd.Index | np.ndarray, *, market: Market | str | None = Market.TSE, start: DateLike | None = None, end: DateLike | None = None, calendar: Calendar = "gregorian", include_jdate: bool = False, on_error: str = "raise", policy: FetchPolicy | str | None = None) -> BatchFrames:
        """Sequential ordered batch with data/errors/requests tables. Input duplicates
        and empty successes have separate request rows. on_error=raise includes
        partial_result; collect reports per-item errors without claiming completeness.
        """
        self._core.check()
        policy = coerce_policy(policy)
        market = market_value(market)
        if market is not None: flow_of(market)
        items = validate_index_batch(indices, on_error)
        parse_range(start, end, calendar=calendar)
        flag(include_jdate, "include_jdate")
        builder = TableBatchBuilder('index_history', len(items), self.config.numeric, include_jdate)
        for position, item in enumerate(items):
            try:
                frame = await self.get_index_history(item, market=market, start=start, end=end, calendar=calendar, include_jdate=include_jdate, policy=policy)
                builder.success(position, item, frame)
            except PyDaraError as exc:
                builder.failure(position, item, exc)
                if on_error == "raise":
                    raise BatchDataError("A batch item failed; inspect partial_result.", partial_result=builder.result()) from exc
        return builder.result()

