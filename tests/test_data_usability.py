"""Regression tests for the data-only usability release; no real network."""
import asyncio
from copy import deepcopy
from datetime import date, datetime, timedelta, UTC
from decimal import Decimal
import inspect
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pydara import tse as data
from pydara.tse import (Client, ClientConfig, FetchPolicy, FreshnessPolicy,
                           NetworkConfig, InstrumentRef)
from pydara.tse.samples import sample_client, sample_async_client, sample_transport
from pydara.tse.exceptions import (InvalidArgumentError, ConfigurationError, DataQualityError,
                                StaleDataError, UnknownInstrumentError, UnsupportedCapabilityError)

FOLAD='\u0641\u0648\u0644\u0627\u062f'
SHASTA='\u0634\u0633\u062a\u0627'
FAST=ClientConfig(network=NetworkConfig(requests_per_second=1e6,max_retries=0))

@pytest.mark.parametrize('kind',[list,tuple,pd.Series,pd.Index,np.array])
def test_pandas_batch_quotes(kind):
    with sample_client() as c:
        result=c.get_quotes(kind([FOLAD,SHASTA,FOLAD]))
        assert result.input_symbol.tolist()==[FOLAD,SHASTA,FOLAD]
        assert result.request_index.tolist()==[0,1,2]
        assert result.status.tolist()==['ok']*3
        assert str(result.ins_code.dtype)=='string'

@pytest.mark.parametrize('kind',[pd.Series,pd.Index,np.array])
def test_pandas_batch_histories(kind):
    with sample_client() as c:
        result=c.get_history_many(kind([FOLAD,SHASTA,FOLAD]))
        assert result.requests.request_index.tolist()==[0,1,2]
        assert result.errors.empty
        assert set(result.data.request_index)=={0,1,2}

@pytest.mark.parametrize('bad',[
    pd.Series([FOLAD,None]),pd.Index([FOLAD,12]),np.array([[FOLAD]]),
    {FOLAD},pd.DataFrame({'symbol':[FOLAD]}),[FOLAD,' '],pd.Series([],dtype='string'),
    (x for x in [FOLAD]),pd.MultiIndex.from_tuples([(FOLAD,1)])])
def test_reject_bad_batch_before_http(bad):
    with sample_client() as c:
        with pytest.raises(InvalidArgumentError):c.get_quotes(bad)
        assert c.request_count==0

def test_numeric_constructor_and_frame_helpers():
    with Client(config=FAST,storage=False,numeric='exact',transport=sample_transport(),_namespace='sample') as c:
        frame=c.get_quote_frame(FOLAD)
        assert isinstance(frame.last_price.iloc[0],Decimal)
        assert c.request_count==3
        assert str(frame.fetched_at.dtype)=='datetime64[ns, UTC]'
        record=c._resolve_instrument_record(FOLAD)
        assert record.to_ref()==InstrumentRef.by_ins_code(record.ins_code)
        pd.testing.assert_frame_equal(c.get_instrument_frame(FOLAD),record.to_frame())

def test_quote_frame_pandas_default():
    with sample_client() as c:
        frame=c.get_quote_frame(FOLAD)
        assert str(frame.last_price.dtype)=='Float64'
        assert frame.ins_code.iloc[0]=='46348559193224090'
        assert len(frame)==1

@pytest.mark.parametrize('bad',['EXACT','float',False,5])
def test_bad_numeric_shorthand(bad):
    with pytest.raises(ConfigurationError):Client(numeric=bad)

def test_offline_policy_keeps_permission_explicit(tmp_path):
    with sample_client(storage=True,data_dir=tmp_path) as c:
        c.get_quote(FOLAD);c.flush()
    with sample_client(storage=True,data_dir=tmp_path) as c:
        with pytest.raises(StaleDataError):c.get_quote(FOLAD,policy='offline')
        quote=c.get_quote(FOLAD,policy=FetchPolicy.offline(allow_stale=True))
        assert quote.meta.from_cache and quote.meta.is_stale
        assert c.request_count==0
        assert 'stale_cached_response' in quote.meta.quality_flags

