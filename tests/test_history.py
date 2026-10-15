from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, UTC, timedelta
from decimal import Decimal
import asyncio
import json
from pathlib import Path
import sqlite3

import httpx
import pandas as pd
import pytest

from pydara import __version__
from pydara.tse import (Client, AsyncClient, ClientConfig, NetworkConfig,
                          StorageConfig, FetchPolicy, FreshnessPolicy, InstrumentRef, BatchFrames)
from pydara.tse.samples import sample_client, sample_async_client, sample_transport
from pydara.tse.providers.history import history_spec, parse_history_rows
from pydara.tse.transport import Packet
from pydara.tse.exceptions import *

FOLAD = '\u0641\u0648\u0644\u0627\u062f'
SHASTA = '\u0634\u0633\u062a\u0627'
CODE = '46348559193224090'
FAST = ClientConfig(network=NetworkConfig(requests_per_second=1_000_000, max_retries=0))
FRESH = FetchPolicy(mode='online', freshness=FreshnessPolicy(max_age=timedelta(0)))
OFFLINE = FetchPolicy(mode='offline', freshness=FreshnessPolicy(allow_stale=True))


def history_payload():
    from importlib.resources import files
    return json.loads(files('pydara.tse.samples').joinpath('history_fixture.json').read_text())


def mock_history(body=None, modify=None, failure=None):
    base = sample_transport()
    def handler(r):
        if 'GetClosingPriceDailyList/' in r.url.path:
            if failure:
                return httpx.Response(failure, json={'problem':'synthetic'})
            value = deepcopy(history_payload() if body is None else body)
            if modify:
                modify(value)
            return httpx.Response(200, json=value)
        return base.handle_request(r)
    return httpx.MockTransport(handler)


def test_sorted_raw_dataframe_and_metadata():
    with sample_client() as c:
        df = c.get_history(FOLAD)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 6 and df.date.is_monotonic_increasing
        assert df.date.dtype == 'datetime64[ns]'
        assert df.ins_code.dtype == 'string'
        assert str(df.trade_count.dtype) == 'Int64'
        assert str(df.last_price.dtype) == 'Float64'
        assert df.loc[0,'last_price'] == 105 and df.loc[0,'closing_price'] == 104
        assert df['adjustment'].tolist() == ['none']*6
        assert df['ins_code'].unique().tolist() == [CODE]
        assert df.attrs['pydara']['package_version'] == __version__
        assert df.attrs['pydara']['coverage_status'] == 'unknown'
        assert df.first_observed_at.min() > pd.Timestamp('2025-03-21',tz='UTC')
        assert (df.available_at == df.fetched_at).all()
        assert 'history_response_identifier_zero_placeholder' in df.quality_flags.iloc[0]
        assert 'synthetic_sample_not_market_data' in df.quality_flags.iloc[0]


def test_date_filter_inclusive_and_same_response_key():
    with sample_client() as c:
        a = c.get_history(FOLAD,start='2024-03-20',end='2024-03-21')
        count = c.request_count
        b = c.get_history(FOLAD,start='2024-03-19',end='2024-04-01')
        assert len(a)==2 and len(b)==4
        assert c.request_count == count
        assert b.from_cache.all()
        assert a.date.dt.date.tolist() == [date(2024,3,20),date(2024,3,21)]


def test_jalali_range_and_column():
    with sample_client() as c:
        df=c.get_history(FOLAD,start='1403-01-01',end='1403-12-30',calendar='jalali',include_jdate=True)
        assert len(df)==4
        assert df.jdate.tolist() == ['1403-01-01','1403-01-02','1403-01-13','1403-12-30']
        assert df.date.iloc[-1] == pd.Timestamp('2025-03-20')
        assert df.attrs['pydara']['calendar_input']=='jalali'


