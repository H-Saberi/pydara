"""Source-shaped synthetic regression tests, never a certification of live endpoints."""
import asyncio
from copy import deepcopy
from datetime import UTC,datetime,timedelta
from decimal import Decimal
import inspect
import json
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest

from pydara import tse as data
from pydara.tse._core.exceptions import (PyDaraError, DataQualityError, SchemaMismatchError,
    InvalidArgumentError, UnsupportedCapabilityError, AmbiguousInstrumentError,
    UnknownInstrumentError, StaleDataError, CoverageError, BatchDataError, ApiError,
    PointInTimeUnavailableError, StaleDataWarning)
from pydara.tse import Client,AsyncClient,ClientConfig,NetworkConfig,FetchPolicy,FreshnessPolicy,Market
from pydara.tse.samples.market import (fixtures,market_transport,sample_market_client,
    sample_market_async_client,legacy_fixture)
from pydara.tse.providers.market import request_spec,parse_market_payload
from pydara.tse.transport import Packet
from pydara.tse.market_schemas import SCHEMAS

FOLAD='\u0641\u0648\u0644\u0627\u062f'; CODE='46348559193224090'; INDEX='32097828799138957'
FAST=ClientConfig(network=NetworkConfig(requests_per_second=1_000_000,max_retries=0))
CALLS=[
 ('get_market_watch',(),{}),('get_market_order_book',(),{}),('get_market_overview',(),{}),
 ('get_market_map',(),{}),('get_sectors',(),{}),('get_sector_instruments',('27',),{}),
 ('get_key_statistics',(),{}),('_get_client_types',(FOLAD,),{}),
 ('_get_client_types',(FOLAD,),{'day':'2026-01-10'}),('_get_client_type_history',(FOLAD,),{}),
 ('get_market_client_types',(),{}),('get_indices',(),{}),('get_indices',(),{'market':None}),
 ('search_indices',('\u06a9\u0644',),{}),('get_index',(INDEX,),{}),
 ('get_index_history',(INDEX,),{}),('get_index_intraday',(INDEX,),{}),
 ('get_index_members',(INDEX,),{}),('get_index_impact',(),{}),
]

@pytest.mark.parametrize('method,args,kwargs',CALLS)
def test_all_frames_and_types(method,args,kwargs):
    with sample_market_client() as c:f=getattr(c,method)(*args,**kwargs)
    assert isinstance(f,pd.DataFrame)
    assert isinstance(f.index,pd.RangeIndex)
    assert f.attrs['pydara']['synthetic']
    assert f.attrs['pydara']['coverage_status']=='unknown'
    assert f.attrs['pydara']['schema_id'] in SCHEMAS
    assert str(f['fetched_at'].dtype)=='datetime64[ns, UTC]'
    for key in ('ins_code','index_code'):
        if key in f:assert str(f[key].dtype)=='string'
    report=data.validate_data(f,schema=f.attrs['pydara']['schema_id'])
    assert report.loc[report.severity=='error'].empty, report.to_dict('records')

@pytest.mark.parametrize('method,args,kwargs',CALLS)
def test_sync_async_parity(method,args,kwargs):
    async def go():
        async with sample_market_async_client() as c:return await getattr(c,method)(*args,**kwargs)
    with sample_market_client() as c:a=getattr(c,method)(*args,**kwargs)
    b=asyncio.run(go())
    assert a.columns.tolist()==b.columns.tolist()
    assert a.dtypes.equals(b.dtypes)
    ignore=('observation_id','fetched_at','first_observed_at','available_at','storage_receipt_id')
    cols=[x for x in a if x not in ignore]
    pd.testing.assert_frame_equal(a[cols],b[cols])

@pytest.mark.parametrize('method,args,kwargs',CALLS)
def test_cache_offline_no_network(tmp_path,method,args,kwargs):
    with sample_market_client(storage=True,data_dir=tmp_path) as c:
        online=getattr(c,method)(*args,**kwargs);c.flush(timeout=10)
    def forbidden(r):raise AssertionError('offline made HTTP')
    with Client(config=FAST,storage=True,data_dir=tmp_path,mode='offline',transport=httpx.MockTransport(forbidden),_namespace='sample') as c:
        with pytest.warns(StaleDataWarning):
            cached=getattr(c,method)(*args,**kwargs,policy=FetchPolicy(mode='offline',freshness=FreshnessPolicy(max_age=timedelta(0),allow_stale=True,max_stale=timedelta(days=2))))
        assert c.request_count==0
        assert len(cached)==len(online)
        assert cached.attrs['pydara']['from_cache']

