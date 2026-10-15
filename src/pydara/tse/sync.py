"""Explicit incremental daily-history reconciliation.

Tail requests use the documented row-count parameter, not an invented date API.
A full snapshot is still required initially and periodically for old corrections.
"""
from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd

from pydara.tse._core.exceptions import (InvalidArgumentError, StorageError,
                                      OfflineDataUnavailableError)
from pydara.tse._core.models import WriteReceipt
from .config import FetchPolicy, FreshnessPolicy
from .history import HistoryQuery, history_frame
from .providers.history import history_spec
from .storage.history_store import HistoryStore


@dataclass(frozen=True, kw_only=True)
class SyncPlan:
    """Describe a planned history synchronization, including overlap and refresh rationale.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    ins_code: str
    symbol: str
    mode: str
    requested_rows: int
    overlap_start: date | None
    last_stored_date: date | None
    reason: str
    warnings: tuple[str,...] = ()


@dataclass(frozen=True, kw_only=True)
class SyncResult:
    """data is the fetched slice, not necessarily the full stored history."""
    data: pd.DataFrame
    plan: SyncPlan
    summary: dict
    write_receipt: WriteReceipt | None = None


def store_for(core):
    """Access a history repository backed by the configured storage path.
    
    Args:
        core (Any): Configured library core and its resources.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        StorageError: When the corresponding validation or operation fails."""
    core.check()
    if core.store is None:raise StorageError('Local storage is disabled.')
    return HistoryStore(core.store.path,namespace=core.namespace,numeric=core.config.numeric,
                        timeout=core.config.storage.offline_read_timeout)


def validate_sync(full,overlap_days,wait,timeout,on_storage_error,full_refresh_days):
    """Validate history synchronization flags and timing settings.
    
    Args:
        full (Any): Force full-history retrieval rather than an incremental tail.
        overlap_days (Any): Calendar-day overlap requested for incremental synchronization.
        wait (Any): Whether to wait for local persistence to finish.
        timeout (Any): Maximum wait time in seconds.
        on_storage_error (Any): How to handle incomplete local persistence: raise or report.
        full_refresh_days (Any): Maximum interval between full-history audits, in days.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails."""
    from .config import positive
    if not isinstance(full,bool) or not isinstance(wait,bool):raise InvalidArgumentError('full and wait must be bool.')
    if isinstance(overlap_days,bool) or not isinstance(overlap_days,int) or overlap_days<1:
        raise InvalidArgumentError('overlap_days must be a positive integer.')
    positive('timeout',timeout)
    positive('full_refresh_days',full_refresh_days)
    if on_storage_error not in ('raise','report'):raise InvalidArgumentError('on_storage_error must be raise or report.')


def plan_for(record,status,*,full,overlap_days,full_refresh_days=7,warnings=()):
    """Choose full or overlapping tail history retrieval from recorded storage status.
    
    Args:
        record (Any): Normalized instrument or market record.
        status (Any): Input for the plan_for operation.
        full (Any): Force full-history retrieval rather than an incremental tail.
        overlap_days (Any): Calendar-day overlap requested for incremental synchronization.
        full_refresh_days (Any): Maximum interval between full-history audits, in days.
        warnings (Any): Input for the plan_for operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    existing=status.loc[status.ins_code==record.ins_code] if not status.empty else status
    last=None
    if not existing.empty and pd.notna(existing.last_date.iloc[0]):
        last=date.fromisoformat(str(existing.last_date.iloc[0]))
    last_full = None if existing.empty else existing.last_full_fetch_at.iloc[0]
    periodic = last_full is None or pd.isna(last_full) or (datetime.now(UTC)-datetime.fromisoformat(str(last_full))) >= timedelta(days=full_refresh_days)
    if full or last is None or periodic:
        return SyncPlan(ins_code=record.ins_code,symbol=record.symbol,mode='full',requested_rows=0,
             overlap_start=None,last_stored_date=last,reason='explicit_full' if full else 'no_indexed_history' if last is None else 'periodic_full_audit',warnings=warnings)
    today=datetime.now(ZoneInfo('Asia/Tehran')).date()
    if last>today:
        return SyncPlan(ins_code=record.ins_code,symbol=record.symbol,mode='full',requested_rows=0,
             overlap_start=None,last_stored_date=last,reason='future_local_date_requires_review',warnings=warnings)
    start=last-timedelta(days=overlap_days)
    n=(today-start).days+2
    return SyncPlan(ins_code=record.ins_code,symbol=record.symbol,mode='tail',requested_rows=n,
                   overlap_start=start,last_stored_date=last,reason='new_days_plus_calendar_overlap',warnings=warnings)


