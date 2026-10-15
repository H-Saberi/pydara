"""Original synthetic shapes for extension tests. Not observations of live markets."""
from copy import deepcopy
from importlib.resources import files
import json
import re
import httpx


def extended_transport(*, responses=None):
    """Perform the extended transport operation.
    
    Args:
        responses (Any): Input for the extended_transport operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    from .market import market_transport
    from ..providers.extended import ENDPOINTS
    fixtures=json.loads(files(__package__).joinpath('extended_fixture.json').read_text(encoding='utf8'))
    if responses:fixtures.update(deepcopy(responses))
    old=market_transport()
    def handler(request):
        """Perform the handler operation.
        
        Args:
            request (Any): Input for the handler operation.
        
        Returns:
            Implementation-defined result or generator output; see the calling API."""
        url=str(request.url);path=request.url.path
        for name,(template,root,age,schema) in ENDPOINTS.items():
            if name=='extra.nav':continue
            target=url if template.startswith('https:') else path.removeprefix('/api/')
            pattern=re.escape(template)
            pattern=re.sub(r'\\\{[^}]+\\\}',r'[^/?&]+',pattern)
            if re.fullmatch(pattern,target):
                body=deepcopy(fixtures[name])
                if root=='__text__':return httpx.Response(200,text=body)
                return httpx.Response(200,json=body)
        return old.handle_request(request)
    return httpx.MockTransport(handler)


def sample_extended_client(*,storage=False,data_dir=None,mode='auto',numeric='analysis',responses=None):
    """Create an extended-data client with synthetic fixtures.
    
    Args:
        storage (Any): Input for the sample_extended_client operation.
        data_dir (Any): Input for the sample_extended_client operation.
        mode (Any): Selected operating or fetching mode.
        numeric (Any): Numeric conversion or output representation setting.
        responses (Any): Input for the sample_extended_client operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Notes:
        Uses demonstration fixtures; does not verify live exchange responses."""
    from ..client import Client
    from ..config import ClientConfig,NetworkConfig
    return Client(config=ClientConfig(numeric=numeric,network=NetworkConfig(requests_per_second=1_000_000,max_retries=0,request_budget=1000)),storage=storage,data_dir=data_dir,mode=mode,transport=extended_transport(responses=responses),_namespace='sample')


def sample_extended_async_client(*,storage=False,data_dir=None,mode='auto',numeric='analysis',responses=None):
    """Create an asynchronous extended-data client with synthetic fixtures.
    
    Args:
        storage (Any): Input for the sample_extended_async_client operation.
        data_dir (Any): Input for the sample_extended_async_client operation.
        mode (Any): Selected operating or fetching mode.
        numeric (Any): Numeric conversion or output representation setting.
        responses (Any): Input for the sample_extended_async_client operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Notes:
        Uses demonstration fixtures; does not verify live exchange responses."""
    from ..async_client import AsyncClient
    from ..config import ClientConfig,NetworkConfig
    return AsyncClient(config=ClientConfig(numeric=numeric,network=NetworkConfig(requests_per_second=1_000_000,max_retries=0,request_budget=1000)),storage=storage,data_dir=data_dir,mode=mode,transport=extended_transport(responses=responses),_namespace='sample')
