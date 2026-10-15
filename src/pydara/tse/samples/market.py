"""Explicit synthetic fixtures for the market extension; never real network data."""
from __future__ import annotations
from copy import deepcopy
from importlib.resources import files
import json
import httpx


def fixtures():
    """Perform the fixtures operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    return json.loads(files(__package__).joinpath('market_fixture.json').read_text(encoding='utf8'))


def legacy_fixture(fixture):
    """Perform the legacy fixture operation.
    
    Args:
        fixture (Any): Input for the legacy_fixture operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    rows=[];orders=[]
    for r in fixture['market.watch']['marketwatch']:
        cols=[r['insCode'],r.get('insID',''),r['lva'],r['lvc'],str(r['hEven']),str(r['priceFirst']),
            str(r['pClosing']),str(r['pDrCotVal']),str(r['zTotTran']),str(r['qTotTran5J']),str(r['qTotCap']),
            str(r['priceMin']),str(r['priceMax']),str(r['priceYesterday']),str(r['eps']),str(r.get('bv',0)),
            '0',str(r['flow']),r['csv'],'2000','1000',str(r.get('ztd',0)),r['yVal']]
        rows.append(','.join(cols))
        for b in r.get('blDs',[]):orders.append(','.join(str(x) for x in [r['insCode'],b['n'],b['zmo'],b['zmd'],b['pmd'],b['pmo'],b['qmd'],b['qmo']]))
    return ('0@synthetic_uninterpreted_market_state@'+';'.join(rows)+'@'+';'.join(orders)+'@12345').encode()


def market_transport(*, responses=None):
    """Perform the market transport operation.
    
    Args:
        responses (Any): Input for the market_transport operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    fixture=fixtures()
    if responses:fixture.update(deepcopy(responses))
    from . import sample_transport
    old=sample_transport()
    def handler(request):
        """Perform the handler operation.
        
        Args:
            request (Any): Input for the handler operation.
        
        Returns:
            Implementation-defined result or generator output; see the calling API."""
        path=request.url.path
        if path.endswith('/MarketWatchInit.aspx'):return httpx.Response(200,content=legacy_fixture(fixture))
        key=None
        routes={
            'GetMarketWatch':'market.watch','GetMarketOverview':'market.overview','GetMarketMap':'market.map',
            'GetSectorsSummary':'market.sectors','GetRelatedCompany':'market.related',
            'GetInstValueAllInstAllParam':'market.statistics','GetClientTypeAll':'clients.market',
            'GetClientType':'clients.latest','GetIndexB2History':'indices.history',
            'GetIndexB1LastDay':'indices.intraday','GetIndexCompany':'indices.members','GetInstEffect':'indices.impact'}
        if '/GetIndexB1LastAll/' in path:key='indices.list.'+path.rsplit('/',1)[1]
        elif '/GetClientTypeHistory/' in path:
            if len(path.split('/'))==6:
                day=int(path.rsplit('/',1)[1]);body=deepcopy(fixture['clients.history']['clientType'][-1]);body['recDate']=day
                return httpx.Response(200,json={'clientType':body})
            key='clients.history'
        else:
            for part in path.split('/'):
                if part in routes:key=routes[part];break
        if key:return httpx.Response(200,json=deepcopy(fixture[key]))
        return old.handle_request(request)
    return httpx.MockTransport(handler)


def sample_market_client(*,storage=False,data_dir=None,mode='auto',numeric='analysis',responses=None):
    """Create a market client with sample response fixtures.
    
    Args:
        storage (Any): Input for the sample_market_client operation.
        data_dir (Any): Input for the sample_market_client operation.
        mode (Any): Selected operating or fetching mode.
        numeric (Any): Numeric conversion or output representation setting.
        responses (Any): Input for the sample_market_client operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Notes:
        Uses demonstration fixtures; does not verify live exchange responses."""
    from ..client import Client
    from ..config import ClientConfig,NetworkConfig
    return Client(config=ClientConfig(numeric=numeric,network=NetworkConfig(requests_per_second=1_000_000,max_retries=0)),
        storage=storage,data_dir=data_dir,mode=mode,transport=market_transport(responses=responses),_namespace='sample')


def sample_market_async_client(*,storage=False,data_dir=None,mode='auto',numeric='analysis',responses=None):
    """Create an asynchronous market client with sample response fixtures.
    
    Args:
        storage (Any): Input for the sample_market_async_client operation.
        data_dir (Any): Input for the sample_market_async_client operation.
        mode (Any): Selected operating or fetching mode.
        numeric (Any): Numeric conversion or output representation setting.
        responses (Any): Input for the sample_market_async_client operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Notes:
        Uses demonstration fixtures; does not verify live exchange responses."""
    from ..async_client import AsyncClient
    from ..config import ClientConfig,NetworkConfig
    return AsyncClient(config=ClientConfig(numeric=numeric,network=NetworkConfig(requests_per_second=1_000_000,max_retries=0)),
        storage=storage,data_dir=data_dir,mode=mode,transport=market_transport(responses=responses),_namespace='sample')