def test_no_network_before_invalid_parameters():
    with sample_client() as c:
        cases=[({'start':'2024-04-01','end':'2024-03-01'},InvalidArgumentError),
               ({'start':20240320},InvalidArgumentError),
               ({'start':datetime(2024,3,20)},InvalidArgumentError),
               ({'calendar':'auto'},InvalidArgumentError),
               ({'include_jdate':1},InvalidArgumentError),
               ({'adjustment':True},InvalidArgumentError),
               ({'series':'continuous_verified'},UnsupportedCapabilityError),
               ({'as_of':datetime(2024,3,20)},InvalidArgumentError),
               ({'as_of':datetime(2024,3,20,tzinfo=UTC)},PointInTimeUnavailableError)]
        for kwargs,error in cases:
            with pytest.raises(error):c.get_history(FOLAD,**kwargs)
        assert c.request_count==0


def test_exact_values_and_mutation_isolation():
    body=history_payload();body['closingPriceDaily'][0]['qTotCap']='9007199254740993'
    with Client(config=replace(FAST,numeric='exact'), storage=False, transport=mock_history(body)) as c:
        a=c.get_history(FOLAD)
        assert isinstance(a.loc[0,'last_price'],Decimal)
        assert a.turnover.iloc[-1] == Decimal('9007199254740993')
        a.loc[0,'last_price']=Decimal('999')
        a.attrs['pydara']['warnings'].append('modified')
        b=c.get_history(FOLAD)
        assert b.loc[0,'last_price']==Decimal('105')
        assert 'modified' not in b.attrs['pydara']['warnings']
    with Client(config=FAST,storage=False,transport=mock_history(body)) as c:
        df=c.get_history(FOLAD)
        assert 'large_numeric_value_use_exact_profile' in df.quality_flags.iloc[-1]


@pytest.mark.parametrize('value',[None,'','0',0,'0.0','0e0',CODE,46348559193224090,'4.6348559193224090E16'])
def test_identity_wire_representations(value):
    body=history_payload()
    for row in body['closingPriceDaily']:row['insCode']=value
    with Client(config=FAST,storage=False,transport=mock_history(body)) as c:
        df=c.get_history(FOLAD)
        assert (df.ins_code==CODE).all()


@pytest.mark.parametrize('value',['42','46348559193224091','4.6348559193224088E16',True,'-1','1.5','nan'])
def test_invalid_or_mismatched_identity_rejected(value):
    def modify(x):x['closingPriceDaily'][0]['insCode']=value
    with Client(config=FAST,storage=False,transport=mock_history(modify=modify)) as c:
        with pytest.raises((SchemaMismatchError,DataQualityError)):
            c.get_history(FOLAD)


@pytest.mark.parametrize('key,value',[('dEven','20250230'),('dEven',0),('dEven',True),
    ('hEven',246000),('hEven','12:30:00'),('pClosing',-1),('pDrCotVal','nan'),
    ('zTotTran','1.5'),('zTotTran','9223372036854775808'),('qTotTran5J',-1)])
def test_bad_fields_have_row_context(key,value):
    def modify(x):x['closingPriceDaily'][0][key]=value
    with Client(config=FAST,storage=False,transport=mock_history(modify=modify)) as c:
        with pytest.raises((SchemaMismatchError,DataQualityError),match='row=0'):
            c.get_history(FOLAD)


def test_optional_missing_fields_are_not_zero_and_zero_no_trade_preserved():
    body=history_payload();r=body['closingPriceDaily'][0]
    for key in ['priceFirst','priceMin','priceMax','qTotCap','hEven','id','insCode']:r.pop(key,None)
    r['pDrCotVal']=None;r['qTotTran5J']=0;r['zTotTran']=0
    with Client(config=FAST,storage=False,transport=mock_history(body)) as c:
        df=c.get_history(FOLAD)
        assert pd.isna(df.last_price.iloc[-1]) and pd.isna(df.open_price.iloc[-1])
        assert df.volume.iloc[-1]==0 and df.trade_count.iloc[-1]==0
        assert len(df)==6
        assert 'no_trade_or_zero_volume_as_reported' in df.quality_flags.iloc[-1]
        assert 'history_response_identifier_missing' in df.quality_flags.iloc[-1]