def test_offline_history_shorthand(tmp_path):
    with sample_client(storage=True,data_dir=tmp_path) as c:
        original=c.get_history(FOLAD);c.flush()
    with sample_client(storage=True,data_dir=tmp_path) as c:
        restored=c.get_history(FOLAD,policy='offline')
        assert restored.closing_price.tolist()==original.closing_price.tolist()
        assert c.request_count==0

def test_fresh_forces_new_request_and_no_stale_permission():
    with sample_client() as c:
        c.get_history(FOLAD)
        n=c.request_count
        c.get_history(FOLAD)
        assert c.request_count==n
        c.get_history(FOLAD,policy=FetchPolicy.fresh())
        assert c.request_count==n+3
    assert FetchPolicy.offline().freshness.allow_stale is False
    assert FetchPolicy.fresh().mode=='online'
    assert FetchPolicy.fresh().freshness.max_age==timedelta(0)

@pytest.mark.parametrize('bad',[{},2,True,'invalid'])
def test_invalid_policy_before_network(bad):
    with sample_client() as c:
        with pytest.raises(ConfigurationError):c.get_history(FOLAD,policy=bad)
        assert c.request_count==0


def test_async_uses_same_batch_and_frame_logic(tmp_path):
    async def run():
        async with sample_async_client(storage=True,data_dir=tmp_path) as c:
            q=await c.get_quote_frame(FOLAD)
            record=await c.get_instrument_frame(FOLAD)
            batch=await c.get_history_many(pd.Series([FOLAD,SHASTA]))
            quotes=await c.get_quotes(pd.Index([FOLAD,SHASTA]))
            assert str(q.fetched_at.dtype)=='datetime64[ns, UTC]'
            assert record.ins_code.iloc[0]==q.ins_code.iloc[0]
            assert batch.errors.empty and len(quotes)==2
            await c.flush()
        async with sample_async_client(storage=True,data_dir=tmp_path) as c:
            old=await c.get_quote_frame(FOLAD,policy=FetchPolicy.offline(allow_stale=True))
            assert c.request_count==0 and old.is_stale.iloc[0]
    asyncio.run(run())


def test_configure_is_lazy_and_does_not_delete_storage(tmp_path):
    data.close()
    try:
        path=tmp_path/'not_created'
        config=data.configure(data_dir=path,storage=False,numeric='exact',mode='offline')
        assert data.get_config()==config
        assert not path.exists()
        data.capabilities()  # introspection must not lock configuration
        data.configure(storage=False)
        data.storage_status()  # intentionally constructs the lazy default client
        with pytest.raises(ConfigurationError,match='close'):data.configure()
    finally:
        data.close();data.configure()


def test_module_method_signatures_match():
    names=['get_quote','get_price','get_quote_frame','get_instrument_frame','get_quotes',
           'get_history','get_history_many','iter_history','sync_history','load_stored_history']
    for name in names:
        facade=inspect.signature(getattr(data,name))
        method=inspect.signature(getattr(Client,name))
        params=list(method.parameters.values())[1:]
        assert facade==method.replace(parameters=params),name

@pytest.mark.parametrize('value',[pd.Timestamp('2024-01-01'),pd.Timestamp('2024-01-01').as_unit('us')])
def test_midnight_pandas_timestamp_as_date(value):
    assert data.to_gregorian(value,calendar='gregorian')==date(2024,1,1)
    with sample_client() as c:
        result=c.get_history(FOLAD,start=value)
        assert (result.date>=value).all()

@pytest.mark.parametrize('bad',[pd.Timestamp('2024-01-01T01:00:00'),pd.Timestamp('2024-01-01',tz='UTC'),
                                pd.Timestamp('2024-01-01T00:00:00.000000001'),pd.NaT])
def test_ambiguous_pandas_dates_rejected(bad):
    with pytest.raises(InvalidArgumentError):data.to_gregorian(bad,calendar='gregorian')

@pytest.mark.parametrize('schema',['daily_bars','quote','quotes.batch','instruments'])
def test_schema_information(schema):
    frame=data.schema_info(schema)
    assert {'column','dtype','required','description'}==set(frame)
    assert frame.column.is_unique
    assert frame.required.dtype=='boolean'
    assert len(frame)>10