# Some endpoints retain fresh positive-TTL cache and correctly emit no stale warning.
# Above test intentionally expires all entries in the explicit policy below.

@pytest.mark.parametrize('sample',['market_watch_v1','client_types_v1','index_history_v1','indices_v1'])
def test_samples(sample):
    df=data.load_sample(sample);other=data.load_sample(sample)
    assert df.attrs['pydara']['sample_name']==sample
    df.iloc[0,0]='CHANGED'
    assert other.iloc[0,0]!='CHANGED'
    assert not data.select_columns(other).empty

@pytest.mark.parametrize('schema',list(SCHEMAS))
def test_empty_schemas(schema):
    from pydara.tse.market_schemas import empty_market_frame
    f=empty_market_frame(schema)
    assert f.empty and f.columns.is_unique
    assert not data.schema_info(schema).empty
    f2=empty_market_frame(schema,numeric='exact')
    for c in SCHEMAS[schema].numbers:assert f2[c].dtype==object


def test_signed_statistics_and_missing_values():
    with sample_market_client() as c:
        f=c.get_market_watch();i=c.get_indices();ct=c._get_client_types(FOLAD)
    assert f.eps.iloc[0]<0 and pd.isna(f.pe.iloc[0])
    assert i.change.iloc[0]<0
    assert ct['date'].isna().all() and ct.individual_buy_value.isna().all()
    assert ct.individual_buy_count.iloc[0]==250
    assert 'client_value_not_reported' in ct.quality_flags.iloc[0]


def test_optional_components_no_cartesian_product():
    with sample_market_client() as c:
        df=c.get_market_watch(include_order_book=True,include_client_types=True)
    assert len(df)==2 and not df.ins_code.duplicated().any()
    assert df.loc[0,'bid_price_1']==1510
    assert pd.isna(df.loc[0,'bid_price_5'])
    assert pd.isna(df.loc[1,'individual_buy_volume'])
    assert df.client_type_source_timestamp.isna().all()
    assert df.order_book_source_timestamp.isna().all()
    assert df.client_type_date.isna().all()
    assert not df.attrs['pydara']['components_are_simultaneous']
    assert 'client_types_not_returned' in df.loc[1,'quality_flags']


def test_legacy_backend_no_invented_trade_date():
    with sample_market_client() as c:
        df=c.get_market_watch(backend='legacy',include_order_book=True,market=Market.TSE)
    assert len(df)==1 and df['date'].isna().all()
    assert df.last_price.iloc[0]==1510.5
    assert df.bid_price_1.iloc[0]==1510


def test_auto_empty_fallback_and_preserved_evidence():
    with sample_market_client(responses={'market.watch':{'marketwatch':[]}}) as c:
        df=c.get_market_watch()
    assert df.empty
    assert df.attrs['pydara']['fallback_reason']=='empty_json_response'
    assert df.attrs['pydara']['backend']=='legacy'
    assert len(df.attrs['pydara']['attempted_components'])==1


def test_no_fallback_on_http_permission_error():
    count=[]
    def handler(r):count.append(r.url);return httpx.Response(403,json={'error':'denied'})
    with Client(config=FAST,storage=False,transport=httpx.MockTransport(handler)) as c:
        with pytest.raises(ApiError):c.get_market_watch()
    assert len(count)==1

