"""Public, source-backed intraday execution selection and time filtering."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, time
from pathlib import Path
import hashlib
import json
import os
import sys
from zoneinfo import ZoneInfo
import pandas as pd

from ._core.models import InstrumentRef
from ._core.exceptions import InvalidArgumentError
from .friendly import friendly_range
from .public_workflows import _source_selectors

_TEHRAN = ZoneInfo('Asia/Tehran')
_COLUMNS = ('inscode', 'symbol', 'market', 'date', 'jdate', 'time', 'tradeid',
            'sequence', 'price', 'quantity', 'value', 'sourcetimestamp',
            'fetchedat', 'source', 'fromcache', 'isstale')


def _clock(value, name):
    """Validate and normalize a Tehran-local wall-clock value."""
    if isinstance(value, time):
        if value.tzinfo is not None:
            raise InvalidArgumentError(f'{name} must be Tehran-local wall time without timezone.')
        return value
    if not isinstance(value, str):
        raise InvalidArgumentError(f'{name} must be HH:MM or HH:MM:SS.')
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise InvalidArgumentError(f'{name} must be a valid HH:MM or HH:MM:SS.') from exc


def trades(client, *, assets=None, ins_code=None, start=None, end=None,
           starttime='00:00:00', endtime='23:59:59', calendar='auto',
           include_jdate=True, max_days=31, on_multiple='all',
           on_conflict='error', on_error='collect', policy=None,
           maxassets=20, progress=True, workers=1, checkpoint=None):
    """Retrieve source-reported individual executions for a selected date/time window.

    This does not reconstruct missing intraday ticks. Source ``tradeid``,
    ``sequence``, cancellation state, original timestamps and provenance survive.
    Same-second executions are retained, not deduplicated.
    """
    if isinstance(maxassets, bool) or not isinstance(maxassets, int) or maxassets < 1:
        raise InvalidArgumentError('maxassets must be a positive integer.')
    if isinstance(workers, bool) or not isinstance(workers, int) or workers != 1:
        raise InvalidArgumentError('workers must be 1: shared Client is not thread-safe; parallel mode is not supported.')
    if not isinstance(progress, bool):
        raise InvalidArgumentError('progress must be bool.')
    if checkpoint is not None and not isinstance(checkpoint, (str, os.PathLike)):
        raise InvalidArgumentError('checkpoint must be a local directory path or None.')
    if on_error not in ('collect', 'raise'):
        raise InvalidArgumentError('on_error must be "collect" or "raise".')
    if not isinstance(include_jdate, bool):
        raise InvalidArgumentError('include_jdate must be bool.')
    if isinstance(max_days, bool) or not isinstance(max_days, int) or not 1 <= max_days <= 366:
        raise InvalidArgumentError('max_days must be an integer from 1 to 366.')
    begin_time, finish_time = _clock(starttime, 'starttime'), _clock(endtime, 'endtime')
    if begin_time > finish_time:
        raise InvalidArgumentError('starttime must not be after endtime on a single day.')
    today = datetime.now(_TEHRAN).date()
    if start is None and end is None:
        lo = hi = today
    elif start is None:
        lo, _, _ = friendly_range(end, None, calendar=calendar)
        hi = lo
    else:
        lo, hi, _ = friendly_range(start, end, calendar=calendar)
        hi = hi if hi is not None else today
    if lo > hi:
        raise InvalidArgumentError('start cannot be after end.')
    if (hi - lo).days + 1 > max_days:
        raise InvalidArgumentError('Requested calendar span exceeds max_days; split into batches.')
    normalized = assets.rename(columns={'inscode':'ins_code'}) if isinstance(assets, pd.DataFrame) and 'inscode' in assets else assets
    selected = _source_selectors(normalized, ins_code, on_multiple, on_conflict)
    if selected is None:
        raise InvalidArgumentError('trades requires assets or ins_code; a whole-market intraday download is not implicit.')
    if not selected:
        empty = pd.DataFrame(columns=_COLUMNS)
        empty.attrs['pydara'] = {'schema_id': 'trades.public', 'requested_items': 0,
                                 'errors': [], 'coverage_status': 'empty_selection'}
        return empty
    if len(selected) > maxassets:
        raise InvalidArgumentError(f'{len(selected)} instruments requested; maxassets={maxassets}. Increase maxassets explicitly to proceed.')
    # A checkpoint stores completed source-backed frames only, never synthetic values.
    # Key includes source parameters to prevent cross-window or policy reuse.
    checkpoint_dir = Path(checkpoint).expanduser() if checkpoint is not None else None
    if checkpoint_dir is not None:
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
    reports, failures, frames, seen = [], [], [], set()
    resumed = 0
    finished = 0
    total = len(selected)
    identities = {}
    if isinstance(assets, pd.DataFrame):
        code_col = 'inscode' if 'inscode' in assets else 'ins_code'
        if code_col in assets:
            for _, row in assets.iterrows():
                code = str(row[code_col])
                if code not in identities:
                    identities[code] = {key: row[key] for key in ('symbol', 'market') if key in assets and pd.notna(row[key])}
    for item in selected:
        try:
            if 'ins_code' in item:
                codes = [InstrumentRef.by_ins_code(str(item['ins_code'])).value]
            else:
                matches = client.instrument(symbol=item['symbol'], on_multiple=on_multiple,
                                            on_conflict=on_conflict, policy=policy)
                codes = [str(code) for code in matches['ins_code']]
            for code in codes:
                if code in seen:
                    continue
                seen.add(code)
                try:
                    signature = json.dumps({'code':code,'start':lo.isoformat(),
                        'end':hi.isoformat(),'calendar':'gregorian',
                        'include_jdate':include_jdate,'policy':str(policy)}, sort_keys=True)
                    key = hashlib.sha256(signature.encode('utf-8')).hexdigest()
                    stored = checkpoint_dir / (key + '.json') if checkpoint_dir is not None else None
                    if stored is not None and stored.is_file():
                        payload = json.loads(stored.read_text(encoding='utf-8'))
                        if payload.get('signature') != signature:
                            raise InvalidArgumentError('Checkpoint identity does not match the request.')
                        frame = pd.read_json(__import__('io').StringIO(payload['frame']), orient='table')
                        frame.attrs['pydara'] = payload.get('metadata', {})
                        resumed += 1
                    else:
                        frame = client.get_trades(InstrumentRef.by_ins_code(code), start=lo, end=hi,
                                              calendar='gregorian', include_jdate=include_jdate,
                                              max_days=max_days, policy=policy)
                        if stored is not None:
                            payload = {'signature':signature, 'frame':frame.to_json(orient='table', date_format='iso'),
                                'metadata':frame.attrs.get('pydara', {})}
                            # Atomically publish only a completely fetched asset.
                            tmp = stored.with_suffix('.tmp')
                            tmp.write_text(json.dumps(payload, default=str, ensure_ascii=False), encoding='utf-8')
                            os.replace(tmp, stored)
                    meta = deepcopy(frame.attrs.get('pydara', {}))
                    output = frame.copy()
                    if 'source_timestamp' in output:
                        stamp = pd.to_datetime(output['source_timestamp'], utc=True, errors='coerce')
                        local = stamp.dt.tz_convert(_TEHRAN)
                        # Inclusive source timestamps only; unknown times cannot be certified.
                        if begin_time != time.min or finish_time != time(23, 59, 59):
                            source_clock = local.dt.time
                            valid = stamp.notna() & source_clock.map(
                                lambda value: pd.notna(value) and begin_time <= value <= finish_time)
                            output = output.loc[valid].copy()
                            local = local.loc[valid]
                        output['time'] = local.dt.strftime('%H:%M:%S')
                    else:
                        if begin_time != time.min or finish_time != time(23, 59, 59):
                            output = output.iloc[0:0].copy()
                        output['time'] = pd.Series(index=output.index, dtype='string')
                    for key, value in identities.get(code, {}).items():
                        if key not in output:
                            output[key] = value
                        else:
                            output[key] = output[key].fillna(value)
                    frames.append(output)
                    reports.append({'inscode': code, 'metadata': meta, 'rows': len(output)})
                except Exception as exc:
                    if on_error == 'raise':
                        raise
                    failures.append({'inscode': code, 'error': type(exc).__name__, 'message': str(exc)})
                finally:
                    finished += 1
                    if progress:
                        print(f'PyDara trades: {finished} / {total} instruments processed', file=sys.stderr, flush=True)
        except Exception as exc:
            if on_error == 'raise':
                raise
            failures.append({'selector': str(item), 'error': type(exc).__name__, 'message': str(exc)})
    output = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    output = output.rename(columns={col: col.replace('_', '') for col in output.columns})
    for col in _COLUMNS:
        if col not in output:
            output[col] = pd.Series(dtype='object')
    output = output[[*_COLUMNS, *(col for col in output if col not in _COLUMNS)]]
    output.attrs['pydara'] = {
        'schema_id': 'trades.public', 'coverage_status': 'source_reported_only',
        'requests': reports, 'requested_items': len(selected), 'failed_items': len(failures),
        'errors': failures, 'requested_range': {'start': str(lo), 'end': str(hi),
                                               'starttime': str(begin_time), 'endtime': str(finish_time)},
        'timezone': 'Asia/Tehran', 'unknown_execution_time_excluded_when_filtering': True,
        'not_a_complete_intraday_tape': True, 'resumed_items': resumed,
        'checkpoint_enabled': checkpoint_dir is not None, 'workers': workers,
        'is_stale': any(r['metadata'].get('is_stale', False) for r in reports),
        'synthetic': any(r['metadata'].get('synthetic', False) for r in reports),
    }
    return output