def tail_plan(record,plan,namespace,numeric):
    """Build and decode a row-limited history request for a resolved instrument.
    
    Args:
        record (Any): Normalized instrument or market record.
        plan (Any): Input for the tail_plan operation.
        namespace (Any): Storage or frame metadata namespace.
        numeric (Any): Numeric conversion or output representation setting.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    spec=history_spec(record.ins_code,n=plan.requested_rows)
    packet=yield spec
    result=history_frame(packet,spec,namespace,record,HistoryQuery(None,None,'gregorian',False),numeric=numeric)
    result.attrs['pydara']['server_requested_rows']=plan.requested_rows
    if plan.requested_rows and len(result)>plan.requested_rows:
        result.attrs['pydara']['warnings'].append('source_returned_more_rows_than_requested')
    return result


def needs_full(plan,frame):
    """Check whether a tail response is insufficient to cover the planned overlap.
    
    Args:
        plan (Any): Input for the needs_full operation.
        frame (Any): DataFrame to convert, validate, process or store.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    if plan.mode!='tail':return False
    return frame.empty or frame.date.iloc[0].date()>plan.overlap_start


def complete_sync(core,frame,plan,*,fallback,wait,timeout,on_storage_error):
    """Summarize fetched history and its separately verified persistence outcome.
    
    Args:
        core (Any): Configured library core and its resources.
        frame (Any): DataFrame to convert, validate, process or store.
        plan (Any): Input for the complete_sync operation.
        fallback (Any): Input for the complete_sync operation.
        wait (Any): Whether to wait for local persistence to finish.
        timeout (Any): Maximum wait time in seconds.
        on_storage_error (Any): How to handle incomplete local persistence: raise or report.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        StorageError: When the corresponding validation or operation fails."""
    receipt_id=frame.attrs['pydara'].get('storage_receipt_id')
    receipt=report=None
    warning=None
    if wait and core.store:
        core.flush(timeout,False)
    try:
        if receipt_id and core.store:
            receipt=core.store.receipt(receipt_id)
            if receipt.state=='persisted':
                report=store_for(core).batch_report(frame.observation_id.iloc[0] if len(frame) else
                    receipt.request_id)
    except Exception as exc:warning=f'{type(exc).__name__}: {exc}'
    state=receipt.state if receipt else 'disabled' if not core.store else 'unknown'
    summary={'state':state,'network_mode':'tail_then_full' if fallback else plan.mode,
             'server_requested_rows':0 if fallback else plan.requested_rows,'counts_scope':'final_response_only',
             'fallback_to_full':fallback,'fetched_rows':len(frame),
             'inserted_rows':report['inserted_rows'] if report else None,
             'revised_rows':report['revised_rows'] if report else None,
             'unchanged_rows':report['unchanged_rows'] if report else None,
             'omitted_previous_rows':report['omitted_previous_rows'] if report else None,
             'coverage_status':'unknown','storage_error':warning or (receipt.reason if receipt else None)}
    result=SyncResult(data=frame,plan=plan,summary=summary,write_receipt=receipt)
    if on_storage_error=='raise' and (state in ('failed','skipped','disabled','unknown') or (wait and state!='persisted')):
        raise StorageError('History was fetched but normalized persistence did not complete.',report=result)
    return result