def test_low_above_high_error():
    body=history_payload();body['closingPriceDaily'][0]['priceMin']=999
    with Client(config=FAST,storage=False,transport=mock_history(body)) as c:
        with pytest.raises(DataQualityError):c.get_history(FOLAD)


def test_identical_duplicates_removed_conflicting_rejected():
    body=history_payload();body['closingPriceDaily'].append(deepcopy(body['closingPriceDaily'][0]))
    with Client(config=FAST,storage=False,transport=mock_history(body)) as c:
        df=c.get_history(FOLAD)
        assert len(df)==6
        assert df.attrs['pydara']['identical_duplicates_removed']==1
    body['closingPriceDaily'][-1]['pClosing']=1
    with Client(config=FAST,storage=False,transport=mock_history(body)) as c:
        with pytest.raises(DataQualityError,match='Conflicting duplicate'):c.get_history(FOLAD)


@pytest.mark.parametrize('body',[{}, {'closingPriceDaily':None}, {'closingPriceDaily':{}},
                               {'closingPriceDaily':[None]}, {'closingPriceDaily':[{}]}])
def test_schema_empty_failure_distinguished(body):
    with Client(config=FAST,storage=False,transport=mock_history(body)) as c:
        with pytest.raises(SchemaMismatchError):c.get_history(FOLAD)


def test_valid_empty_and_outside_range_are_typed():
    with Client(config=FAST,storage=False,transport=mock_history({'closingPriceDaily':[]})) as c:
        df=c.get_history(FOLAD,include_jdate=True)
        assert df.empty and str(df.last_price.dtype)=='Float64'
        assert str(df.trade_count.dtype)=='Int64' and str(df.jdate.dtype)=='string'
        assert df.attrs['pydara']['no_rows_reason']=='empty_source'
    with sample_client() as c:
        df=c.get_history(FOLAD,start='2010-01-01',end='2010-12-31')
        assert df.empty and df.attrs['pydara']['no_rows_reason']=='no_rows_in_requested_range'


def test_strict_coverage_never_claims_complete():
    with sample_client() as c:
        with pytest.raises(CoverageError) as caught:
            c.get_history(FOLAD,policy=FetchPolicy(coverage='raise'))
        assert caught.value.report['coverage_status']=='unknown'


def test_batch_retains_empty_successes_duplicates_errors_and_remaining():
    with sample_client() as c:
        b=c.get_history_many([FOLAD,'BAD',SHASTA,FOLAD],on_error='collect')
        assert isinstance(b,BatchFrames)
        assert b.requests.status.tolist()==['ok','error','ok','ok']
        assert len(b.data)==18 and len(b.errors)==1
        assert b.data.request_index.unique().tolist()==[0,2,3]
        assert b.manifest['processed_items']==4 and b.manifest['failed_items']==1
        e=c.get_history_many([FOLAD,SHASTA],start='2000-01-01',end='2000-01-02')
        assert e.data.empty and e.errors.empty and e.requests.status.tolist()==['empty','empty']
        with pytest.raises(BatchDataError) as caught:c.get_history_many([FOLAD,'BAD',SHASTA])
        partial=caught.value.partial_result
        assert isinstance(partial,BatchFrames) and partial.manifest['unprocessed_items']==1


def test_iter_local_chunks_not_extra_requests():
    with sample_client() as c:
        chunks=list(c.iter_history(FOLAD,start='2024-03-19',end='2025-03-21',chunk_days=200))
        assert [len(x) for x in chunks]==[4,2]
        assert c.request_count==3
        joined=pd.concat(chunks,ignore_index=True)
        assert len(joined)==6 and joined.date.is_unique
        assert chunks[0].attrs['pydara']['chunk']['start']=='2024-03-19'
        with pytest.raises(InvalidArgumentError):list(c.iter_history(FOLAD,start=None,end=None))
        with pytest.raises(InvalidArgumentError):list(c.iter_history(FOLAD,start='2024-01-01',end='2024-02-01',chunk_days=0))


