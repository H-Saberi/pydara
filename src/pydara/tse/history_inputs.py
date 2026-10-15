"""Normalize the public convenience history inputs without changing lower-level history APIs."""
from __future__ import annotations
from collections.abc import Sequence
import numpy as np
import pandas as pd
from ._core.models import InstrumentRef
from ._core.exceptions import InvalidArgumentError
from .instrument_lookup import lookup_policies


def selectors(instrument=None, *, ins_code=None, symbol=None, on_multiple="all", on_conflict="error"):
    """Return independent selectors in input order; never guess a numeric symbol is a code.

    A DataFrame is an instrument table containing ``ins_code``; each row can also
    carry ``symbol`` as an identity check. Explicit ``ins_code`` and ``symbol``
    kwargs can be combined with the same conflict rule as ``instrument()``.
    """
    lookup_policies(on_multiple, on_conflict, has_ins_code=ins_code is not None)
    if instrument is not None and (ins_code is not None or symbol is not None):
        raise InvalidArgumentError('Pass instrument OR keyword ins_code/symbol, not both.')
    if instrument is None:
        if ins_code is None and symbol is None:
            raise InvalidArgumentError('Supply instrument, ins_code or symbol.')
        if ins_code is not None:
            from .instrument_lookup import normalize_ins_codes
            return [dict(ins_code=code, **({"symbol":symbol} if symbol is not None else {}))
                    for code in normalize_ins_codes(ins_code)]
        return [dict(symbol=symbol)]
    if isinstance(instrument, pd.DataFrame):
        if 'ins_code' not in instrument:
            raise InvalidArgumentError('Instrument DataFrame requires an ins_code column.')
        items=[]
        for _, row in instrument.iterrows():
            code=row['ins_code']
            if pd.isna(code):
                raise InvalidArgumentError('Instrument DataFrame contains a missing ins_code.')
            item={'ins_code':code}
            if 'symbol' in row and pd.notna(row['symbol']):
                item['symbol']=row['symbol']
            items.append(item)
        return items
    if isinstance(instrument, InstrumentRef):
        if instrument.kind == 'ins_code':
            return [dict(ins_code=instrument.value)]
        if instrument.kind == 'symbol':
            return [dict(symbol=instrument.value)]
        raise InvalidArgumentError('ISIN-only history resolution is not supported.')
    if isinstance(instrument, str):
        return [dict(symbol=instrument)]
    if isinstance(instrument, (list, tuple, pd.Series, pd.Index, np.ndarray)):
        if isinstance(instrument, np.ndarray) and instrument.ndim != 1:
            raise InvalidArgumentError('Expected a one-dimensional input list.')
        items=[]
        for value in instrument:
            if isinstance(value, (list, tuple, pd.DataFrame, np.ndarray)):
                raise InvalidArgumentError('Nested instrument input is not supported.')
            items.extend(selectors(value, on_multiple=on_multiple, on_conflict=on_conflict))
        return items
    raise InvalidArgumentError('Expected a symbol, InstrumentRef, instrument DataFrame or 1D list.')


def codes_from_frame(frame):
    """Extract unique codes in source order without silently discarding invalid records."""
    if 'ins_code' not in frame:
        raise InvalidArgumentError('Instrument result must have ins_code.')
    result=[]
    for code in frame['ins_code']:
        if pd.isna(code):
            raise InvalidArgumentError('Resolved instrument has no ins_code.')
        ref=InstrumentRef.by_ins_code(str(code))
        if ref.value not in result:
            result.append(ref.value)
    return result


def merged_result(frames, errors, requests, *, numeric='analysis', include_jdate=False, calendar='gregorian'):
    """Return one DataFrame with preserved provenance and explicit batch reports."""
    from .history import empty_history_frame
    if frames:
        out=pd.concat(frames, ignore_index=True)
    else:
        out=empty_history_frame(numeric=numeric, include_jdate=include_jdate)
    meta={
        'schema_id':'daily_bars.history_convenience',
        'coverage_status':'unknown',
        'input_calendar':calendar,
        'requested_items':len(requests),
        'failed_items':len(errors),
        'requests':requests,
        'errors':errors,
        'items':[item for frame in frames for item in [frame.attrs.get('pydara',{})]],
    }
    out.attrs['pydara']=meta
    return out
