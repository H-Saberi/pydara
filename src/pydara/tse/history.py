"""Shared history orchestration, table schema, batch results and local chunking."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
import warnings

import pandas as pd

from pydara import __version__
from pydara.tse._core.exceptions import (
    CoverageError, InvalidArgumentError, PointInTimeUnavailableError,
    StaleDataWarning, UnsupportedCapabilityError,
)
from .dates import Calendar, DateLike, parse_range, to_jalali
from .frames import cast_frame
from .config import coerce_policy
from .history_models import BatchFrames
from .providers.history import NUMERIC_FIELDS, history_spec, parse_history_rows
from .providers.public import instrument_plan

STRINGS = [
    'ins_code', 'symbol', 'raw_symbol', 'instrument_id', 'company_cisin',
    'currency', 'quote_unit', 'quantity_unit', 'adjustment', 'series',
    'source', 'endpoint_id', 'scope_id', 'row_id', 'row_version_id', 'observation_id',
    'payload_hash', 'raw_reference', 'raw_ins_code', 'source_record_id',
    'availability_basis', 'storage_receipt_id', 'timestamp_kind',
]
TIMES = ['source_timestamp', 'fetched_at', 'first_observed_at', 'available_at',
         'identity_fetched_at']
BOOLS = ['from_cache', 'is_stale']
DISPLAY_COLUMNS = ['date', 'ins_code', 'symbol', 'open_price', 'high_price', 'low_price',
                   'last_price', 'closing_price', 'previous_reference_price',
                   'volume', 'turnover', 'trade_count']


@dataclass(frozen=True)
class HistoryQuery:
    """Represent history query data used by the TSE module.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    start: date | None
    end: date | None
    calendar: str
    include_jdate: bool
    adjustment: str = "none"


def prepare_history(*, start=None, end=None, calendar='gregorian', adjustment='none',
                    series='listing', as_of=None, include_jdate=False) -> HistoryQuery:
    """Prepare history.
    
    Args:
        start (Any): Optional beginning of the requested date range.
        end (Any): Optional end of the requested date range.
        calendar (Any): Calendar used to parse or format dates.
        adjustment (Any): Input for the prepare_history operation.
        series (Any): Input for the prepare_history operation.
        as_of (Any): Requested economic effective date; check endpoint support.
        include_jdate (Any): Input for the prepare_history operation.
    
    Returns:
        HistoryQuery: Result of the prepare_history operation; refer to its public API contract for schema details.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails.
        PointInTimeUnavailableError: When the corresponding validation or operation fails.
        UnsupportedCapabilityError: When the corresponding validation or operation fails."""
    if adjustment not in ('none', 'source'):
        raise InvalidArgumentError('adjustment must be none or source.')
    if series not in ('listing', 'continuous_verified'):
        raise InvalidArgumentError('series must be listing or continuous_verified.')
    if series != 'listing':
        raise UnsupportedCapabilityError('A verified historical identity chain is not implemented.')
    if as_of is not None:
        if not isinstance(as_of, datetime) or as_of.tzinfo is None or as_of.utcoffset() is None:
            raise InvalidArgumentError('as_of must be a timezone-aware datetime.')
        raise PointInTimeUnavailableError('Point-in-time snapshot selection is not implemented in Part 2.')
    if not isinstance(include_jdate, bool):
        raise InvalidArgumentError('include_jdate must be bool.')
    lo, hi = parse_range(start, end, calendar=calendar)
    return HistoryQuery(lo, hi, calendar, include_jdate, adjustment)


