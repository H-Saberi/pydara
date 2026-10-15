"""Offline regression for instrument result-count and conflicting-criteria policies."""
import asyncio
from types import SimpleNamespace
import pytest
from pydara.tse.samples import sample_client, sample_async_client
from pydara.tse._core.exceptions import (AmbiguousInstrumentError, InvalidArgumentError,
                                        UnknownInstrumentError)
from pydara.tse.instrument_lookup import matching_codes, select_codes, lookup_policies

FOLAD = '46348559193224090'


def test_default_and_explicit_cardinality():
    records = [SimpleNamespace(ins_code='2', symbol='فولاد'),
               SimpleNamespace(ins_code='1', symbol='فولاد'),
               SimpleNamespace(ins_code='2', symbol='فولاد')]
    codes = matching_codes(records, {'symbol': 'فولاد'}, True)
    assert codes == ('2', '1')
    assert select_codes(codes, 'all') == ('2', '1')
    assert select_codes(codes, 'first') == ('2',)
    with pytest.raises(AmbiguousInstrumentError) as exc:
        select_codes(codes, 'error')
    assert exc.value.candidates == ('2', '1')


def test_disagreement_modes_and_default():
    with sample_client() as client:
        with pytest.raises(UnknownInstrumentError):
            client.instrument(ins_code=FOLAD, symbol='wrong')
        frame = client.instrument(ins_code=FOLAD, symbol='wrong', on_conflict='ins_code')
        assert frame.ins_code.iloc[0] == FOLAD
        assert client.instrument(ins_code=FOLAD, on_multiple='all').shape[0] == 1
        assert client.instrument(ins_code=FOLAD, on_multiple='first').shape[0] == 1
        assert client.instrument(ins_code=FOLAD, on_multiple='error').shape[0] == 1


def test_unambiguous_search_all_works():
    with sample_client() as client:
        result = client.instrument(symbol='فولاد')
        assert len(result) == 1
        assert client.instrument(symbol='فولاد', on_multiple='first').ins_code.tolist() == result.ins_code.tolist()
        assert client.instrument(symbol='فولاد', on_multiple='error').ins_code.tolist() == result.ins_code.tolist()


def test_bad_policies_rejected_before_network():
    with sample_client() as client:
        for kw in [dict(on_multiple='random'), dict(on_multiple=None),
                   dict(on_multiple=1), dict(on_conflict='first'),
                   dict(on_conflict=None), dict(on_conflict='ins_code')]:
            with pytest.raises(InvalidArgumentError):
                client.instrument(symbol='فولاد', **kw)
        assert client.request_count == 0


def test_async_parity():
    async def run():
        async with sample_async_client() as client:
            with pytest.raises(UnknownInstrumentError):
                await client.instrument(ins_code=FOLAD, symbol='wrong')
            rows = await client.instrument(ins_code=FOLAD, symbol='wrong',
                                           on_conflict='ins_code')
            assert rows.ins_code.iloc[0] == FOLAD
            rows = await client.instrument(symbol='فولاد', on_multiple='all')
            assert len(rows) == 1
    asyncio.run(run())
