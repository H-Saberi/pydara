"""Regression tests for new adapters, shared workflows and safe conveniences."""
from __future__ import annotations
import asyncio
from decimal import Decimal
from pathlib import Path
import json
import sqlite3
from unittest.mock import patch
import pandas as pd
import pytest

from pydara import tse as data
from pydara.tse import FetchPolicy
from pydara.tse.samples.extended import sample_extended_client, sample_extended_async_client
from pydara.tse._core.exceptions import PyDaraError, DataQualityError, InvalidArgumentError, UnsupportedCapabilityError, StorageError

S='\u0641\u0648\u0644\u0627\u062f'
DATE='2025-03-18'
CALLS=[
 ('get_trades',(S,),{}),('get_trades',(S,),{'day':DATE}),
 ('get_order_book',(S,),{}),('get_order_book_history',(S,),{'start':DATE}),
 ('get_order_book_updates',(S,),{'start':DATE}),
 ('get_instrument_states',(S,),{'day':DATE}),('get_thresholds',(S,),{'day':DATE}),
 ('get_shareholders',(S,),{}),('get_shareholder_history',(S,123),{}),
 ('get_share_capital_history',(S,),{}),('get_adjustments',(S,),{}),
 ('get_adjusted_history',(S,),{}),('get_history',(S,),{'adjustment':'source'}),
 ('get_dividends',(S,),{}),('get_messages',(S,),{}),('get_disclosures',(S,),{}),
 ('get_boards',(),{}),('get_instruments',(),{}),('get_funds',(),{}),
 ('get_fund',('7001',),{}),('get_fund_nav_history',('7001',),{}),
 ('get_options',(),{}),('get_options',(S,),{}),('get_futures',(),{}),
]

@pytest.mark.parametrize('method,args,kwargs',CALLS)
def test_new_family_returns_frame(method,args,kwargs):
    with sample_extended_client() as client:
        frame=getattr(client,method)(*args,**kwargs)
    assert isinstance(frame,pd.DataFrame)
    assert not frame.empty
    assert frame.attrs['pydara']['coverage_status']=='unknown'
    if 'ins_code' in frame:assert str(frame['ins_code'].dtype)=='string'
    assert 'source_fields' in frame or method=='get_instruments'

@pytest.mark.parametrize('method,args,kwargs',CALLS)
def test_async_same_schema_values(method,args,kwargs):
    with sample_extended_client() as client:a=getattr(client,method)(*args,**kwargs)
    async def run():
        async with sample_extended_async_client() as client:return await getattr(client,method)(*args,**kwargs)
    b=asyncio.run(run())
    assert list(a)==list(b)
    assert a.dtypes.astype(str).tolist()==b.dtypes.astype(str).tolist()
    exclude={'fetched_at','first_observed_at','available_at','identity_fetched_at','request_id','observation_id','row_id','storage_receipt_id'}
    cols=[c for c in a if c not in exclude]
    pd.testing.assert_frame_equal(a[cols],b[cols])

@pytest.mark.parametrize('method,args,kwargs',CALLS[:16])
def test_new_data_stores_and_reads_offline(tmp_path,method,args,kwargs):
    with sample_extended_client(storage=True,data_dir=tmp_path) as client:
        expected=getattr(client,method)(*args,**kwargs)
        client.flush(timeout=10)
    with sample_extended_client(storage=True,data_dir=tmp_path,mode='offline') as client:
        with patch.object(client._wire,'request',side_effect=AssertionError('network')):
            frame=getattr(client,method)(*args,**kwargs,policy=FetchPolicy.offline(allow_stale=True))
    assert len(frame)==len(expected)
    assert frame['from_cache'].all()

@pytest.mark.parametrize('method,args,kwargs',[
    ('get_trades',(S,),{'start':'2025-01-01','end':'2025-06-01'}),
    ('get_trades',(S,),{'day':DATE,'start':DATE}),
    ('get_trades',(S,),{'cancellation':'exclude_verified'}),
    ('get_shareholder_history',(S,-1),{}),
    ('get_disclosures',(S,),{'limit':0}),
    ('get_funds',(),{'category':'nonsense'}),
    ('get_options',(True,),{}),
    ('get_instruments',(),{'include_inactive':True}),
    ('get_futures',(),{'source':'public'}),
])
def test_reject_invalid_before_network(method,args,kwargs):
    with sample_extended_client() as client:
        with pytest.raises(PyDaraError):getattr(client,method)(*args,**kwargs)
        assert client.request_count==0