def test_full_response_cached_even_for_small_query_and_no_http_offline(tmp_path,monkeypatch):
    with sample_client(storage=True,data_dir=tmp_path) as c:
        c.get_history(FOLAD,start='2024-03-20',end='2024-03-20')
        assert c.flush().complete
    def forbidden(*a,**k):raise AssertionError('unexpected HTTP')
    monkeypatch.setattr(httpx.Client,'send',forbidden)
    with sample_client(storage=True,data_dir=tmp_path,mode='offline') as c:
        b=c.get_history(FOLAD,policy=OFFLINE)
        assert len(b)==6 and b.from_cache.all()
        assert c.request_count==0


def test_stale_history_without_permission_is_rejected(tmp_path):
    with sample_client(storage=True,data_dir=tmp_path) as c:
        c.get_history(FOLAD);c.flush()
    policy=FetchPolicy(mode='offline',freshness=FreshnessPolicy(max_age=timedelta(0)))
    with sample_client(storage=True,data_dir=tmp_path) as c:
        with pytest.raises(StaleDataError):c.get_history(FOLAD,policy=policy)
        with pytest.warns(StaleDataWarning):
            df=c.get_history(FOLAD,policy=replace(policy,freshness=FreshnessPolicy(max_age=timedelta(0),allow_stale=True)))
        assert df.is_stale.all() and c.request_count==0


def test_bad_payload_never_persisted(tmp_path):
    body=history_payload();body['closingPriceDaily'][0]['pClosing']=-2
    with Client(config=FAST,data_dir=tmp_path,transport=mock_history(body)) as c:
        with pytest.raises(DataQualityError):c.get_history(FOLAD)
        c.flush()
    con=sqlite3.connect(tmp_path/'pydara.sqlite3')
    assert con.execute("SELECT count(*) FROM response_versions WHERE endpoint_id='history.daily'").fetchone()[0]==0
    con.close()


def test_changed_response_has_revision_and_identical_repeats_dedup_payload(tmp_path):
    body=history_payload()
    with Client(config=FAST,data_dir=tmp_path,transport=mock_history(body)) as c:
        a=c.get_history(FOLAD,policy=FRESH);c.flush()
        aa=c.get_history(FOLAD,policy=FRESH);c.flush()
    body['closingPriceDaily'][0]['pClosing']=Decimal('126')
    # Serialize Decimal explicitly as a numeric string in fixture JSON.
    body['closingPriceDaily'][0]['pClosing']='126'
    with Client(config=FAST,data_dir=tmp_path,transport=mock_history(body)) as c:
        b=c.get_history(FOLAD,policy=FRESH);c.flush()
    assert a.row_id.tolist()==b.row_id.tolist()
    assert a.row_version_id.iloc[-1]!=b.row_version_id.iloc[-1]
    con=sqlite3.connect(tmp_path/'pydara.sqlite3')
    assert con.execute("SELECT count(*) FROM response_versions WHERE endpoint_id='history.daily'").fetchone()[0]==2
    assert con.execute("SELECT count(*) FROM latest_response WHERE cache_key LIKE '%history.daily%'").fetchone()[0]==1
    con.close()


def test_storage_failure_and_queue_skip_do_not_break_history(tmp_path):
    file=tmp_path/'not_a_dir';file.write_text('x')
    with sample_client(storage=True,data_dir=file) as c:
        df=c.get_history(FOLAD)
        report=c.flush(raise_on_error=False)
        assert len(df)==6 and report.failed>0
    with Client(config=replace(FAST,storage=StorageConfig(queue_max_bytes=1)),
                data_dir=tmp_path/'queue',transport=sample_transport()) as c:
        df=c.get_history(FOLAD)
        assert len(df)==6 and c.storage_status().skipped_jobs>0


def test_history_async_parity_and_offline(tmp_path):
    async def run():
        with sample_client() as c:expected=c.get_history(FOLAD,include_jdate=True)
        async with sample_async_client(storage=True,data_dir=tmp_path) as c:
            actual=await c.get_history(FOLAD,include_jdate=True)
            assert actual[expected.columns[:12]].equals(expected[expected.columns[:12]])
            b=await c.get_history_many([FOLAD,'BAD',SHASTA],on_error='collect')
            assert len(b.data)==12 and len(b.errors)==1
            chunks=[x async for x in c.iter_history(FOLAD,start='2024-03-19',end='2025-03-21',chunk_days=200)]
            assert [len(x) for x in chunks]==[4,2]
            await c.flush()
        async with sample_async_client(storage=True,data_dir=tmp_path,mode='offline') as c:
            frame=await c.get_history(FOLAD,policy=OFFLINE)
            assert len(frame)==6 and frame.from_cache.all() and c.request_count==0
    asyncio.run(run())


