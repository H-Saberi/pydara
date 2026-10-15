from copy import deepcopy
from dataclasses import replace
from datetime import UTC,date,datetime,timedelta
from decimal import Decimal
import asyncio
import json
import sqlite3
import time

import httpx
import pandas as pd
import pytest

from pydara.tse import (Client, AsyncClient, ClientConfig, NetworkConfig, StorageConfig,
                           FetchPolicy,FreshnessPolicy,InstrumentRef,HistoryStore)
from pydara.tse.samples import sample_client,sample_async_client,sample_transport
from pydara.tse.providers.history import history_spec
from pydara.tse.transport import Packet
from pydara.tse.exceptions import *

FOLAD='\u0641\u0648\u0644\u0627\u062f'; CODE='46348559193224090'
FAST=ClientConfig(network=NetworkConfig(requests_per_second=1_000_000,max_retries=0))
FRESH=FetchPolicy(mode='online',freshness=FreshnessPolicy(max_age=timedelta(0)))

def payload():
    from importlib.resources import files
    return json.loads(files('pydara.tse.samples').joinpath('history_fixture.json').read_text())


def dynamic_transport(state):
    base=sample_transport()
    def handler(r):
        if 'GetClosingPriceDailyList/' in r.url.path:
            state.setdefault('requests',[]).append(r.url.path)
            result=deepcopy(state['body'])
            n=int(r.url.path.rsplit('/',1)[1])
            if n:
                result['closingPriceDaily']=sorted(result['closingPriceDaily'],key=lambda x:x['dEven'],reverse=True)[:n]
            return httpx.Response(200,json=result)
        return base.handle_request(r)
    return httpx.MockTransport(handler)


def test_auto_index_and_offline_query(tmp_path):
    with sample_client(storage=True,data_dir=tmp_path) as c:
        df=c.get_history(FOLAD);c.flush(timeout=10)
        stat=c.history_status().iloc[0]
        assert stat.rows==6 and stat.versions==6 and stat.batches==1
    with sample_client(storage=True,data_dir=tmp_path,mode='offline') as c:
        out=c.load_stored_history(FOLAD,include_jdate=True)
        assert c.request_count==0
        assert len(out)==6 and out.closing_price.tolist()==df.closing_price.tolist()
        assert all(out.from_cache) and all(out.is_stale)
        assert (out.available_at>=out.fetched_at).all()
        assert 'stored_history_not_live' in out.quality_flags.iloc[0]
        assert c.get_history_revisions(FOLAD).shape[0]==6


def test_identical_correction_and_reversion_preserve_observations(tmp_path):
    state={'body':payload()}
    with Client(config=FAST,data_dir=tmp_path,transport=dynamic_transport(state),_namespace='sample') as c:
        c.get_history(FOLAD,policy=FRESH);c.flush(timeout=10)
        t1=datetime.now(UTC)
        c.get_history(FOLAD,policy=FRESH);c.flush(timeout=10)
        assert c.history_status().iloc[0].versions==6
        state['body']['closingPriceDaily'][0]['pClosing']=Decimal('128').__int__()
        c.get_history(FOLAD,policy=FRESH);c.flush(timeout=10)
        t2=datetime.now(UTC)
        assert c.history_status().iloc[0].versions==7
        assert c.load_stored_history(FOLAD).closing_price.iloc[-1]==128
        assert c.load_stored_history(FOLAD,as_of=t1).closing_price.iloc[-1]==127
        state['body']=payload()
        c.get_history(FOLAD,policy=FRESH);c.flush(timeout=10)
        assert c.history_status().iloc[0].versions==7
        assert c.history_status().iloc[0].batches==4
        assert c.load_stored_history(FOLAD).closing_price.iloc[-1]==127
        assert c.load_stored_history(FOLAD,as_of=t2).closing_price.iloc[-1]==128
        with pytest.raises(PointInTimeUnavailableError):
            c.load_stored_history(InstrumentRef.by_ins_code(CODE),as_of=datetime(2020,1,1,tzinfo=UTC))
        with pytest.raises(InvalidArgumentError):c.load_stored_history(FOLAD,as_of=datetime(2020,1,1))


def test_identical_retrieval_keeps_first_observation(tmp_path):
    with sample_client(storage=True,data_dir=tmp_path) as c:
        c.get_history(FOLAD,policy=FRESH);c.flush(timeout=10)
        first=c.load_stored_history(FOLAD).first_observed_at.copy()
        c.get_history(FOLAD,policy=FRESH);c.flush(timeout=10)
        pd.testing.assert_series_equal(first,c.load_stored_history(FOLAD).first_observed_at)