def history_plan(instrument, *, query: HistoryQuery, namespace='public', numeric='analysis'):
    """Perform the history plan operation.
    
    Args:
        instrument (Any): Instrument name or explicit instrument reference; ambiguity is not silently resolved.
        query (HistoryQuery): Instrument or market search text.
        namespace (Any): Storage or frame metadata namespace.
        numeric (Any): Numeric conversion or output representation setting.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    if query.adjustment == 'source':
        from .extended import instrument_table_plan
        return (yield from instrument_table_plan(instrument, name='extra.adjusted', start=query.start, end=query.end, include_jdate=query.include_jdate, namespace=namespace, numeric=numeric))
    record = yield from instrument_plan(instrument, namespace=namespace)
    spec = history_spec(record.ins_code)
    packet = yield spec
    return history_frame(packet, spec, namespace, record, query, numeric=numeric)


def empty_history_frame(*, numeric='analysis', include_jdate=False) -> pd.DataFrame:
    """Create an empty history frame.
    
    Args:
        numeric (Any): Numeric conversion or output representation setting.
        include_jdate (Any): Input for the empty_history_frame operation.
    
    Returns:
        pd.DataFrame: Result of the empty_history_frame operation; refer to its public API contract for schema details."""
    frame = cast_frame([], STRINGS, TIMES, BOOLS, list(NUMERIC_FIELDS), ['trade_count'],
                       numeric=numeric, extra=['date', 'quality_flags'])
    frame['date'] = pd.Series(dtype='datetime64[ns]')
    if include_jdate:
        frame['jdate'] = pd.Series(dtype='string')
    return frame[[*DISPLAY_COLUMNS, *[c for c in frame if c not in DISPLAY_COLUMNS]]]


def history_frame(packet, spec, namespace, record, query, *, numeric):
    """Perform the history frame operation.
    
    Args:
        packet (Any): Response packet received from a provider.
        spec (Any): Request or schema specification.
        namespace (Any): Storage or frame metadata namespace.
        record (Any): Normalized instrument or market record.
        query (Any): Instrument or market search text.
        numeric (Any): Numeric conversion or output representation setting.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    parsed = parse_history_rows(packet, spec)
    rows = []
    for original in parsed.rows:
        day = original['date']
        if query.start is not None and day < query.start or query.end is not None and day > query.end:
            continue
        flags = list(original['quality_flags'])
        flags.extend(record.meta.quality_flags)
        flags.append('identity_resolved_from_current_instrument_info')
        flags.append('publication_time_unknown')
        if packet.is_stale:
            flags.append('stale_cached_response')
        if record.meta.is_stale:
            flags.append('stale_identity_response')
        if namespace == 'sample':
            flags.append('synthetic_sample_not_market_data')
        if numeric == 'analysis' and any(original[field] is not None
                and abs(original[field]) > 2**53 for field in NUMERIC_FIELDS):
            flags.append('large_numeric_value_use_exact_profile')
        row = dict(original, symbol=record.symbol, raw_symbol=record.raw_symbol,
                   instrument_id=record.instrument_id, company_cisin=record.company_cisin,
                   currency=record.currency, quote_unit=record.quote_unit,
                   quantity_unit=record.quantity_unit, adjustment='none', series='listing',
                   source='public', endpoint_id=spec.endpoint_id, scope_id=namespace,
                   row_id=sha256(f'{namespace}:daily:{record.ins_code}:{day}'.encode()).hexdigest(),
                   observation_id=packet.request_id, payload_hash=packet.payload_hash,
                   raw_reference=packet.payload_hash, availability_basis='observed_response',
                   # Conservative: fetched_at, NOT the historical trade date.
                   available_at=packet.fetched_at, fetched_at=packet.fetched_at,
                   first_observed_at=packet.first_observed_at,
                   identity_fetched_at=record.meta.retrieved_at,
                   storage_receipt_id=packet.receipt_id, from_cache=packet.from_cache,
                   is_stale=packet.is_stale, timestamp_kind='source_hEven_semantics_unverified',
                   quality_flags=tuple(dict.fromkeys(flags)))
        rows.append(row)
    frame = cast_frame(rows, STRINGS, TIMES, BOOLS, list(NUMERIC_FIELDS), ['trade_count'],
                       numeric=numeric, extra=['date', 'quality_flags'])
    frame['date'] = pd.to_datetime(frame['date']).astype('datetime64[ns]')
    if query.include_jdate:
        frame['jdate'] = pd.Series([to_jalali(r['date']) for r in rows], dtype='string')
    frame = frame[[*DISPLAY_COLUMNS, *[c for c in frame if c not in DISPLAY_COLUMNS]]]
    observed = parsed.rows
    source_start = observed[0]['date'].isoformat() if observed else None
    source_end = observed[-1]['date'].isoformat() if observed else None
    warnings_ = ['complete_listing_history_not_certified', 'not_a_point_in_time_dataset']
    if parsed.identical_duplicates:
        warnings_.append('identical_duplicate_rows_removed')
    if packet.is_stale:
        warnings_.append('stale_cached_response')
    frame.attrs['pydara'] = dict(
        schema_id='daily_bars', schema_version='1', parser_version='history-1',
        package_version=__version__, numeric=numeric, adjustment='none', series='listing',
        calendar_input=query.calendar, date_calendar='gregorian',
        requested_range={'start':query.start.isoformat() if query.start else None,
                         'end':query.end.isoformat() if query.end else None},
        source_observed_range={'start':source_start,'end':source_end},
        returned_range={'start':rows[0]['date'].isoformat() if rows else None,
                        'end':rows[-1]['date'].isoformat() if rows else None},
        coverage_status='unknown', query_status='rows_returned' if rows else 'empty',
        no_rows_reason=None if rows else 'empty_source' if not observed else 'no_rows_in_requested_range',
        source_row_count=parsed.source_row_count, unique_source_rows=len(observed),
        identical_duplicates_removed=parsed.identical_duplicates, returned_rows=len(rows),
        source='public', endpoint_id=spec.endpoint_id, scope_id=namespace,
        fetched_at=packet.fetched_at.isoformat(), first_observed_at=packet.first_observed_at.isoformat(),
        available_at=packet.fetched_at.isoformat(), availability_basis='observed_response',
        from_cache=packet.from_cache, is_stale=packet.is_stale,
        raw_reference=packet.payload_hash, storage_receipt_id=packet.receipt_id,
        warnings=warnings_, retrieval_strategy='full_response_then_local_filter',
        no_trade_policy='preserve_reported_rows_no_fill',
        note='attrs may be lost in Pandas operations; provenance is also stored in columns.',
    )
    return frame