def test_trades_same_second_retained():
    with sample_extended_client() as client:f=client.get_trades(S,day=DATE)
    assert len(f)==2
    assert f['source_timestamp'].nunique()==1
    assert f.trade_id.tolist()==['11','12']
    assert set(f.cancellation_state)=={'unknown'}


def test_adjusted_does_not_modify_raw():
    with sample_extended_client() as client:
        raw=client.get_history(S)
        adjusted=client.get_history(S,adjustment='source')
        raw_again=client.get_history(S)
    pd.testing.assert_frame_equal(raw.drop(columns=['from_cache']),raw_again.drop(columns=['from_cache']))
    assert adjusted.adjustment.eq('source').all()
    assert adjusted.attrs['pydara']['anchor_date']=='2025-03-18'
    assert adjusted.attrs['pydara']['point_in_time'] is False
    assert adjusted.attrs['pydara']['raw_prices_overwritten'] is False


def test_options_two_sides_and_no_fake_units():
    with sample_extended_client() as client:f=client.get_options(S)
    assert set(f.option_type)=={'call','put'}
    assert f.currency.isna().all()
    assert f.open_interest.isna().all()


def test_auto_calendar_scoped_to_simple_alias():
    with sample_extended_client() as client:
        a=client.history(S,start='1403/12/27',end='1403/12/28')
        b=client.history(S,start='2025-03-17',end='2025-03-18')
    assert a.date.tolist()==b.date.tolist()
    with pytest.raises(InvalidArgumentError):__import__('pydara.tse.friendly',fromlist=['friendly_range']).friendly_range('1600-01-01',None)


def test_simple_helpers():
    f=data.load_sample();original=f.copy(deep=True)
    selected=data.select(f,columns=['date','ins_code','closing_price'])
    assert list(selected)==['date','ins_code','closing_price']
    indexed=data.set_date_index(f)
    assert isinstance(indexed.index,pd.DatetimeIndex)
    both=data.concat([f,f])
    assert len(both)==2*len(f)
    pd.testing.assert_frame_equal(f,original)
    assert data.compare_sources(f,f).empty
    other=f.copy();other.loc[0,'closing_price']+=1
    assert len(data.compare_sources(f,other))==1
    pd.testing.assert_frame_equal(data.to_pandas(f),f)


def test_coverage_explicit_sessions_only():
    f=data.load_sample();expected=pd.date_range(f.date.min(),f.date.max())
    unknown=data.coverage(f)
    assert unknown.coverage_status.eq('unknown').all()
    assert data.coverage(f,expected_sessions=f.date).missing_expected_sessions.eq(0).all()
    assert len(data.missing_sessions(f,expected_sessions=expected))==len(expected)-f.date.nunique()
    assert data.coverage(f,expected_sessions=expected,start=f.date.min().date(),end=f.date.min().date()).missing_expected_sessions.eq(0).all()


def test_download_resume_and_safe_export(tmp_path):
    with sample_extended_client(storage=True,data_dir=tmp_path/'db') as c:
        a=c.download([S,S],update=False,checkpoint_dir=tmp_path/'jobs')
        sent=c.request_count
        b=c.download([S,S],update=False,checkpoint_dir=tmp_path/'jobs')
        assert b.requests.resumed.all()
        assert c.request_count==sent
        assert len(a.data)==len(b.data)
        assert b.requests.request_index.tolist()==[0,1]
        exports=data.export_many(b,tmp_path/'out',formats=['csv','sqlite'],overwrite=True)
        assert exports.state.eq('persisted').all()
        c.flush(timeout=10)
        assert not c.datasets().empty
        assert c.backup(tmp_path/'backup.sqlite')['state']=='persisted'
        with sqlite3.connect(tmp_path/'backup.sqlite') as con:assert con.execute('PRAGMA quick_check').fetchone()[0]=='ok'


def test_download_partial_error_and_order():
    with sample_extended_client() as c:
        result=c.download([S,'NOT_A_SYMBOL',S],dataset='trades',start=DATE,end=DATE,update=False)
    assert result.requests.status.tolist()==['ok','error','ok']
    assert result.data.request_index.tolist()==[0,0,2,2]