@pytest.mark.parametrize('method,args,kwargs',[
 ('get_market_watch',(),{'backend':'invalid'}),('get_market_watch',(),{'market':'nonsense'}),
 ('get_market_watch',(),{'include_order_book':1}),('get_market_watch',(),{'show_traded':'yes'}),
 ('get_market_overview',(),{'market':Market.BASE}),('get_indices',(),{'market':Market.ENERGY}),
 ('get_index_history',(float(INDEX),),{}),('get_index_history',(True,),{}),
 ('get_index_history',(INDEX,),{'start':'2026-02-01','end':'2026-01-01'}),
 ('get_index_intraday',(INDEX,),{'day':'2025-01-01'}),('get_index_members',(INDEX,),{'as_of':'2025-01-01'}),
 ('get_sector_instruments',('../secrets',),{}),('get_market_map',(),{'limit':0}),
 ('_get_client_type_history',(FOLAD,),{'calendar':'guess'}),('_get_client_types',(FOLAD,),{'day':'1405/01/01'}),
 ('get_index_impact',(),{'limit':True}),
])
def test_invalid_inputs_before_http(method,args,kwargs):
    with sample_market_client() as c:
        with pytest.raises(PyDaraError):getattr(c,method)(*args,**kwargs)
        assert c.request_count==0


def test_market_filter_does_not_guess_missing_flow():
    f=fixtures();body=deepcopy(f['market.watch']);[r.pop('flow') for r in body['marketwatch']]
    with sample_market_client(responses={'market.watch':body}) as c:
        out = c.get_market_watch(market=Market.TSE)
    # A matching server selector supplies the missing source market label.
    assert set(out['market']) == {'TSE'}
    assert out.attrs['pydara']['market_labels_from_server_selector'] == len(out)


def test_market_client_filter_uses_separate_watch():
    with sample_market_client() as c:
        df=c.get_market_client_types(market='tse')
    assert len(df)==1 and df.symbol.iloc[0]==FOLAD
    assert df['date'].isna().all()
    assert df.attrs['pydara']['filtered_by_current_watch']


def test_date_filter_jalali_and_sorted():
    with sample_market_client() as c:
        f=c._get_client_type_history(FOLAD,start='1404-10-20',end='1404-10-20',calendar='jalali',include_jdate=True)
        i=c.get_index_history(INDEX,start='2026-01-10',end='2026-01-10',include_jdate=True)
    assert len(f)==len(i)==1
    assert f.jdate.iloc[0]=='1404-10-20'
    assert f['date'].iloc[0]==i['date'].iloc[0]


def test_placeholder_only_for_bound_routes():
    f=fixtures();b=deepcopy(f['clients.market']);b['clientTypeAllDto'][0]['insCode']='0'
    with sample_market_client(responses={'clients.market':b}) as c:
        with pytest.raises(SchemaMismatchError):c.get_market_client_types()
    with sample_market_client() as c:
        df=c._get_client_type_history(FOLAD)
        assert set(df.ins_code)=={CODE}
        assert 'response_identifier_missing_or_zero' in df.quality_flags.iloc[0]

@pytest.mark.parametrize('ep,params,root',[
 ('indices.history',{'code':INDEX},'indexB2'),('clients.history',{'code':CODE},'clientType')])
def test_conflicting_identifier_rejected(ep,params,root):
    f=fixtures();body=deepcopy(f[ep]);body[root][0]['insCode']='999'
    spec=request_spec(ep,**params)
    p=Packet.create(spec,'sample',json.dumps(body).encode())
    with pytest.raises(DataQualityError):parse_market_payload(p,spec)


def test_duplicate_rows_identical_or_conflicting():
    f=fixtures();body=deepcopy(f['indices.history']);body['indexB2']+=[deepcopy(body['indexB2'][0])]
    with sample_market_client(responses={'indices.history':body}) as c:
        df=c.get_index_history(INDEX)
    assert len(df)==2 and df.attrs['pydara']['identical_duplicates_removed']==1
    body['indexB2'][-1]['xNivInuClMresIbs']+=1
    with sample_market_client(responses={'indices.history':body}) as c:
        with pytest.raises(DataQualityError):c.get_index_history(INDEX)


def test_intraday_equal_times_preserved():
    with sample_market_client() as c:df=c.get_index_intraday(INDEX)
    assert len(df)==3
    assert df.source_timestamp.is_monotonic_increasing
    assert df.source_position.tolist()==[1,2,0]