def finish_history(frame: pd.DataFrame, policy=None) -> pd.DataFrame:
    """Finalize history.
    
    Args:
        frame (pd.DataFrame): DataFrame to convert, validate, process or store.
        policy (Any): Fetch policy controlling network and cached/offline behavior.
    
    Returns:
        pd.DataFrame: Result of the finish_history operation; refer to its public API contract for schema details.
    
    Raises:
        CoverageError: When the corresponding validation or operation fails."""
    metadata = frame.attrs['pydara']
    policy = coerce_policy(policy)
    if policy is not None and policy.coverage == 'raise':
        raise CoverageError('The public endpoint does not certify complete historical coverage.',
                            report=deepcopy(metadata))
    if metadata['is_stale']:
        try:
            warnings.warn('Returning explicitly permitted cached history; it may miss later corrections.',
                          StaleDataWarning, stacklevel=3)
        except StaleDataWarning:
            pass
    return frame


def validate_chunks(chunk_days):
    """Validate chunks.
    
    Args:
        chunk_days (Any): Input for the validate_chunks operation.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails."""
    if isinstance(chunk_days, bool) or not isinstance(chunk_days, int) or chunk_days <= 0:
        raise InvalidArgumentError('chunk_days must be a positive integer.')


def split_history_frames(frame: pd.DataFrame, start: date, end: date, chunk_days: int):
    """Local output chunks, NOT incremental network fetch or bounded response memory."""
    validate_chunks(chunk_days)
    if frame.empty:
        chunk = frame.copy(deep=True)
        chunk.attrs = deepcopy(frame.attrs)
        chunk.attrs['pydara']['chunk'] = {'index':0,'start':str(start),'end':str(end)}
        yield chunk
        return
    current, index = start, 0
    while current <= end:
        remaining = (end - current).days
        upper = current + timedelta(days=min(chunk_days - 1, remaining))
        selected = frame.loc[(frame['date'] >= pd.Timestamp(current)) &
                             (frame['date'] <= pd.Timestamp(upper))].copy(deep=True)
        if not selected.empty:
            selected.reset_index(drop=True, inplace=True)
            selected.attrs = deepcopy(frame.attrs)
            metadata = selected.attrs['pydara']
            metadata['chunk'] = {'index':index,'start':str(current),'end':str(upper)}
            metadata['returned_rows'] = len(selected)
            metadata['returned_range'] = {'start':str(selected['date'].iloc[0].date()),
                                           'end':str(selected['date'].iloc[-1].date())}
            yield selected
            index += 1
        current = upper + timedelta(days=1)