def test_normalized_existing_history_does_not_mutate_input():
    with sample_client() as c:df=c.get_history(FOLAD,include_jdate=True)
    original=df.copy(deep=True);original.attrs=deepcopy(df.attrs)
    out=data.normalize_data(df)
    pd.testing.assert_frame_equal(df,original)
    assert data.validate_data(out).empty
    assert out is not df
    assert data.validate_data(out).attrs['pydara']['is_valid']


def test_explicit_column_mapping_and_numeric_conversion():
    df=pd.DataFrame({'id':['46348559193224090'],'day':['1403-01-01'],
                     'p':['1200.50'],'n':['3'],'extra':['kept']})
    out=data.normalize_data(df,columns={'id':'ins_code','day':'date','p':'closing_price','n':'trade_count'},calendar='jalali')
    assert out.date.iloc[0]==pd.Timestamp('2024-03-20')
    assert str(out.closing_price.dtype)=='Float64'
    assert out.trade_count.iloc[0]==3 and str(out.trade_count.dtype)=='Int64'
    assert out.extra.iloc[0]=='kept' and df.p.iloc[0]=='1200.50'
    assert out.attrs['pydara']['provenance_status']=='unknown'
    assert not data.validate_data(out).attrs['pydara']['is_valid']  # missing required fields reported


def test_exact_normalization_and_signed_values_not_clipped():
    df=pd.DataFrame({'closing_price':['-1.25'],'ins_code':['1']})
    out=data.normalize_data(df,numeric='exact')
    assert out.closing_price.iloc[0]==Decimal('-1.25')
    assert 'negative_value' in data.validate_data(out).rule.values

@pytest.mark.parametrize('value',[46348559193224090.0,Decimal('46348559193224090.0'),True])
def test_normalization_never_recovers_float_identifiers(value):
    with pytest.raises(InvalidArgumentError):data.normalize_data(pd.DataFrame({'ins_code':[value]}))

@pytest.mark.parametrize('value',['False','0',0,1])
def test_boolean_strings_not_guessed(value):
    with pytest.raises(InvalidArgumentError):data.normalize_data(pd.DataFrame({'is_stale':[value]}))


def test_normalize_naive_timestamp_requires_timezone():
    df=pd.DataFrame({'fetched_at':['2025-01-01T12:00:00']})
    with pytest.raises(InvalidArgumentError):data.normalize_data(df)
    result=data.normalize_data(df,timezone='Asia/Tehran')
    assert result.fetched_at.iloc[0]==pd.Timestamp('2025-01-01T08:30:00Z')
    assert str(result.fetched_at.dtype)=='datetime64[ns, UTC]'


def test_bad_renaming_and_duplicate_columns():
    with pytest.raises(InvalidArgumentError):data.normalize_data(pd.DataFrame({'a':[1]}),columns={'unknown':'price'})
    with pytest.raises(InvalidArgumentError):data.normalize_data(pd.DataFrame({'a':[1],'b':[2]}),columns={'a':'b'})
    with pytest.raises(InvalidArgumentError):data.validate_data(pd.DataFrame([[1,2]],columns=['a','a']))


def test_validator_duplicates_nulls_and_invalid_values():
    with sample_client() as c:df=c.get_history(FOLAD)
    broken=pd.concat([df,df.iloc[[0]]],ignore_index=True)
    broken.loc[1,'ins_code']=pd.NA
    broken.loc[2,'low_price']=10000000.0
    report=data.validate_data(broken)
    assert {'duplicate_key','missing_identity_or_date','low_above_high'}.issubset(set(report.rule))
    with pytest.raises(DataQualityError) as e:data.validate_data(broken,raise_on_error=True)
    assert isinstance(e.value.report,pd.DataFrame)


def test_compact_projection_explicit_and_safe():
    with sample_client() as c:df=c.get_history(FOLAD)
    compact=data.select_columns(df)
    assert len(compact.columns)<len(df.columns)
    assert compact.attrs['pydara']['presentation_only']
    assert 'available_at' in compact.attrs['pydara']['removed_evidence_columns']
    compact.loc[0,'closing_price']=0
    assert df.closing_price.iloc[0]!=0
    info=data.frame_metadata(df);info['fake']='test'
    assert 'fake' not in df.attrs['pydara']
    with pytest.raises(InvalidArgumentError):data.select_columns(df,['closing_price','BAD'])
    with pytest.raises(InvalidArgumentError):data.select_columns(df,['date','date'])