def test_index_name_ambiguity_and_no_guess():
    f=fixtures();body=deepcopy(f['indices.list.1']);body['indexB1'][1]['lVal30']=body['indexB1'][0]['lVal30']
    with sample_market_client(responses={'indices.list.1':body}) as c:
        with pytest.raises(AmbiguousInstrumentError) as err:c.get_index('\u0634\u0627\u062e\u0635 \u06a9\u0644')
        assert len(err.value.candidates)==2
        assert len(c.get_index(INDEX))==1
        with pytest.raises(UnknownInstrumentError):c.get_index('999999')


def test_exact_profile_and_exports(tmp_path):
    with sample_market_client(numeric='exact') as c:f=c.get_indices(market=None)
    assert isinstance(f.value.iloc[0],Decimal)
    for ext in ('csv','xlsx','sqlite'):
        p=tmp_path/('indices.'+ext);data.save(f,p);g=data.load(p)
        pd.testing.assert_frame_equal(f,g)

@pytest.mark.parametrize('kind', ['client','index'])
def test_batches_preserve_duplicates_and_errors(kind):
    with sample_market_client() as c:
        if kind=='client':b=c._get_client_type_history_many(pd.Series([FOLAD,'bad',FOLAD]),on_error='collect')
        else:b=c.get_index_history_many(np.array([INDEX,'bad',INDEX]),on_error='collect')
    assert len(b.requests)==3 and len(b.errors)==1
    assert set(b.data.request_index)=={0,2}
    assert b.requests.row_count.tolist()==[2,0,2]
    assert not b.manifest.get('complete',False)


def test_batch_fail_fast_has_report():
    with sample_market_client() as c:
        with pytest.raises(BatchDataError) as err:c.get_index_history_many([INDEX,'not-there'])
    assert len(err.value.partial_result.requests)==2


def test_read_only_storage_does_not_lose_valid_data(tmp_path):
    target=tmp_path/'not_a_directory';target.write_text('file')
    with sample_market_client(storage=True,data_dir=target) as c:
        f=c.get_indices()
        report=c.flush(timeout=5,raise_on_error=False)
        assert not f.empty and report.failed>0


def test_watching_is_lazy_bounded_and_fresh(monkeypatch):
    from pydara.tse import market_client
    sleeps=[];monkeypatch.setattr(market_client.time,'sleep',lambda s:sleeps.append(s))
    with sample_market_client() as c:
        it=c.watch_market(max_updates=2,interval=1)
        assert c.request_count==0
        out=list(it)
        assert c.request_count==2
    assert [f.attrs['pydara']['poll_index'] for f in out]==[0,1]
    assert 1 in sleeps


def test_async_watching_can_close():
    async def go():
        async with sample_market_async_client() as c:
            it=c.watch_market(max_updates=None,interval=1)
            f=await anext(it);await it.aclose()
            assert not f.empty and c.request_count==1
    asyncio.run(go())


def test_coverage_and_freshness_policies():
    with sample_market_client() as c:
        with pytest.raises(CoverageError):c.get_indices(policy=FetchPolicy(coverage='raise'))
        with pytest.raises(StaleDataError):c._get_client_types(FOLAD,policy=FetchPolicy(freshness=FreshnessPolicy(max_source_age=timedelta(days=100))))


def test_unknown_raw_fields_preserved_and_impact_not_fabricated():
    f=fixtures();b=deepcopy(f['indices.impact']);b['instEffect'][0]['newField']='abc'
    with sample_market_client(responses={'indices.impact':b}) as c:df=c.get_index_impact()
    raw=json.loads(df.source_fields.iloc[0]);assert raw['newField']=='abc' and Decimal(raw['instEffect'])==Decimal('-123.5')
    assert df.impact_points.isna().all()
    assert df.attrs['pydara']['mapping_status']=='experimental_source_fields_only'


def test_empty_endpoint_shapes():
    with sample_market_client(responses={'clients.history':{'clientType':[]},'indices.history':{'indexB2':[]},'market.watch':{'marketwatch':[]}}) as c:
        a=c._get_client_type_history(FOLAD);b=c.get_index_history(INDEX);d=c.get_market_watch(backend='json')
    assert a.empty and b.empty and d.empty
    assert str(a.individual_buy_count.dtype)=='Int64'
    assert str(b.value.dtype)=='Float64'
    assert str(d.ins_code.dtype)=='string'


