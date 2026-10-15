from datetime import timedelta, datetime, UTC
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest
import httpx

from pydara.tse import (
    Client, ClientConfig, NetworkConfig, StorageConfig, FreshnessPolicy, FetchPolicy,
    InstrumentRef, Market,
)
from pydara.tse.samples import sample_client, sample_transport
from pydara.tse.exceptions import *

FOLAD = "\u0641\u0648\u0644\u0627\u062f"
SHASTA = "\u0634\u0633\u062a\u0627"
CODE = "46348559193224090"
FAST = ClientConfig(network=NetworkConfig(requests_per_second=1_000_000, max_retries=0))


def test_quote_does_not_request_history():
    base = sample_transport()
    paths = []
    def handler(r):
        paths.append(r.url.path)
        return base.handle_request(r)
    with Client(config=FAST, storage=False, transport=httpx.MockTransport(handler)) as c:
        q = c.get_quote(FOLAD)
        assert q.last_price == Decimal("1234.5")
        assert len(paths) == 3
        assert all("History" not in p and "LastPossibleDeven" not in p for p in paths)
        assert q.source_timestamp.tzinfo is not None
        assert q.meta.available_at == q.retrieved_at
        assert q.timestamp_kind == "unknown"
        assert "source_date_not_today" in q.meta.quality_flags


def test_identity_and_quotes_are_immutable():
    from dataclasses import FrozenInstanceError
    with sample_client() as c:
        q = c.get_quote(FOLAD)
        with pytest.raises(FrozenInstanceError):
            q.last_price = 1
        with pytest.raises(FrozenInstanceError):
            q.instrument.ins_code = "1"


def test_long_identifier_preserved():
    with sample_client() as c:
        q = c.get_quote(SHASTA)
        assert q.instrument.ins_code == "9007199254740993"
        frame = q.to_frame()
        assert frame.loc[0, "ins_code"] == "9007199254740993"
        assert str(frame["ins_code"].dtype) == "string"


def test_batch_preserves_order_duplicates_and_errors():
    with sample_client() as c:
        frame = c.get_quotes([FOLAD, "DOES_NOT_EXIST", FOLAD], on_error="collect")
        assert frame["request_index"].tolist() == [0, 1, 2]
        assert frame["input_symbol"].tolist() == [FOLAD, "DOES_NOT_EXIST", FOLAD]
        assert frame["status"].tolist() == ["ok", "error", "ok"]
        assert pd.isna(frame.loc[1, "last_price"])
        assert frame.loc[1, "error_code"] == "UnknownInstrumentError"


def test_batch_raise_attaches_partial_result():
    with sample_client() as c:
        with pytest.raises(BatchDataError) as caught:
            c.get_quotes([FOLAD, "NO", SHASTA])
        assert len(caught.value.partial_result) == 2
        assert caught.value.partial_result.iloc[-1]["status"] == "error"


def test_empty_search_is_typed_not_a_network_failure():
    with sample_client() as c:
        df = c.search_instruments("NOT_PRESENT")
        assert df.empty
        assert str(df["ins_code"].dtype) == "string"
        assert str(df["is_active"].dtype) == "boolean"
        assert df.attrs["pydara"]["coverage_status"] == "unknown"


def test_prices_have_separate_meanings():
    with sample_client() as c:
        assert c.get_price(FOLAD) == Decimal("1234.5")
        assert c.get_price(FOLAD, field="closing") == Decimal("1225")
        assert c.get_price(FOLAD, field="previous_reference") == Decimal("1200")


def test_unknown_instrument_not_first_search_result():
    with sample_client() as c:
        with pytest.raises(UnknownInstrumentError):
            c.get_quote(FOLAD[:2])


def test_market_constraint_checked():
    with sample_client() as c:
        with pytest.raises(UnknownInstrumentError):
            c._resolve_instrument_record(InstrumentRef.by_ins_code(CODE), market=Market.IFB)


def test_historical_identity_explicitly_unimplemented():
    with sample_client() as c:
        with pytest.raises(PointInTimeUnavailableError):
            c._resolve_instrument_record(FOLAD, known_at=datetime.now(UTC))
        assert c.request_count == 0


def test_isin_lookup_does_not_guess():
    with sample_client() as c:
        with pytest.raises(UnsupportedCapabilityError):
            c._resolve_instrument_record(InstrumentRef.by_isin("IRO1FOLD0001"))


def test_stale_source_guard():
    with sample_client() as c:
        with pytest.raises(StaleDataError):
            c.get_quote(FOLAD, freshness=FreshnessPolicy(max_source_age=timedelta(seconds=30)))


def test_exact_profile():
    with sample_client() as c:
        q = c.get_quote(FOLAD)
        frame = q.to_frame(numeric="exact")
        assert isinstance(frame.loc[0, "last_price"], Decimal)
        assert frame.loc[0, "last_price"] == Decimal("1234.5")


def test_returned_frame_cannot_mutate_cache():
    with sample_client() as c:
        df = c.search_instruments(FOLAD)
        df.loc[0, "symbol"] = "wrong"
        assert c._resolve_instrument_record(FOLAD).symbol == FOLAD


def test_closed_client_rejected():
    c = sample_client()
    c.close()
    c.close()
    with pytest.raises(ClosedClientError):
        c.get_quote(FOLAD)


@pytest.mark.parametrize("value", [None, 12, "", "  ", "bad/id", "12.0", "-1", "0", True])
def test_bad_ins_code(value):
    with pytest.raises(ConfigurationError):
        InstrumentRef.by_ins_code(value)


@pytest.mark.parametrize("options", [dict(max_retries=-1), dict(connect_timeout=0),
    dict(requests_per_second=float("nan")), dict(max_concurrency=True), dict(request_budget=0)])
def test_invalid_network_options(options):
    with pytest.raises(ConfigurationError):
        NetworkConfig(**options)


@pytest.mark.parametrize("instruments", [FOLAD, [], 1, [123], None])
def test_invalid_batch(instruments):
    with sample_client() as c:
        with pytest.raises(InvalidArgumentError):
            c.get_quotes(instruments)


def test_official_api_is_not_faked():
    with pytest.raises(UnsupportedCapabilityError):
        Client(source="official")


def test_import_and_constructor_do_not_create_data_or_threads(tmp_path):
    script = r'''
import sys, threading, socket, pathlib
before = {t.ident for t in threading.enumerate()}
socket.socket.connect = lambda *a, **k: (_ for _ in ()).throw(AssertionError('network'))
import pydara
from pydara import tse as data
assert pydara.__all__ == ['tse', '__version__']
assert not hasattr(pydara, 'analytics') and not hasattr(pydara, 'ml')
c = data.Client(data_dir=sys.argv[1])
assert not pathlib.Path(sys.argv[1]).exists()
assert {t.ident for t in threading.enumerate()} == before
assert 'sklearn' not in sys.modules and 'torch' not in sys.modules
c.close()
'''
    subprocess.run([sys.executable, "-c", script, str(tmp_path / "not_created")], check=True, timeout=20)


def test_cleanup_does_not_mask_user_error(monkeypatch):
    c=sample_client()
    monkeypatch.setattr(c._wire,'close',lambda: (_ for _ in ()).throw(RuntimeError('cleanup')))
    with pytest.raises(ValueError,match='original'):
        with c:
            raise ValueError('original')


@pytest.mark.parametrize('kwargs',[{'source':''},{'mode':''}])
def test_empty_setting_is_not_silently_defaulted(kwargs):
    with pytest.raises(ConfigurationError):Client(**kwargs)
