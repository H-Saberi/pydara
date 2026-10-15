import asyncio
from datetime import timedelta
from decimal import Decimal
import threading
import time

import httpx
import pandas as pd
import pytest

from pydara.tse import AsyncClient, ClientConfig, NetworkConfig, FetchPolicy, FreshnessPolicy
from pydara.tse.samples import sample_client, sample_async_client, sample_transport
from pydara.tse.exceptions import *
FOLAD="\u0641\u0648\u0644\u0627\u062f"


def test_sync_async_quote_equivalence():
    with sample_client() as c:
        q1=c.get_quote(FOLAD)
    async def run():
        async with sample_async_client() as c:
            q2=await c.get_quote(FOLAD)
            assert q1.last_price==q2.last_price
            assert q1.instrument.ins_code==q2.instrument.ins_code
            assert q1.source_timestamp==q2.source_timestamp
            assert q1.meta.quality_flags==q2.meta.quality_flags
            assert list(q1.to_frame().dtypes.astype(str))==list(q2.to_frame().dtypes.astype(str))
    asyncio.run(run())


def test_sync_works_inside_running_event_loop():
    async def run():
        with sample_client() as c:
            assert c.get_price(FOLAD)==Decimal('1234.5')
    asyncio.run(run())


def test_async_batch_preserves_order_and_failure():
    async def run():
        async with sample_async_client() as c:
            df=await c.get_quotes([FOLAD,'NO',FOLAD],on_error='collect')
            assert df.status.tolist()==['ok','error','ok']
    asyncio.run(run())


def test_async_offline_round_trip(tmp_path):
    async def run():
        async with sample_async_client(storage=True,data_dir=tmp_path) as c:
            q=await c.get_quote(FOLAD)
            assert (await c.flush()).complete
        async with sample_async_client(storage=True,data_dir=tmp_path,mode='offline') as c:
            p=FetchPolicy(freshness=FreshnessPolicy(allow_stale=True))
            actual=await c.get_quote(FOLAD,policy=p)
            assert q.last_price==actual.last_price
            assert c.request_count==0
    asyncio.run(run())


def test_async_disk_wait_does_not_stop_heartbeat(tmp_path,monkeypatch):
    async def run():
        ticks=[]
        async with sample_async_client(storage=True,data_dir=tmp_path,mode='offline') as c:
            def slow(key):time.sleep(.15);return None
            monkeypatch.setattr(c._core.store,'read',slow)
            async def heartbeat():
                for _ in range(10):ticks.append(1);await asyncio.sleep(.01)
            task=asyncio.create_task(heartbeat())
            with pytest.raises(OfflineDataUnavailableError):
                await c.get_quote(FOLAD)
            await task
            assert len(ticks)==10
    asyncio.run(run())


def test_async_cancellation_is_not_swallowed():
    async def handler(request):
        await asyncio.sleep(10)
        return httpx.Response(200,json={})
    async def run():
        config=ClientConfig(network=NetworkConfig(requests_per_second=1_000_000))
        async with AsyncClient(config=config,storage=False,transport=httpx.MockTransport(handler)) as c:
            task=asyncio.create_task(c.get_quote(FOLAD))
            await asyncio.sleep(.03);task.cancel()
            with pytest.raises(asyncio.CancelledError):await task
            assert c.request_count==1
    asyncio.run(run())


def test_async_deadline():
    async def handler(request):await asyncio.sleep(.2);return httpx.Response(200,json={})
    async def run():
        config=ClientConfig(network=NetworkConfig(requests_per_second=1_000_000,operation_timeout=.02))
        async with AsyncClient(config=config,storage=False,transport=httpx.MockTransport(handler)) as c:
            with pytest.raises(OperationTimeoutError):await c.get_quote(FOLAD)
    asyncio.run(run())


def test_independent_async_requests_respect_bound():
    active=[0,0];base=sample_transport()
    async def handler(request):
        active[0]+=1;active[1]=max(active[1],active[0])
        try:await asyncio.sleep(.005);return base.handle_request(request)
        finally:active[0]-=1
    async def run():
        config=ClientConfig(network=NetworkConfig(max_concurrency=2,requests_per_second=1_000_000,max_retries=0))
        async with AsyncClient(config=config,storage=False,transport=httpx.MockTransport(handler)) as c:
            values=await asyncio.gather(*(c.get_price(FOLAD) for _ in range(5)))
            assert values==[Decimal('1234.5')]*5
            assert active[1]<=2
    asyncio.run(run())
