"""Offline end-to-end coverage for public unified history selectors."""
import asyncio
import pandas as pd
import pytest
from pydara.tse.samples import sample_client, sample_async_client
from pydara.tse._core.exceptions import InvalidArgumentError, UnknownInstrumentError

CODE='46348559193224090'
SYMBOL='فولاد'


def test_four_input_modes_and_unique_rows():
    with sample_client() as client:
        refs=client.instrument(symbol=SYMBOL)
        inputs=[SYMBOL, [SYMBOL, SYMBOL], refs, None]
        results=[]
        for value in inputs:
            kwargs={'ins_code':CODE} if value is None else {'instrument':value}
            out=client.history(**kwargs, start='2024-01-01',end='2025-12-31')
            assert isinstance(out,pd.DataFrame)
            assert not out.empty
            assert out.ins_code.eq(CODE).all()
            assert out.attrs['pydara']['failed_items']==0
            results.append(out)
        assert len(results[0])==len(results[1])==len(results[2])==len(results[3])


def test_code_conflict_policy_and_collection():
    with sample_client() as client:
        with pytest.raises(UnknownInstrumentError):
            client.history(ins_code=CODE,symbol='wrong',on_error='raise')
        out=client.history(ins_code=CODE,symbol='wrong',on_conflict='ins_code')
        assert not out.empty
        frame=pd.DataFrame({'ins_code':[CODE,CODE],'symbol':[SYMBOL,SYMBOL]})
        assert len(client.history(frame))==len(out)
        failed=client.history([SYMBOL,'nonexistent-some-symbol'])
        assert len(failed.attrs['pydara']['errors'])==1
        assert not failed.empty


def test_invalid_input_and_empty_dataframe():
    with sample_client() as client:
        with pytest.raises(InvalidArgumentError):client.history(pd.DataFrame({'symbol':[SYMBOL]}))
        with pytest.raises(InvalidArgumentError):client.history(ins_code=CODE,instrument=SYMBOL)
        with pytest.raises(InvalidArgumentError):client.history(SYMBOL,on_multiple='bogus')
        empty=client.history(pd.DataFrame({'ins_code':pd.Series([],dtype='string')}))
        assert empty.empty
        assert 'ins_code' in empty


def test_async_input_parity():
    async def run():
        async with sample_async_client() as client:
            frame=await client.instrument(symbol=SYMBOL)
            result=await client.history(frame)
            code=await client.history(ins_code=CODE)
            many=await client.history([SYMBOL,SYMBOL])
            assert len(result)==len(code)==len(many)
            assert result.ins_code.eq(CODE).all()
    asyncio.run(run())


def test_keyword_multi_codes_with_dedup_and_conflict():
    with sample_client() as client:
        result=client.history(ins_code=[CODE,CODE], start='2024-01-01',end='2025-12-31')
        single=client.history(ins_code=CODE, start='2024-01-01',end='2025-12-31')
        assert len(result)==len(single)
        assert result.attrs['pydara']['failed_items']==0
        with pytest.raises(UnknownInstrumentError):
            client.history(ins_code=[CODE], symbol='wrong', on_error='raise')
        assert not client.history(ins_code=[CODE],symbol='wrong',on_conflict='ins_code').empty


def test_keyword_multi_codes_async():
    async def run():
        async with sample_async_client() as client:
            result=await client.history(ins_code=[CODE,CODE])
            single=await client.history(ins_code=CODE)
            assert len(result)==len(single)
    asyncio.run(run())
