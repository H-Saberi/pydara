"""Regression contract for the short instrument identity API; offline only."""
import asyncio
import pytest
from pydara import tse as data
from pydara.tse.samples import sample_client, sample_async_client
from pydara.tse._core.exceptions import (UnknownInstrumentError, InvalidArgumentError,
                                        AmbiguousInstrumentError, UnsupportedCapabilityError)
from pydara.tse._core.models import Market

FOLAD = "46348559193224090"


def test_exact_code_and_constraints():
    with sample_client() as client:
        result = client.instrument(ins_code=FOLAD, symbol="فولاد", market=Market.TSE)
        assert len(result) == 1
        assert result.ins_code.iloc[0] == FOLAD
        assert client.instrument(symbol="فولاد").ins_code.iloc[0] == FOLAD
        assert client.resolve_instrument(ins_code=FOLAD).ins_code.iloc[0] == FOLAD
        with pytest.raises(UnknownInstrumentError):
            client.instrument(ins_code=FOLAD, symbol="شستا")
        with pytest.raises(UnknownInstrumentError):
            client.instrument(ins_code=FOLAD, market=Market.IFB)
        with pytest.raises(UnknownInstrumentError):
            client.instrument(ins_code=FOLAD, name="نام نادرست")


def test_invalid_inputs_prior_to_http():
    with sample_client() as client:
        for params in ({}, {"ins_code": True}, {"ins_code": "123.4"},
                       {"strict": False}, {"symbol": " "}, {"is_active": 1, "ins_code": FOLAD},
                       {"ins_code": FOLAD, "strict": 2}):
            with pytest.raises(InvalidArgumentError):
                client.instrument(**params)
        with pytest.raises(UnsupportedCapabilityError):
            client.instrument(company_cisin="IRO1FOLD0001")
        assert client.request_count == 0


def test_ambiguity_never_picks_first(monkeypatch):
    from pydara.tse.instrument_lookup import candidates_from_search
    from types import SimpleNamespace
    candidates = [SimpleNamespace(ins_code="1", symbol="فولاد"),
                  SimpleNamespace(ins_code="2", symbol="فولاد")]
    with pytest.raises(AmbiguousInstrumentError) as exc:
        candidates_from_search(candidates, {"symbol": "فولاد"}, True)
    assert exc.value.candidates == ("1", "2")


def test_module_short_names_exist():
    for name in ("assets", "markets", "prices", "history", "traders", "orders", "search", "catalog"):
        assert callable(getattr(data, name))
    assert not hasattr(data, "instrument")


def test_async_parity():
    async def run():
        async with sample_async_client() as client:
            frame = await client.instrument(ins_code=FOLAD, symbol="فولاد")
            assert frame.ins_code.iloc[0] == FOLAD
            frame2 = await client.resolve_instrument(ins_code=FOLAD)
            assert frame2.ins_code.iloc[0] == FOLAD
    asyncio.run(run())


def test_multi_code_inputs_sync_and_public_removal():
    from pydara import tse
    assert not hasattr(tse, 'get_instrument')
    with sample_client() as client:
        values = [FOLAD, FOLAD]
        frame = client.instrument(ins_code=values)
        assert frame.ins_code.tolist() == [FOLAD]
        for bad in ([], [FOLAD, 'bad'], [[FOLAD]], [1.2], [True]):
            with pytest.raises(InvalidArgumentError):
                client.instrument(ins_code=bad)
        assert client.instrument(ins_code=values, on_multiple='first').ins_code.tolist() == [FOLAD]


def test_multi_code_inputs_async():
    async def run():
        async with sample_async_client() as client:
            frame = await client.instrument(ins_code=[FOLAD, FOLAD])
            assert frame.ins_code.tolist() == [FOLAD]
    asyncio.run(run())
