"""Explicit, bounded diagnostics. Never silently bypass a proxy or TLS checks."""
from __future__ import annotations
from dataclasses import replace
from datetime import datetime, UTC
import importlib.metadata
import sys
import time
import pandas as pd
import httpx
from pydara.tse._core.exceptions import ConfigurationError, InvalidArgumentError
from .config import ClientConfig, NetworkConfig, positive

PROBE='https://cdn.tsetmc.com/api/Instrument/GetInstrumentInfo/46348559193224090'


def check_connection(*, network='environment', allow_direct=False, timeout=10.0) -> pd.DataFrame:
    """Probe one reviewed small endpoint with explicit connection profiles.
    network: environment/direct/auto. auto tries direct ONLY when allow_direct=True.
    Does not alter configuration, disable certificate validation, or expose proxy URLs.
    """
    positive('timeout',timeout)
    if network not in ('environment','direct','auto'):raise InvalidArgumentError('Invalid network profile.')
    if not isinstance(allow_direct,bool):raise InvalidArgumentError('allow_direct must be bool.')
    profiles=[True] if network=='environment' else [False] if network=='direct' else [True,False] if allow_direct else [True]
    rows=[]
    for trust in profiles:
        started=time.monotonic();row=dict(profile='environment' if trust else 'direct',trust_env=trust,status='error',http_status=None,error_type=None,bytes=0)
        try:
            with httpx.Client(trust_env=trust,timeout=timeout,follow_redirects=False) as client:
                with client.stream('GET',PROBE) as response:
                    row['http_status']=response.status_code
                    chunks=[];size=0
                    for chunk in response.iter_bytes():
                        size+=len(chunk)
                        if size>2*1024*1024 or time.monotonic()-started>timeout:
                            raise ValueError('Probe exceeds limits.')
                        chunks.append(chunk)
                    row['bytes']=size
                    if response.status_code!=200:row['error_type']='HTTP_'+str(response.status_code)
                    else:
                        import json
                        value=json.loads(b''.join(chunks)).get('instrumentInfo')
                        if not isinstance(value,dict) or str(value.get('insCode'))!='46348559193224090':
                            raise ValueError('Probe shape/identity mismatch.')
                        row['status']='ok'
        except (httpx.HTTPError,ValueError,KeyError,TypeError) as exc:row['error_type']=type(exc).__name__
        row['elapsed_seconds']=round(time.monotonic()-started,3);rows.append(row)
    return pd.DataFrame(rows)


def setup(*, network='environment', allow_direct=False, probe=False, storage=None, data_dir=None, mode=None, numeric=None) -> ClientConfig:
    """Configure the lazy facade before use. Explicit network='direct' ignores
    environment proxy/CA settings but keeps TLS verification. auto requires a probe
    and direct consent. Close an already-used default client first; no hidden reset.
    Settings are in-process, not silently written into the user's home directory.
    """
    from . import configure, get_config
    if not isinstance(probe,bool) or not isinstance(allow_direct,bool):raise InvalidArgumentError('probe/allow_direct must be bool.')
    if network not in ('environment','direct','auto'):raise InvalidArgumentError('Invalid network profile.')
    config=get_config()
    if network=='auto':
        report=check_connection(network='auto',allow_direct=allow_direct)
        good=report.loc[report.status=='ok']
        if good.empty:raise ConfigurationError('No tested connection profile succeeded; inspect check_connection().')
        trust=bool(good.iloc[0].trust_env)
    else:
        trust=network=='environment'
        if probe and check_connection(network=network).status.ne('ok').any():
            raise ConfigurationError('Selected connection profile failed.')
    net=replace(config.network,trust_env=trust)
    return configure(config=replace(config,network=net),storage=storage,data_dir=data_dir,mode=mode,numeric=numeric)


def diagnose(*, live=False, network='environment', allow_direct=False) -> pd.DataFrame:
    """Version/dependency report without network by default; no credentials or proxy URLs."""
    from pydara import __version__
    if not isinstance(live,bool):raise InvalidArgumentError('live must be bool.')
    rows=[{'component':'python','status':'ok','value':sys.version.split()[0]}, {'component':'pydara','status':'ok','value':__version__}]
    for package in ('pandas','httpx','openpyxl','pyarrow','ipykernel'):
        try:value=importlib.metadata.version(package);status='ok'
        except importlib.metadata.PackageNotFoundError:value='not installed';status='optional_missing' if package in ('openpyxl','pyarrow','ipykernel') else 'missing'
        rows.append(dict(component=package,status=status,value=value))
    if live:
        for r in check_connection(network=network,allow_direct=allow_direct).to_dict('records'):
            rows.append(dict(component='connection:'+r['profile'],status=r['status'],value=r['error_type'] or 'verified_response'))
    return pd.DataFrame(rows)
