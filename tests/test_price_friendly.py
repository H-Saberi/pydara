"""Offline tests for the public price DataFrame workflow."""
import asyncio
import pandas as pd
import pytest
from pydara.tse.samples import sample_client, sample_async_client
from pydara.tse._core.exceptions import InvalidArgumentError
CODE='46348559193224090'

def test_price_dataframe_and_code_list():
    with sample_client() as client:
        instruments=client.instrument(ins_code=[CODE,CODE])
        by_frame=client.price(instruments)
        by_codes=client.price(ins_code=[CODE,CODE])
        assert len(by_frame)==len(by_codes)==1
        for frame in (by_frame,by_codes):
            assert {'state','is_active','fetched_at','source_timestamp','last_price','closing_price','ins_code'} <= set(frame.columns)
            assert frame.ins_code.iloc[0]==CODE
            assert pd.notna(frame.fetched_at.iloc[0])
            assert frame.attrs['pydara']['errors']==[]

def test_price_invalid_and_empty():
    with sample_client() as client:
        with pytest.raises(InvalidArgumentError):client.price(ins_code=[CODE],instrument='فولاد')
        with pytest.raises(InvalidArgumentError):client.price(ins_code=[])
        assert client.price(pd.DataFrame({'ins_code':pd.Series([],dtype='string')})).empty

def test_async_price():
    async def run():
        async with sample_async_client() as client:
            data=await client.price(ins_code=[CODE,CODE])
            assert len(data)==1
            assert 'is_active' in data and 'fetched_at' in data
    asyncio.run(run())