def test_normalization_signed_and_exact():
    f=pd.DataFrame({'index_code':[INDEX],'date':['2026-01-10'],'value':['1000.25'],'change':['-0.5']})
    o=data.normalize_data(f,schema='indices',numeric='exact')
    assert o.change.iloc[0]==Decimal('-0.5') and o.value.iloc[0]==Decimal('1000.25')
    assert f.change.iloc[0]=='-0.5'

@pytest.mark.parametrize('key,bad',[
 ('market.watch',{'marketwatch':None}),
 ('clients.market',{'clientTypeAllDto':{'unexpected':'object'}}),
 ('clients.history',{'clientType':[{'recDate':20260110}]}),
 ('indices.list.1',{'indexB1':[{'insCode':'0','xDrNivJIdx004':200}]}),
 ('indices.history',{'indexB2':[{'dEven':20260110,'insCode':None}]}),
])
def test_malformed_source_not_hidden(key,bad):
    methods={'market.watch':('get_market_watch',()),'clients.market':('get_market_client_types',()),
             'clients.history':('_get_client_type_history',(FOLAD,)),
             'indices.list.1':('get_indices',()),'indices.history':('get_index_history',(INDEX,))}
    method,args=methods[key]
    with sample_market_client(responses={key:bad}) as c:
        with pytest.raises(PyDaraError):getattr(c,method)(*args)


def test_index_identifier_validator_rejects_float_and_zero():
    f=data.load_sample('index_history_v1');f['index_code']=[0.0]*len(f)
    issues=data.validate_data(f,schema='index_history')
    assert 'identifier_not_exact_text' in set(issues.rule)
    with pytest.raises(InvalidArgumentError):data.normalize_data(f,schema='index_history')


def test_missing_participant_value_not_imputed_and_zero_count_preserved():
    fixture=fixtures();row=deepcopy(fixture['clients.latest']['clientType']);row['buy_CountI']=0
    with sample_market_client(responses={'clients.latest':{'clientType':row}}) as c:df=c._get_client_types(FOLAD)
    assert df.individual_buy_count.iloc[0]==0 and df.individual_buy_value.isna().all()


def test_composite_source_age_cannot_hide_unknown_component_time():
    from pydara.tse.market_schemas import finish_market
    with sample_market_client() as c:f=c.get_market_watch(include_client_types=True)
    f['source_timestamp']=pd.Timestamp.now(tz='UTC')
    policy=FetchPolicy(freshness=FreshnessPolicy(max_source_age=timedelta(days=1)))
    with pytest.raises(StaleDataError):finish_market(f,policy)


def test_bad_batch_policy_raises_once_before_network():
    from pydara.tse._core.exceptions import ConfigurationError
    with sample_market_client() as c:
        with pytest.raises(ConfigurationError):c._get_client_types_many([FOLAD],on_error='collect',policy='nonsense')
        assert c.request_count==0


def test_aliases_and_integer_index_and_name_resolution():
    with sample_market_client() as c:
        a=c.get_index(int(INDEX),market='tse')
        b=c.get_index('\u0634\u0627\u062e\u0635 \u06a9\u0644',market=Market.TSE)
        assert a.index_code.iloc[0]==b.index_code.iloc[0]==INDEX


def test_lazy_async_generator_has_no_network_before_first_item():
    async def go():
        async with sample_market_async_client() as c:
            it=c.watch_market(max_updates=1);assert c.request_count==0
            f=await anext(it);assert len(f)>0 and c.request_count>0
            with pytest.raises(StopAsyncIteration):await anext(it)
    asyncio.run(go())


def test_sync_poll_does_not_escape_offline_client():
    with sample_market_client(mode='offline') as c:
        with pytest.raises(InvalidArgumentError):next(c.watch_market(max_updates=1))
        assert c.request_count==0


def test_async_poll_does_not_escape_offline_client():
    async def go():
        async with sample_market_async_client(mode='offline') as c:
            with pytest.raises(InvalidArgumentError):await anext(c.watch_market(max_updates=1))
            assert c.request_count==0
    asyncio.run(go())