def test_async_download_shared_plan(tmp_path):
    async def run():
        async with sample_extended_async_client(storage=True,data_dir=tmp_path/'db') as c:
            a=await c.download([S],update=False,checkpoint_dir=tmp_path/'jobs')
            b=await c.download([S],update=False,checkpoint_dir=tmp_path/'jobs')
            await c.flush(timeout=10)
            status=await c.datasets()
            backup=await c.backup(tmp_path/'backup.sqlite')
            return a,b,status,backup
    a,b,status,backup=asyncio.run(run())
    assert b.requests.resumed.all() and not status.empty and backup['state']=='persisted'


def test_intraday_batch_api():
    with sample_extended_client() as c:r=c.get_trades_many([S,S],start=DATE)
    assert len(r.data)==4


def test_dataframe_empty_missing_and_incompatible():
    f=data.load_sample()
    empty=f.iloc[:0]
    assert data.coverage(empty).coverage_status.iloc[0]=='unknown'
    bad=f.copy();bad['adjustment']='source'
    with pytest.raises(DataQualityError):data.concat([f,bad])
    with pytest.raises(DataQualityError):data.compare_sources(f,bad)
    with pytest.raises(DataQualityError):data.set_date_index(pd.concat([f,f]))


def test_no_silent_proxy_change(monkeypatch):
    from pydara.tse import diagnostics
    touched=[]
    class Fake:
        def __init__(self,**kw):touched.append(kw['trust_env'])
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def stream(self,*args,**kw):raise ValueError('fixture failure')
    monkeypatch.setattr(diagnostics.httpx,'Client',Fake)
    r=data.check_connection(network='auto')
    assert touched==[True] and r.status.eq('error').all()
    data.check_connection(network='auto',allow_direct=True)
    assert touched==[True,True,False]
    assert not data.diagnose().empty

@pytest.mark.parametrize('name',['trades_v1','order_book_v1','adjustments_v1','adjusted_history_v1','funds_v1','fund_nav_v1','shareholders_v1','options_v1','futures_v1','dividends_v1'])
def test_explicit_new_samples(name):
    f=data.load_sample(name)
    assert not f.empty and f.attrs['pydara']['synthetic']
    assert not data.validate_data(f).query("severity == 'error'").shape[0]

@pytest.mark.parametrize('method,args,kwargs',CALLS)
def test_exact_numeric_profile(method,args,kwargs):
    with sample_extended_client(numeric='exact') as c:f=getattr(c,method)(*args,**kwargs)
    from pydara.tse.market_schemas import SCHEMAS
    spec=SCHEMAS[f.attrs['pydara']['schema_id']]
    for col in spec.numbers:
        assert f[col].dtype==object
        assert all(isinstance(v,Decimal) for v in f[col].dropna())

@pytest.mark.parametrize('ep,response',[
 ('extra.trades',{'trade':[{'pTran':100}]}),
 ('extra.trades',{'trade':[{'pTran':None,'qTitTran':100}]}),
 ('extra.trades',{'trade':[{'pTran':-1,'qTitTran':100}]}),
 ('extra.adjustments',{'priceAdjust':[{'dEven':20250318,'pClosing':100}]}),
 ('extra.options',{'instrumentOptMarketWatch':[{'strikePrice':100}]}),
 ('extra.boards','<html>login</html>'),
 ('extra.dividends','<html>login</html>'),
 ('extra.adjusted','20250317,90,100,101,108,2000,106;'),
 ('extra.adjusted','wrong,text;'),
])
def test_malformed_new_shapes_not_cached(ep,response):
    names={'extra.trades':('get_trades',(S,)),'extra.adjustments':('get_adjustments',(S,)),
           'extra.options':('get_options',()),'extra.boards':('get_boards',()),'extra.dividends':('get_dividends',(S,)),
           'extra.adjusted':('get_adjusted_history',(S,))}
    method,args=names[ep]
    with sample_extended_client(responses={ep:response}) as c:
        with pytest.raises(PyDaraError):getattr(c,method)(*args)


def test_checkpoint_permission_failure_does_not_lose_data(tmp_path,monkeypatch):
    import pydara.tse.workflows as w
    monkeypatch.setattr(w,'_prepare_checkpoint',lambda *a: (_ for _ in ()).throw(PermissionError()))
    with sample_extended_client(storage=True,data_dir=tmp_path) as c:
        r=c.download([S],update=False,checkpoint_dir=tmp_path/'jobs')
    assert not r.data.empty
    assert r.requests.checkpoint_state.tolist()==['failed']


