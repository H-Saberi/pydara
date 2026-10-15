"""Explicit synthetic, network-free examples. Never silently replace live data."""
from copy import deepcopy
from importlib.resources import files
import json

import httpx


def sample_transport():
    """Create a deterministic sample-only transport without live market access.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        AssertionError: When the corresponding validation or operation fails.
    
    Notes:
        Uses demonstration fixtures; does not verify live exchange responses."""
    fixture = json.loads(files(__package__).joinpath("fixtures.json").read_text(encoding="utf-8"))
    def handler(request):
        """Perform the handler operation.
        
        Args:
            request (Any): Input for the handler operation.
        
        Returns:
            Implementation-defined result or generator output; see the calling API.
        
        Raises:
            AssertionError: When the corresponding validation or operation fails."""
        path = request.url.path
        if "GetInstrumentSearch/" in path:
            from ..providers.public import normalize_symbol
            query = normalize_symbol(path.rsplit("/", 1)[1])
            rows = [r for r in fixture["instruments"]
                    if query in normalize_symbol(r["lVal18AFC"]) or query in r["lVal30"]]
            return httpx.Response(200, json={"instrumentSearch": rows})
        if "GetClosingPriceDailyList/" in path:
            code = path.rsplit("/", 2)[1]
            found = any(r["insCode"] == code for r in fixture["instruments"])
            body = json.loads(files(__package__).joinpath("history_fixture.json").read_text(encoding="utf-8"))
            if not found:
                body = {"closingPriceDaily": []}
            return httpx.Response(200, json=body)
        code = path.rsplit("/", 1)[1]
        matches = [r for r in fixture["instruments"] if r["insCode"] == code]
        if "GetInstrumentInfo/" in path:
            return httpx.Response(200, json={"instrumentInfo": matches[0] if matches else None})
        if "GetClosingPriceInfo/" in path:
            q = deepcopy(fixture["quote"])
            q["insCode"] = code
            return httpx.Response(200, json={"closingPriceInfo": q if matches else None})
        raise AssertionError("An unreviewed endpoint was requested by the example.")
    return httpx.MockTransport(handler)


def sample_client(*, storage=False, data_dir=None, mode="auto"):
    """Return a regular Client with synthetic transport and a separate cache namespace."""
    from ..client import Client
    from ..config import ClientConfig, NetworkConfig
    return Client(config=ClientConfig(network=NetworkConfig(requests_per_second=1_000_000,
                  max_retries=0)), storage=storage, data_dir=data_dir, mode=mode,
                  transport=sample_transport(), _namespace="sample")


def sample_async_client(*, storage=False, data_dir=None, mode="auto"):
    """Create an asynchronous sample client for offline demonstrations.
    
    Args:
        storage (Any): Input for the sample_async_client operation.
        data_dir (Any): Input for the sample_async_client operation.
        mode (Any): Selected operating or fetching mode.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Notes:
        Uses demonstration fixtures; does not verify live exchange responses."""
    from ..async_client import AsyncClient
    from ..config import ClientConfig, NetworkConfig
    return AsyncClient(config=ClientConfig(network=NetworkConfig(requests_per_second=1_000_000,
                       max_retries=0)), storage=storage, data_dir=data_dir, mode=mode,
                       transport=sample_transport(), _namespace="sample")