def test_module_facade_uses_same_client(monkeypatch):
    from pydara import tse as data
    with sample_client() as c:
        monkeypatch.setattr(data,'_client',lambda:c)
        assert len(data.get_history(FOLAD))==6
        assert len(data.get_history_many([FOLAD]).data)==6
        assert sum(map(len,data.iter_history(FOLAD,start='2024-01-01',end='2025-12-31')))==6


def test_offline_sample_data_does_not_replace_public_data(tmp_path):
    with sample_client(storage=True,data_dir=tmp_path) as c:c.get_history(FOLAD);c.flush()
    with Client(config=FAST,data_dir=tmp_path,mode='offline',transport=mock_history()) as c:
        with pytest.raises(OfflineDataUnavailableError):c.get_history(FOLAD,policy=OFFLINE)
        assert c.request_count==0


def test_analysis_overflow_not_infinity_exact_profile_preserves():
    body=history_payload();body['closingPriceDaily'][0]['qTotCap']='1e309'
    with Client(config=FAST,storage=False,transport=mock_history(body)) as c:
        with pytest.raises(DataQualityError,match='overflows'):c.get_history(FOLAD)
    with Client(config=replace(FAST,numeric='exact'),storage=False,transport=mock_history(body)) as c:
        df=c.get_history(FOLAD)
        assert df.turnover.iloc[-1]==Decimal('1e309')


def test_row_version_hash_is_exact_not_decimal_context_rounded():
    body=history_payload();body['closingPriceDaily'][0]['qTotCap']='1.234567890123456789012345678901'
    spec=history_spec(CODE)
    a=parse_history_rows(Packet.create(spec,'sample',json.dumps(body).encode()),spec)
    body['closingPriceDaily'][0]['qTotCap']='1.234567890123456789012345678902'
    b=parse_history_rows(Packet.create(spec,'sample',json.dumps(body).encode()),spec)
    assert a.rows[-1]['row_version_id']!=b.rows[-1]['row_version_id']


def test_empty_iterator_preserves_empty_result_metadata():
    with sample_client() as c:
        pieces=list(c.iter_history(FOLAD,start='2010-01-01',end='2010-12-31'))
        assert len(pieces)==1 and pieces[0].empty
        assert pieces[0].attrs['pydara']['no_rows_reason']=='no_rows_in_requested_range'


def test_history_resource_limits_and_real_errors_not_empty():
    conf=replace(FAST,network=replace(FAST.network,max_response_bytes=1000))
    with Client(config=conf,storage=False,transport=mock_history()) as c:
        with pytest.raises(SchemaMismatchError,match='byte limit'):c.get_history(FOLAD)
    with Client(config=FAST,storage=False,transport=mock_history(failure=503)) as c:
        with pytest.raises(ServiceUnavailableError):c.get_history(FOLAD)
    with Client(config=FAST,storage=False,transport=mock_history({'closingPriceDaily':[{"dEven":20240320,"pClosing":1}]})) as c:
        with pytest.raises(SchemaMismatchError,match='pDrCotVal'):c.get_history(FOLAD)


def test_same_day_row_not_claimed_final():
    body=history_payload();today=datetime.now(UTC).astimezone(__import__('zoneinfo').ZoneInfo('Asia/Tehran')).date()
    body['closingPriceDaily'][0]['dEven']=int(today.strftime('%Y%m%d'))
    with Client(config=FAST,storage=False,transport=mock_history(body)) as c:
        df=c.get_history(FOLAD)
        assert 'current_session_row_not_certified_final' in df.quality_flags.iloc[-1]
