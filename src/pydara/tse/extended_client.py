"""Native interfaces for expanded data families. Generated signatures, shared plans."""
from __future__ import annotations
import pandas as pd
from pydara.tse._core.models import InstrumentLike, Market
from .config import FetchPolicy
from .dates import DateLike, Calendar
from .history_models import BatchFrames
from .extended import (instrument_table_plan, intraday_plan, table_plan, funds_plan,
                       fund_plan, options_plan, instruments_plan, futures_plan)
from .market_schemas import finish_market

class ExtendedClientMixin:
    """Provide extended  client operations to a client.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    def get_adjustments(self, instrument: InstrumentLike, *, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Reported price-adjustment events and price ratios. Reasons and complete corporate-action coverage are unknown; this is not a total-return algorithm.'
        frame = self._run(instrument_table_plan(instrument, name='extra.adjustments', start=start, end=end, calendar=calendar, include_jdate=include_jdate, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_share_capital_history(self, instrument: InstrumentLike, *, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Reported old/new share counts, not legal capital-increase classifications. All observed rows are retained.'
        frame = self._run(instrument_table_plan(instrument, name='extra.shares', start=start, end=end, calendar=calendar, include_jdate=include_jdate, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_dividends(self, instrument: InstrumentLike, *, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Dividend history from the legacy text route. Payment/ex dates are not inferred; failed or HTML responses raise.'
        frame = self._run(instrument_table_plan(instrument, name='extra.dividends', start=start, end=end, calendar=calendar, include_jdate=include_jdate, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_adjusted_history(self, instrument: InstrumentLike, *, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Source-adjusted chart history, separate from raw history. Source method tsetmc_chart_a1; anchor is the last returned date. No total-return or point-in-time guarantee. Missing turnover/count/reference price stay missing.'
        frame = self._run(instrument_table_plan(instrument, name='extra.adjusted', start=start, end=end, calendar=calendar, include_jdate=include_jdate, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_shareholders(self, instrument: InstrumentLike, *, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Latest reported major shareholders. Empty does not prove that no major holders exist.'
        frame = self._run(instrument_table_plan(instrument, name='extra.shareholders', namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_shareholder_history(self, instrument: InstrumentLike, holder_id: str | int, *, days: int=90, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'History of one holder of one instrument; holder_id comes from get_shareholders, not the holding_ref. days is 1..3650; date filtering is local.'
        frame = self._run(instrument_table_plan(instrument, name='extra.shareholders.history', holder_id=holder_id, days=days, start=start, end=end, calendar=calendar, include_jdate=include_jdate, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_disclosures(self, instrument: InstrumentLike, *, limit: int=20, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Disclosure metadata linked by TSETMC. Does not download or parse financial-statement attachments. limit is 1..1000; dates filter the returned subset only.'
        frame = self._run(instrument_table_plan(instrument, name='extra.disclosures', limit=limit, start=start, end=end, calendar=calendar, include_jdate=include_jdate, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_messages(self, instrument: InstrumentLike, *, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Reported instrument supervisor messages, with source timestamp and original text.'
        frame = self._run(instrument_table_plan(instrument, name='extra.messages', start=start, end=end, calendar=calendar, include_jdate=include_jdate, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_trades(self, instrument: InstrumentLike, *, day: DateLike | None=None, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, max_days: int=31, cancellation: str='as_reported', policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Reported executions, current or per explicit calendar day. Same-second trades are not deduplicated. Cancellation remains unknown; only as_reported is supported. Max 31 days by default, configurable up to 366.'
        frame = self._run(intraday_plan(instrument, kind='trades', day=day, start=start, end=end, calendar=calendar, include_jdate=include_jdate, max_days=max_days, cancellation=cancellation, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_order_book(self, instrument: InstrumentLike, *, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Current reported best limits (up to five depths), not a full exchange order book. Missing source timestamps stay missing.'
        frame = self._run(intraday_plan(instrument, kind='book', namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_order_book_history(self, instrument: InstrumentLike, *, start: DateLike, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, max_days: int=31, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Historical best-limit updates. Sequence/reference and source position are preserved. No fill-forward or fictional complete snapshots; empty days do not prove holidays.'
        frame = self._run(intraday_plan(instrument, kind='book', start=start, end=end, calendar=calendar, include_jdate=include_jdate, max_days=max_days, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_instrument_states(self, instrument: InstrumentLike, *, day: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Reported state/price-limit records for one day. No day means the last trading date reported by the quote, not today. Empty is not interpreted as open/unrestricted.'
        frame = self._run(intraday_plan(instrument, kind='states', day=day, calendar=calendar, include_jdate=include_jdate, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_thresholds(self, instrument: InstrumentLike, *, day: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Reported state/price-limit records for one day. No day means the last trading date reported by the quote, not today. Empty is not interpreted as open/unrestricted.'
        frame = self._run(intraday_plan(instrument, kind='thresholds', day=day, calendar=calendar, include_jdate=include_jdate, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_boards(self, *, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Board codes from the reviewed reference HTML table. A replaced page raises rather than returning a false empty registry.'
        frame = self._run(table_plan('extra.boards', namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_instruments(self, *, market: Market | str | None=None, include_inactive: bool=False, changed_since: DateLike | None=None, backend: str='auto', policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Current observed watch instrument list only. include_inactive=True and changed_since require a historical registry and raise; suspended instruments may still be in the current watch.'
        frame = self._run(instruments_plan(market=market, include_inactive=include_inactive, changed_since=changed_since, backend=backend, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_funds(self, category: str | None='stock', *, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Registered funds by category name/code; None explicitly fetches the ten reviewed categories. registration_no is not an ins_code.'
        frame = self._run(funds_plan(category, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_fund(self, registration_no: str | int, *, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Fund detail as a one-row frame with raw fields retained. Use the registration_no from get_funds.'
        frame = self._run(fund_plan(registration_no, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_fund_nav_history(self, registration_no: str | int, *, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Reported NAV stats; unit/currency not supplied by source remain unknown, not assumed from stock prices.'
        frame = self._run(fund_plan(registration_no, history=True, start=start, end=end, calendar=calendar, include_jdate=include_jdate, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_options(self, underlying: InstrumentLike | None=None, *, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Public option-chain pairs expanded into one row per put/call contract. Underlying filter is optional and local. No option pricing or inferred Greeks.'
        frame = self._run(options_plan(underlying, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_futures(self, *, source: str='tse_exchange', policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Current futures snapshot from the separate public tse.ir exchange gateway (not TSETMC CDN). Source must be tse_exchange. Fields with unverified meanings remain in source_fields. No history or commodity-exchange completeness guarantee.'
        frame = self._run(futures_plan(source=source, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    def get_trades_many(self, instruments, *, start, end=None, calendar='gregorian', include_jdate=False, on_error='collect', policy=None) -> BatchFrames:
        """Get reported trades for ordered inputs, with explicit per-input failure reports."""
        return self.download(instruments,dataset='trades',start=start,end=end if end is not None else start,calendar=calendar,include_jdate=include_jdate,on_error=on_error,update=False,policy=policy)

    def get_order_book_updates(self, instrument, *, start, end=None, calendar='gregorian', include_jdate=False, max_days=31, policy=None) -> pd.DataFrame:
        """Alias emphasizing that history rows are updates, not reconstructed full books."""
        return self.get_order_book_history(instrument,start=start,end=end,calendar=calendar,include_jdate=include_jdate,max_days=max_days,policy=policy)

class AsyncExtendedClientMixin:
    """Provide asynchronous extended  client operations to a client.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    async def get_adjustments(self, instrument: InstrumentLike, *, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Reported price-adjustment events and price ratios. Reasons and complete corporate-action coverage are unknown; this is not a total-return algorithm.'
        frame = await self._run(instrument_table_plan(instrument, name='extra.adjustments', start=start, end=end, calendar=calendar, include_jdate=include_jdate, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_share_capital_history(self, instrument: InstrumentLike, *, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Reported old/new share counts, not legal capital-increase classifications. All observed rows are retained.'
        frame = await self._run(instrument_table_plan(instrument, name='extra.shares', start=start, end=end, calendar=calendar, include_jdate=include_jdate, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_dividends(self, instrument: InstrumentLike, *, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Dividend history from the legacy text route. Payment/ex dates are not inferred; failed or HTML responses raise.'
        frame = await self._run(instrument_table_plan(instrument, name='extra.dividends', start=start, end=end, calendar=calendar, include_jdate=include_jdate, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_adjusted_history(self, instrument: InstrumentLike, *, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Source-adjusted chart history, separate from raw history. Source method tsetmc_chart_a1; anchor is the last returned date. No total-return or point-in-time guarantee. Missing turnover/count/reference price stay missing.'
        frame = await self._run(instrument_table_plan(instrument, name='extra.adjusted', start=start, end=end, calendar=calendar, include_jdate=include_jdate, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_shareholders(self, instrument: InstrumentLike, *, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Latest reported major shareholders. Empty does not prove that no major holders exist.'
        frame = await self._run(instrument_table_plan(instrument, name='extra.shareholders', namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_shareholder_history(self, instrument: InstrumentLike, holder_id: str | int, *, days: int=90, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'History of one holder of one instrument; holder_id comes from get_shareholders, not the holding_ref. days is 1..3650; date filtering is local.'
        frame = await self._run(instrument_table_plan(instrument, name='extra.shareholders.history', holder_id=holder_id, days=days, start=start, end=end, calendar=calendar, include_jdate=include_jdate, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_disclosures(self, instrument: InstrumentLike, *, limit: int=20, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Disclosure metadata linked by TSETMC. Does not download or parse financial-statement attachments. limit is 1..1000; dates filter the returned subset only.'
        frame = await self._run(instrument_table_plan(instrument, name='extra.disclosures', limit=limit, start=start, end=end, calendar=calendar, include_jdate=include_jdate, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_messages(self, instrument: InstrumentLike, *, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Reported instrument supervisor messages, with source timestamp and original text.'
        frame = await self._run(instrument_table_plan(instrument, name='extra.messages', start=start, end=end, calendar=calendar, include_jdate=include_jdate, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_trades(self, instrument: InstrumentLike, *, day: DateLike | None=None, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, max_days: int=31, cancellation: str='as_reported', policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Reported executions, current or per explicit calendar day. Same-second trades are not deduplicated. Cancellation remains unknown; only as_reported is supported. Max 31 days by default, configurable up to 366.'
        frame = await self._run(intraday_plan(instrument, kind='trades', day=day, start=start, end=end, calendar=calendar, include_jdate=include_jdate, max_days=max_days, cancellation=cancellation, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_order_book(self, instrument: InstrumentLike, *, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Current reported best limits (up to five depths), not a full exchange order book. Missing source timestamps stay missing.'
        frame = await self._run(intraday_plan(instrument, kind='book', namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_order_book_history(self, instrument: InstrumentLike, *, start: DateLike, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, max_days: int=31, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Historical best-limit updates. Sequence/reference and source position are preserved. No fill-forward or fictional complete snapshots; empty days do not prove holidays.'
        frame = await self._run(intraday_plan(instrument, kind='book', start=start, end=end, calendar=calendar, include_jdate=include_jdate, max_days=max_days, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_instrument_states(self, instrument: InstrumentLike, *, day: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Reported state/price-limit records for one day. No day means the last trading date reported by the quote, not today. Empty is not interpreted as open/unrestricted.'
        frame = await self._run(intraday_plan(instrument, kind='states', day=day, calendar=calendar, include_jdate=include_jdate, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_thresholds(self, instrument: InstrumentLike, *, day: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Reported state/price-limit records for one day. No day means the last trading date reported by the quote, not today. Empty is not interpreted as open/unrestricted.'
        frame = await self._run(intraday_plan(instrument, kind='thresholds', day=day, calendar=calendar, include_jdate=include_jdate, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_boards(self, *, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Board codes from the reviewed reference HTML table. A replaced page raises rather than returning a false empty registry.'
        frame = await self._run(table_plan('extra.boards', namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_instruments(self, *, market: Market | str | None=None, include_inactive: bool=False, changed_since: DateLike | None=None, backend: str='auto', policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Current observed watch instrument list only. include_inactive=True and changed_since require a historical registry and raise; suspended instruments may still be in the current watch.'
        frame = await self._run(instruments_plan(market=market, include_inactive=include_inactive, changed_since=changed_since, backend=backend, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_funds(self, category: str | None='stock', *, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Registered funds by category name/code; None explicitly fetches the ten reviewed categories. registration_no is not an ins_code.'
        frame = await self._run(funds_plan(category, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_fund(self, registration_no: str | int, *, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Fund detail as a one-row frame with raw fields retained. Use the registration_no from get_funds.'
        frame = await self._run(fund_plan(registration_no, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_fund_nav_history(self, registration_no: str | int, *, start: DateLike | None=None, end: DateLike | None=None, calendar: Calendar='gregorian', include_jdate: bool=False, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Reported NAV stats; unit/currency not supplied by source remain unknown, not assumed from stock prices.'
        frame = await self._run(fund_plan(registration_no, history=True, start=start, end=end, calendar=calendar, include_jdate=include_jdate, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_options(self, underlying: InstrumentLike | None=None, *, policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Public option-chain pairs expanded into one row per put/call contract. Underlying filter is optional and local. No option pricing or inferred Greeks.'
        frame = await self._run(options_plan(underlying, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)

    async def get_futures(self, *, source: str='tse_exchange', policy: FetchPolicy | str | None=None) -> pd.DataFrame:
        'Current futures snapshot from the separate public tse.ir exchange gateway (not TSETMC CDN). Source must be tse_exchange. Fields with unverified meanings remain in source_fields. No history or commodity-exchange completeness guarantee.'
        frame = await self._run(futures_plan(source=source, namespace=self._core.namespace, numeric=self.config.numeric), policy=policy)
        return finish_market(frame, policy)


    async def get_trades_many(self, instruments, *, start, end=None, calendar='gregorian', include_jdate=False, on_error='collect', policy=None) -> BatchFrames:
        """Native async group operation with the shared job planner."""
        return await self.download(instruments,dataset='trades',start=start,end=end if end is not None else start,calendar=calendar,include_jdate=include_jdate,on_error=on_error,update=False,policy=policy)

    async def get_order_book_updates(self, instrument, *, start, end=None, calendar='gregorian', include_jdate=False, max_days=31, policy=None) -> pd.DataFrame:
        """Historical best-limit updates, not full snapshots.
        
        Args:
            instrument (Any): Instrument name or explicit instrument reference; ambiguity is not silently resolved.
            start (Any): Optional beginning of the requested date range.
            end (Any): Optional end of the requested date range.
            calendar (Any): Calendar used to parse or format dates.
            include_jdate (Any): Input for the get_order_book_updates operation.
            max_days (Any): Input for the get_order_book_updates operation.
            policy (Any): Fetch policy controlling network and cached/offline behavior.
        
        Notes:
            This coroutine must be awaited.
        
        Returns:
            pd.DataFrame: Result of the get_order_book_updates operation; refer to its public API contract for schema details."""
        return await self.get_order_book_history(instrument,start=start,end=end,calendar=calendar,include_jdate=include_jdate,max_days=max_days,policy=policy)
