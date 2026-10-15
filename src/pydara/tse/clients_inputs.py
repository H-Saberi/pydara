"""Public clients() output contracts; persistent data schemas are unchanged."""
from __future__ import annotations
import pandas as pd
from .market_schemas import empty_market_frame

_ALIASES = {
    'ins_code':'inscode', 'source_timestamp':'sourcetime',
    'fetched_at':'fetchedat','first_observed_at':'firstobservedat',
    'available_at':'availableat','from_cache':'fromcache',
    'is_stale':'isstale','source_position':'sourceposition',
    'buy_ddd_count':'buydddcount','buy_ddd_volume':'buydddvolume',
}
for _side, _short in (('individual','i'), ('institutional','l')):
    for _action in ('buy','sell'):
        for _metric in ('count','volume','value'):
            _ALIASES[f'{_side}_{_action}_{_metric}']=f'{_short}{_action}{_metric}'

def output(frames, errors, requests, *, numeric='analysis', include_jdate=False, calendar='gregorian'):
    """Return full client observations with simple, unique one-word column names."""
    result=pd.concat(frames,ignore_index=True) if frames else empty_market_frame(
        'client_types',numeric=numeric,include_jdate=include_jdate)
    mapping={name:_ALIASES.get(name,name.replace('_','')) for name in result.columns}
    if len(set(mapping.values())) != len(mapping):
        raise ValueError('Client output column-name collision.')
    result=result.rename(columns=mapping)
    result.attrs['pydara']={'schema_id':'clients.convenience.v1',
        'input_calendar':calendar,'requested_items':len(requests),
        'failed_items':len(errors),'requests':requests,'errors':errors,
        'items':[f.attrs.get('pydara',{}) for f in frames],
        'column_aliases':mapping}
    return result