class HistoryBatchBuilder:
    """Encapsulate history batch builder behavior in the TSE module.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    def __init__(self, *, numeric='analysis', include_jdate=False, total=0):
        """Initialize the instance and its configured state.
        
        Args:
            numeric (Any): Numeric conversion or output representation setting.
            include_jdate (Any): Input for the __init__ operation.
            total (Any): Input for the __init__ operation."""
        self.numeric, self.include_jdate, self.total = numeric, include_jdate, total
        self.frames, self.errors, self.requests = [], [], []
        self.manifests = []

    @staticmethod
    def input_text(item):
        """Perform the input text operation.
        
        Args:
            item (Any): Input for the input_text operation.
        
        Returns:
            Implementation-defined result or generator output; see the calling API."""
        return item if isinstance(item, str) else f'{item.kind}:{item.value}'

    def success(self, index, item, frame):
        """Perform the success operation.
        
        Args:
            index (Any): Input for the success operation.
            item (Any): Input for the success operation.
            frame (Any): DataFrame to convert, validate, process or store."""
        out = frame.copy(deep=True)
        self.manifests.append({'request_index':index, **deepcopy(frame.attrs['pydara'])})
        out.attrs = {}
        out['request_index'] = pd.Series([index]*len(out), dtype='Int64')
        out['input_symbol'] = pd.Series([self.input_text(item)]*len(out), dtype='string')
        self.frames.append(out)
        self.requests.append({'request_index':index, 'input_symbol':self.input_text(item),
                              'status':'empty' if frame.empty else 'ok', 'row_count':len(frame),
                              'error_code':None, 'error_message':None})

    def failure(self, index, item, exc):
        """Perform the failure operation.
        
        Args:
            index (Any): Input for the failure operation.
            item (Any): Input for the failure operation.
            exc (Any): Input for the failure operation."""
        row = {'request_index':index,'input_symbol':self.input_text(item),
               'error_code':type(exc).__name__,'error_message':str(exc)}
        self.errors.append(row)
        self.requests.append({**row,'status':'error','row_count':0})

    def result(self):
        """Perform the result operation.
        
        Returns:
            Implementation-defined result or generator output; see the calling API."""
        data = (pd.concat(self.frames, ignore_index=True) if self.frames else
                empty_history_frame(numeric=self.numeric, include_jdate=self.include_jdate))
        if 'request_index' not in data:
            data['request_index'] = pd.Series(dtype='Int64')
            data['input_symbol'] = pd.Series(dtype='string')
        errors = pd.DataFrame(self.errors, columns=['request_index','input_symbol','error_code','error_message'])
        requests = pd.DataFrame(self.requests, columns=['request_index','input_symbol','status','row_count',
                                                        'error_code','error_message'])
        for frame in (errors, requests):
            frame['request_index'] = frame['request_index'].astype('Int64')
            for col in frame:
                if col not in ('request_index','row_count'):
                    frame[col] = frame[col].astype('string')
        requests['row_count'] = requests['row_count'].astype('Int64')
        manifest = {'schema_id':'daily_bars.batch','schema_version':'1','package_version':__version__,
                    'coverage_status':'unknown','requested_items':self.total,
                    'processed_items':len(requests),'failed_items':len(errors),
                    'unprocessed_items':self.total-len(requests),'items':deepcopy(self.manifests)}
        data.attrs['pydara'] = deepcopy(manifest)
        return BatchFrames(data=data, errors=errors, requests=requests, manifest=manifest)
