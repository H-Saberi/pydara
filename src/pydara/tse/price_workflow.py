"""Shared selectors and report assembly for the friendly price DataFrame API."""
from __future__ import annotations
import pandas as pd
from ._core.exceptions import InvalidArgumentError
from .history_inputs import selectors, codes_from_frame
from .instrument_lookup import lookup_policies
from ._core.models import InstrumentRef
from .frames import quote_row, quote_frame


def prepare(instrument, ins_code, on_multiple, on_conflict, on_error):
    """Validate price selectors and failure policy before any network request."""
    if on_error not in ('collect', 'raise'):
        raise InvalidArgumentError('on_error must be collect or raise.')
    lookup_policies(on_multiple, on_conflict, has_ins_code=ins_code is not None or isinstance(instrument, pd.DataFrame))
    return selectors(instrument, ins_code=ins_code, on_multiple=on_multiple, on_conflict=on_conflict)


def append_quotes(rows, matches, seen, fetch_quote, selector, index):
    """Return new codes with active state, leaving quote fetching to the caller."""
    jobs=[]
    for code in codes_from_frame(matches):
        if code in seen:
            continue
        seen.add(code)
        found=matches.loc[matches['ins_code'].astype('string') == code]
        active=found.iloc[0]['is_active'] if 'is_active' in found and not found.empty else pd.NA
        jobs.append((code, active))
    return jobs


def result(rows, errors, requests, numeric):
    """Create a typed quote DataFrame with per-selector metadata."""
    frame=quote_frame([], numeric=numeric, batch_rows=rows)
    frame['is_active']=pd.array([r.get('is_active', pd.NA) for r in rows], dtype='boolean')
    frame.attrs['pydara'].update(requests=requests, errors=errors,
                                  requested_items=len(requests), failed_items=len(errors))
    return frame
