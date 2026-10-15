"""Synthetic regression for the unified participant facade."""
import asyncio
import pandas as pd
import pytest
from pydara import tse
from pydara.tse.samples.market import sample_market_client, sample_market_async_client
from pydara.tse._core.exceptions import InvalidArgumentError
CODE='46348559193224090'


def test_codes_dataframe_and_column_contract():
    with sample_market_client() as client:
        instruments=client.instrument(ins_code=[CODE,CODE])
        a=client.clients(ins_code=[CODE,CODE])
        b=client.clients(instruments)
        assert len(a)==len(b)==1
        assert a.inscode.iloc[0]==CODE
        assert not any('_' in c for c in a.columns)
        assert {'ibuycount','isellcount','lbuycount','lsellcount','ibuyvolume','lbuyvolume','buydddcount','fetchedat'} <= set(a.columns)
        assert a.ibuycount.iloc[0]==250
        assert a.attrs['pydara']['errors']==[]
        assert a.attrs['pydara']['items'][0]['synthetic']


def test_date_modes_and_empty_input():
    with sample_market_client() as client:
        assert isinstance(client.clients(ins_code=CODE,day='1404-01-01',calendar='jalali'),pd.DataFrame)
        assert isinstance(client.clients(ins_code=CODE,start='2024-01-01',end='2026-12-31'),pd.DataFrame)
        empty=client.clients(pd.DataFrame({'ins_code':pd.Series([],dtype='string')}))
        assert empty.empty and 'inscode' in empty
        with pytest.raises(InvalidArgumentError):client.clients(ins_code=CODE,day='2025-01-01',start='2024-01-01')
        with pytest.raises(InvalidArgumentError):client.clients(instrument='فولاد',ins_code=CODE)
        with pytest.raises(InvalidArgumentError):client.clients(ins_code=CODE,on_multiple='bad')


def test_collect_failures_and_old_names_not_public():
    with sample_market_client() as client:
        result=client.clients(['فولاد','no_such_instrument'])
        assert not result.empty
        assert len(result.attrs['pydara']['errors'])==1
        for old in ('get_client_types','get_client_type_history','get_client_types_many','get_client_type_history_many'):
            assert not hasattr(tse,old)
            assert not hasattr(client,old)


def test_async_clients():
    async def run():
        async with sample_market_async_client() as client:
            a=await client.clients(ins_code=[CODE,CODE]);b=await client.clients(await client.instrument(ins_code=CODE))
            assert len(a)==len(b)==1
            assert a.inscode.iloc[0]==CODE
    asyncio.run(run())