def sync_history(client,instrument,*,full=False,overlap_days=14,full_refresh_days=7,wait=True,timeout=30.0,on_storage_error='report'):
    """Synchronize daily history against local SQLite storage, with tail/full fallback.
    
    Args:
        client (Any): Synchronous or asynchronous client supplying operations.
        instrument (Any): Instrument name or explicit instrument reference; ambiguity is not silently resolved.
        full (Any): Force full-history retrieval rather than an incremental tail.
        overlap_days (Any): Calendar-day overlap requested for incremental synchronization.
        full_refresh_days (Any): Maximum interval between full-history audits, in days.
        wait (Any): Whether to wait for local persistence to finish.
        timeout (Any): Maximum wait time in seconds.
        on_storage_error (Any): How to handle incomplete local persistence: raise or report.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Notes:
        Returned ``data`` contains the retrieved slice, not necessarily all stored history.
        Offline mode reads local history; a network fetch does not guarantee persistence."""
    validate_sync(full,overlap_days,wait,timeout,on_storage_error,full_refresh_days)
    client._core.check()
    if client.config.mode=='offline':
        frame=store_for(client._core).read(instrument)
        code=frame.ins_code.iloc[0] if len(frame) else ''
        return SyncResult(data=frame,plan=SyncPlan(ins_code=code,symbol=str(instrument),mode='offline',
            requested_rows=0,overlap_start=None,last_stored_date=None,reason='explicit_offline'),
            summary={'state':'offline_read','network_requests':0,'coverage_status':'unknown'})
    record=client._resolve_instrument_record(instrument)
    warnings=()
    try:status=store_for(client._core).status()
    except Exception as exc:status=pd.DataFrame();warnings=(f'local_index_unavailable:{type(exc).__name__}',)
    plan=plan_for(record,status,full=full,overlap_days=overlap_days,full_refresh_days=full_refresh_days,warnings=warnings)
    policy=FetchPolicy(mode='online',freshness=FreshnessPolicy(max_age=timedelta(0)))
    frame=client._run(tail_plan(record,plan,client._core.namespace,client.config.numeric),policy=policy)
    fallback=needs_full(plan,frame)
    if fallback:
        from dataclasses import replace
        frame=client._run(tail_plan(record,replace(plan,requested_rows=0),client._core.namespace,
                                   client.config.numeric),policy=policy)
    return complete_sync(client._core,frame,plan,fallback=fallback,wait=wait,timeout=timeout,
                         on_storage_error=on_storage_error)


async def async_sync_history(client,instrument,*,full=False,overlap_days=14,full_refresh_days=7,wait=True,timeout=30.0,on_storage_error='report'):
    """Asynchronously synchronize daily history using thread-safe local persistence.
    
    Args:
        client (Any): Synchronous or asynchronous client supplying operations.
        instrument (Any): Instrument name or explicit instrument reference; ambiguity is not silently resolved.
        full (Any): Force full-history retrieval rather than an incremental tail.
        overlap_days (Any): Calendar-day overlap requested for incremental synchronization.
        full_refresh_days (Any): Maximum interval between full-history audits, in days.
        wait (Any): Whether to wait for local persistence to finish.
        timeout (Any): Maximum wait time in seconds.
        on_storage_error (Any): How to handle incomplete local persistence: raise or report.
    
    Notes:
        This coroutine must be awaited.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Notes:
        Returned ``data`` contains the retrieved slice, not necessarily all stored history.
        Offline mode reads local history; a network fetch does not guarantee persistence."""
    validate_sync(full,overlap_days,wait,timeout,on_storage_error,full_refresh_days)
    client._core.check()
    if client.config.mode=='offline':
        frame=await asyncio.to_thread(store_for(client._core).read,instrument)
        return SyncResult(data=frame,plan=SyncPlan(ins_code=frame.ins_code.iloc[0] if len(frame) else '',
            symbol=str(instrument),mode='offline',requested_rows=0,overlap_start=None,last_stored_date=None,
            reason='explicit_offline'),summary={'state':'offline_read','network_requests':0,'coverage_status':'unknown'})
    record=await client._resolve_instrument_record(instrument)
    warnings=()
    try:status=await asyncio.to_thread(store_for(client._core).status)
    except Exception as exc:status=pd.DataFrame();warnings=(f'local_index_unavailable:{type(exc).__name__}',)
    plan=plan_for(record,status,full=full,overlap_days=overlap_days,full_refresh_days=full_refresh_days,warnings=warnings)
    policy=FetchPolicy(mode='online',freshness=FreshnessPolicy(max_age=timedelta(0)))
    frame=await client._run(tail_plan(record,plan,client._core.namespace,client.config.numeric),policy=policy)
    fallback=needs_full(plan,frame)
    if fallback:
        from dataclasses import replace
        frame=await client._run(tail_plan(record,replace(plan,requested_rows=0),client._core.namespace,
                                         client.config.numeric),policy=policy)
    # SQLite and flush never execute directly on the caller's event loop.
    return await asyncio.to_thread(complete_sync,client._core,frame,plan,fallback=fallback,
                                   wait=wait,timeout=timeout,on_storage_error=on_storage_error)