def test_full_omission_not_deleted(tmp_path):
    state={'body':payload()}
    with Client(config=FAST,data_dir=tmp_path,transport=dynamic_transport(state),_namespace='sample') as c:
        c.get_history(FOLAD,policy=FRESH);c.flush(timeout=10)
        state['body']['closingPriceDaily'].pop(0)
        c.get_history(FOLAD,policy=FRESH);c.flush(timeout=10)
        result=c.load_stored_history(FOLAD)
        assert len(result)==6
        assert result.attrs['pydara']['last_full_snapshot_omissions']==1
        assert 'absent_from_last_full_snapshot_retained' in result.quality_flags.iloc[-1]


def test_sample_scope_isolated(tmp_path):
    with sample_client(storage=True,data_dir=tmp_path) as c:c.get_history(FOLAD);c.flush(timeout=10)
    other=HistoryStore(tmp_path/'pydara.sqlite3',namespace='public')
    assert other.status().empty
    with pytest.raises(OfflineDataUnavailableError):other.read(FOLAD)


def test_normalization_failure_does_not_fail_get_history(monkeypatch,tmp_path):
    import pydara.tse.storage.history_store as repo
    def fail(*a,**k):raise StorageError('mock normalized failure')
    monkeypatch.setattr(repo,'persist_packet',fail)
    with sample_client(storage=True,data_dir=tmp_path) as c:
        frame=c.get_history(FOLAD)
        assert len(frame)==6
        report=c.flush(timeout=10,raise_on_error=False)
        assert report.failed==1
        with sqlite3.connect(tmp_path/'pydara.sqlite3') as con:
            assert con.execute("SELECT count(*) FROM observations WHERE cache_key LIKE '%:history.daily:%'").fetchone()==(0,)
            assert con.execute('SELECT count(*) FROM dara_daily_latest').fetchone()==(0,)


def test_reindex_legacy_response_cache_idempotent(tmp_path):
    with sample_client(storage=True,data_dir=tmp_path) as c:c.get_history(FOLAD);c.flush(timeout=10)
    # Writer lease has been released. Wait for it to close before simulating a v0.2 database.
    time.sleep(.05)
    with sqlite3.connect(tmp_path/'pydara.sqlite3') as con:
        for name in ['dara_daily_latest','dara_daily_observations','dara_daily_versions','dara_history_batches','dara_history_meta']:
            con.execute('DROP TABLE '+name)
    with sample_client(storage=True,data_dir=tmp_path,mode='offline') as c:
        assert c.history_status().empty
        result=c.reindex_history()
        assert result['indexed_batches']==1 and result['network_requests']==0
        assert len(c.load_stored_history(FOLAD))==6
        assert c.reindex_history()['indexed_batches']==0
        assert len(c.get_history(FOLAD,policy=FetchPolicy(mode='offline',freshness=FreshnessPolicy(allow_stale=True))))==6


def recent_body():
    body=payload();base=deepcopy(body['closingPriceDaily'][0]);today=date.today()
    rows=[]
    for age in range(59,-1,-1):
        r=deepcopy(base);r['dEven']=int((today-timedelta(days=age)).strftime('%Y%m%d'));rows.append(r)
    return {'closingPriceDaily':rows}


def test_sync_full_then_tail_and_old_correction_requires_full(tmp_path):
    state={'body':recent_body()}
    with Client(config=FAST,data_dir=tmp_path,transport=dynamic_transport(state),_namespace='sample') as c:
        first=c.sync_history(FOLAD,timeout=10,on_storage_error='raise')
        assert first.summary['state']=='persisted' and first.plan.mode=='full'
        assert first.summary['inserted_rows']==60
        second=c.sync_history(FOLAD,timeout=10,on_storage_error='raise')
        assert second.plan.mode=='tail' and not second.summary['fallback_to_full']
        assert second.summary['inserted_rows']==0
        assert int(state['requests'][-1].rsplit('/',1)[1])<60
        # Correction outside tail is discovered by explicit full refresh, not guessed.
        state['body']['closingPriceDaily'][0]['pClosing']=120
        c.sync_history(FOLAD,timeout=10)
        assert c.load_stored_history(FOLAD).closing_price.iloc[0]==127
        full=c.sync_history(FOLAD,full=True,timeout=10)
        assert full.summary['revised_rows']==1
        assert c.load_stored_history(FOLAD).closing_price.iloc[0]==120


def test_short_tail_falls_back_to_full(tmp_path):
    state={'body':recent_body()}
    with Client(config=FAST,data_dir=tmp_path,transport=dynamic_transport(state),_namespace='sample') as c:
        c.sync_history(FOLAD,timeout=10)
        state['body']['closingPriceDaily']=state['body']['closingPriceDaily'][-2:]
        result=c.sync_history(FOLAD,timeout=10)
        assert result.summary['fallback_to_full']
        assert state['requests'][-1].endswith('/0')
        assert len(c.load_stored_history(FOLAD))==60