@pytest.mark.parametrize('suffix',['csv','xlsx','sqlite'])
def test_new_table_helpers_roundtrip(suffix,tmp_path):
    with sample_client() as c:df=c.get_quote_frame(FOLAD)
    path=tmp_path/f'result.{suffix}'
    data.save(df,path)
    restored=data.load(path)
    pd.testing.assert_frame_equal(df,restored)

@pytest.mark.parametrize('bad',[None,42,b'bytes',True,' '])
def test_invalid_path_has_public_error(bad):
    with pytest.raises(InvalidArgumentError):data.save(pd.DataFrame({'x':[1]}),bad)
    with pytest.raises(InvalidArgumentError):data.load(bad)

def test_invalid_format_has_public_error(tmp_path):
    with pytest.raises(InvalidArgumentError):data.save(pd.DataFrame({'x':[1]}),tmp_path/'x',format=2)


def test_data_only_extras_and_catalog():
    assert 'analytics' not in data.__all__ and 'ml' not in data.__all__
    ref=data.api_reference('get_history')
    assert ref.name.tolist()==['get_history']
    assert 'DataFrame' in ref['returns'].iloc[0]
    assert 'start' in ref['signature'].iloc[0]
    with pytest.raises(InvalidArgumentError):data.api_reference('not_a_function')

@pytest.mark.parametrize('options',[{'mode':[]},{'numeric':[]},{'source':[]},
    {'data_dir':3},{'data_dir':' '},{'storage':'false'}])
def test_invalid_constructor_inputs_are_configuration_errors(options):
    with pytest.raises(ConfigurationError):Client(**options)

@pytest.mark.parametrize('field',[[],{},False,None])
def test_price_field_checked_before_network(field):
    with sample_client() as c:
        with pytest.raises(InvalidArgumentError):c.get_price(FOLAD,field=field)
        assert c.request_count==0


def test_config_boolean_types_explicit():
    with pytest.raises(ConfigurationError):NetworkConfig(trust_env='false')
    with pytest.raises(ConfigurationError):FetchPolicy(allow_official_offline=1)
    with pytest.raises(ConfigurationError):ClientConfig(strict_schema='true')

@pytest.mark.parametrize('name',['future_unimplemented_schema','not_known',[],None])
def test_unknown_schema_not_guessed(name):
    with pytest.raises(InvalidArgumentError):data.schema_info(name)


def test_roadmap_validation_and_synthetic_sample():
    df=data.load_sample()
    assert df.attrs['pydara']['synthetic'] is True
    assert data.validate(df,schema='daily_bars').empty
    assert {'row_id','rule','severity','message'}.issubset(data.validate(df,schema='daily_bars'))
    out=data.normalize(df,schema='daily_bars',source='canonical')
    assert len(out)==len(df)
    with pytest.raises(UnsupportedCapabilityError):
        data.normalize(df,schema='daily_bars',source='unreviewed')


def test_load_sample_does_not_initialize_default_client(tmp_path):
    data.close();data.configure(storage=False,data_dir=tmp_path/'not_created')
    try:
        df=data.load_sample('quote_v1')
        assert len(df)==1 and not (tmp_path/'not_created').exists()
        data.configure()  # still no default client exists
    finally:
        data.close();data.configure()


def test_batch_signatures_declare_pandas_inputs():
    for owner in (data, data.Client, data.AsyncClient):
        for name in ("get_quotes", "get_history_many"):
            annotation = str(inspect.signature(getattr(owner, name)).parameters["instruments"].annotation)
            assert "pd.Series" in annotation and "pd.Index" in annotation and "np.ndarray" in annotation

@pytest.mark.parametrize("bad", [[], {}, 123, np.array(["analysis", "exact"])])
def test_schema_profile_types_are_explicit(bad):
    with pytest.raises(InvalidArgumentError):
        data.schema_info(numeric=bad)