def test_stale_resume_labeled_and_fresh_bypasses(tmp_path):
    with sample_extended_client(storage=True,data_dir=tmp_path/'db') as c:
        c.download([S],update=False,checkpoint_dir=tmp_path/'jobs')
        r=c.download([S],update=False,checkpoint_dir=tmp_path/'jobs')
        assert r.data.is_stale.all() and r.data.from_cache.all()
        assert r.manifest['components'][0]['resumed_from_checkpoint']
        fresh=c.download([S],update=False,checkpoint_dir=tmp_path/'jobs',policy=FetchPolicy.fresh())
        assert not fresh.requests.resumed.any()


def test_closed_client_rejects_job_before_writing(tmp_path):
    c=sample_extended_client(storage=True,data_dir=tmp_path/'db');c.close()
    with pytest.raises(PyDaraError):c.download([S],checkpoint_dir=tmp_path/'jobs')
    assert not (tmp_path/'jobs').exists()


def test_offline_default_never_syncs_network(tmp_path):
    with sample_extended_client(storage=True,data_dir=tmp_path) as c:
        c.get_history(S);c.flush(timeout=10)
    with sample_extended_client(storage=True,data_dir=tmp_path,mode='offline') as c:
        with patch.object(c._wire,'request',side_effect=AssertionError('network')):
            r=c.download([S],policy=FetchPolicy.offline(allow_stale=True))
    assert not r.data.empty


def test_unsafe_backup_destination_rejected(tmp_path):
    with sample_extended_client(storage=True,data_dir=tmp_path) as c:
        c.get_history(S);c.flush(timeout=10)
        with pytest.raises(StorageError):c.backup(c.storage_status().path,overwrite=True)


def test_async_cancellation_propagates():
    async def run():
        async with sample_extended_async_client() as c:
            async def cancelled(*args,**kwargs):raise asyncio.CancelledError()
            with patch.object(c,'get_history',new=cancelled):
                with pytest.raises(asyncio.CancelledError):await c.download([S],update=False)
    asyncio.run(run())


def test_download_market_default_only_plans():
    with sample_extended_client() as c:
        plan=c.download_market(limit=1)
        assert len(plan)==1 and plan.attrs['pydara']['not_historical_universe']
        assert c.request_count==1


def test_multiday_trade_ids_scope_to_dates():
    with sample_extended_client() as c:
        f=c.get_trades(S,start='2025-03-17',end='2025-03-18')
    assert f.row_id.is_unique and len(f)==4


def test_autosave_errors_do_not_break_new_quote_data(tmp_path):
    with sample_extended_client(storage=True,data_dir=tmp_path) as c:
        with patch.object(c._core.store,'submit',side_effect=StorageError('simulated storage problem')):
            # Core's public autosave handling decides how errors are isolated.
            try:r=c.get_trades(S,day=DATE)
            except StorageError:pytest.fail('autosave error escaped fetch')
    assert len(r)==2

@pytest.mark.parametrize('sample',['trades_v1','order_book_v1','shareholders_v1','fund_nav_v1','options_v1','adjusted_history_v1'])
@pytest.mark.parametrize('fmt',['csv','sqlite','xlsx'])
def test_new_family_archive_roundtrip(tmp_path,sample,fmt):
    if fmt=='xlsx':pytest.importorskip('openpyxl')
    original=data.load_sample(sample)
    path=tmp_path/('archive.'+fmt)
    data.save(original,path)
    restored=data.load(path)
    pd.testing.assert_frame_equal(original,restored,check_dtype=True)


def test_public_exports_have_catalog_rows():
    names=['history','download','download_many','setup','diagnose','coverage','get_trades_many','get_funds','get_options','get_futures','backup','examples','columns']
    for name in names:
        assert name in data.__all__
        assert len(data.api_reference(name))==1


def test_fresh_checkpoint_does_not_override_fresh_policy(tmp_path):
    with sample_extended_client(storage=True,data_dir=tmp_path/'db') as c:
        kw={'update':False,'checkpoint_dir':tmp_path/'jobs','policy':FetchPolicy.fresh()}
        c.download([S],**kw);count=c.request_count
        r=c.download([S],**kw)
        assert c.request_count>count
        assert not r.requests.resumed.any()