def test_sync_storage_disabled_preserves_fetched_data():
    with sample_client(storage=False) as c:
        r=c.sync_history(FOLAD)
        assert r.summary['state']=='disabled' and len(r.data)==6
        with pytest.raises(StorageError) as ex:c.sync_history(FOLAD,on_storage_error='raise')
        assert len(ex.value.report.data)==6


def test_async_sync_and_query(tmp_path):
    async def run():
        async with sample_async_client(storage=True,data_dir=tmp_path) as c:
            result=await c.sync_history(FOLAD,timeout=10)
            assert result.summary['state']=='persisted'
            assert len(await c.load_stored_history(FOLAD))==6
            assert len(await c.history_status())==1
            assert len(await c.get_history_revisions(FOLAD))==6
    asyncio.run(run())


def test_sync_offline_no_network(tmp_path):
    with sample_client(storage=True,data_dir=tmp_path) as c:c.sync_history(FOLAD,timeout=10)
    with sample_client(storage=True,data_dir=tmp_path,mode='offline') as c:
        result=c.sync_history(FOLAD)
        assert result.summary['network_requests']==0 and len(result.data)==6
        assert c.request_count==0


@pytest.mark.parametrize('kwargs',[{'overlap_days':0},{'overlap_days':True},{'full':1},{'wait':0},{'on_storage_error':'ignore'}])
def test_sync_validates_before_network(kwargs):
    with sample_client(storage=False) as c:
        with pytest.raises(InvalidArgumentError):c.sync_history(FOLAD,**kwargs)
        assert c.request_count==0


def test_normalized_schema_future_rejected(tmp_path):
    with sample_client(storage=True,data_dir=tmp_path) as c:c.get_history(FOLAD);c.flush(timeout=10)
    with sqlite3.connect(tmp_path/'pydara.sqlite3') as con:con.execute('UPDATE dara_history_meta SET version=999')
    with pytest.raises(StorageError,match='schema version'):HistoryStore(tmp_path/'pydara.sqlite3').status()


def test_exact_local_values_and_date_selection(tmp_path):
    state={'body':payload()};state['body']['closingPriceDaily'][0]['qTotCap']='9007199254740993'
    with Client(config=replace(FAST,numeric='exact'),data_dir=tmp_path,transport=dynamic_transport(state),_namespace='sample') as c:
        c.get_history(FOLAD);c.flush(timeout=10)
        frame=c.load_stored_history(FOLAD,calendar='jalali',start='1404-01-01',end='1404-01-01')
        assert len(frame)==1 and frame.turnover.iloc[0]==Decimal('9007199254740993')
        assert c.load_stored_history(FOLAD,start='2010-01-01',end='2010-01-02').empty


def test_periodic_full_plan():
    from types import SimpleNamespace
    from pydara.tse.sync import plan_for
    r=SimpleNamespace(ins_code=CODE,symbol=FOLAD)
    status=pd.DataFrame([{'ins_code':CODE,'last_date':date.today().isoformat(),
                         'last_full_fetch_at':(datetime.now(UTC)-timedelta(days=8)).isoformat()}])
    p=plan_for(r,status,full=False,overlap_days=14,full_refresh_days=7)
    assert p.mode=='full' and p.reason=='periodic_full_audit'


def test_out_of_order_packet_does_not_roll_back_latest(tmp_path):
    from pydara.tse.storage.history_store import persist_packet
    state={'body':payload()}
    with Client(config=FAST,data_dir=tmp_path,transport=dynamic_transport(state),_namespace='sample') as c:
        c.get_history(FOLAD,policy=FRESH);c.flush(timeout=10)
    body=payload();body['closingPriceDaily'][0]['pClosing']=1
    spec=history_spec(CODE);packet=Packet.create(spec,'sample',json.dumps(body).encode())
    packet=replace(packet,fetched_at=packet.fetched_at-timedelta(days=2))
    with sqlite3.connect(tmp_path/'pydara.sqlite3') as con:
        persist_packet(con,packet,datetime.now(UTC))
    repo=HistoryStore(tmp_path/'pydara.sqlite3',namespace='sample')
    assert repo.read(FOLAD).closing_price.iloc[-1]==127
    assert len(repo.revisions(FOLAD))==7


def test_dataframes_can_be_mutated_without_corrupting_index(tmp_path):
    with sample_client(storage=True,data_dir=tmp_path) as c:
        df=c.get_history(FOLAD)
        df.loc[0,'closing_price']=99999
        c.flush(timeout=10)
        assert c.load_stored_history(FOLAD).closing_price.iloc[0]==104
