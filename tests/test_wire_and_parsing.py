from copy import deepcopy
from datetime import timedelta
import json
import time

import httpx
import pytest

from pydara.tse import Client, ClientConfig, NetworkConfig, InstrumentRef
from pydara.tse.samples import sample_transport
from pydara.tse.exceptions import *

FOLAD = "\u0641\u0648\u0644\u0627\u062f"
CODE = "46348559193224090"

def make(handler, **network):
    return Client(storage=False, config=ClientConfig(network=NetworkConfig(
        requests_per_second=1_000_000, max_retries=0, **network)),
        transport=httpx.MockTransport(handler))


@pytest.mark.parametrize("content", [b"<!doctype html><html></html>", b"", b"NOT JSON",
    b'{"other":[]}', b'{"instrumentSearch":null}', b'{"instrumentSearch":[],"instrumentSearch":[]}'])
def test_bad_search_response_not_empty_table(content):
    with make(lambda r: httpx.Response(200, content=content)) as c:
        with pytest.raises(SchemaMismatchError):
            c.search_instruments(FOLAD)


@pytest.mark.parametrize("status,error", [(401,AuthenticationError),(403,PermissionDeniedError),
    (404,ApiError),(302,ApiError),(429,RateLimitError),(503,ServiceUnavailableError)])
def test_status_mapping(status,error):
    with make(lambda r: httpx.Response(status)) as c:
        with pytest.raises(error):
            c.search_instruments(FOLAD)
        assert c.request_count == 1


def test_response_size_limit():
    with make(lambda r: httpx.Response(200, content=b"{" + b"x"*200), max_response_bytes=50) as c:
        with pytest.raises(SchemaMismatchError):
            c.search_instruments(FOLAD)


def test_request_budget():
    base = sample_transport()
    with make(base.handle_request, request_budget=1) as c:
        with pytest.raises(RequestBudgetExceededError):
            c.get_quote(FOLAD)
        assert c.request_count == 1


def test_no_history_dependency_and_direct_code_needs_two_requests():
    base = sample_transport()
    with make(base.handle_request) as c:
        assert c.get_quote(InstrumentRef.by_ins_code(CODE)).instrument.ins_code == CODE
        assert c.request_count == 2


def test_ambiguous_symbol_is_explicit():
    base = sample_transport()
    def handler(r):
        data = json.loads(base.handle_request(r).content)
        if "instrumentSearch" in data:
            other = deepcopy(data["instrumentSearch"][0]); other["insCode"] = "12345"
            data["instrumentSearch"].append(other)
        return httpx.Response(200, json=data)
    with make(handler) as c:
        with pytest.raises(AmbiguousInstrumentError) as caught:
            c.get_quote(FOLAD)
        assert len(caught.value.candidates) == 2


def change_quote(change):
    base = sample_transport()
    def handler(r):
        response = base.handle_request(r)
        data = json.loads(response.content)
        if "closingPriceInfo" in data:
            change(data["closingPriceInfo"])
        return httpx.Response(200, json=data)
    return handler


@pytest.mark.parametrize("field,val,error", [("insCode",123.4,SchemaMismatchError),
    ("insCode","1",DataQualityError),("pDrCotVal",-1,DataQualityError),
    ("pClosing","oops",SchemaMismatchError),("zTotTran",1.5,DataQualityError),
    ("dEven",20241399,SchemaMismatchError),("hEven",256000,SchemaMismatchError),
    ("priceMin",999999,DataQualityError)])
def test_invalid_quote_field(field,val,error):
    with make(change_quote(lambda q: q.update({field:val}))) as c:
        with pytest.raises(error):
            c.get_quote(FOLAD)


def test_missing_price_is_none_not_zero():
    with make(change_quote(lambda q:q.update(pDrCotVal=None))) as c:
        assert c.get_quote(FOLAD).last_price is None
        with pytest.raises(MissingValueError):
            c.get_price(FOLAD)


def test_unknown_unit_is_not_labeled_rial():
    base = sample_transport()
    def handler(r):
        data = json.loads(base.handle_request(r).content)
        if "instrumentInfo" in data:
            data["instrumentInfo"]["yVal"] = "999999"
        return httpx.Response(200, json=data)
    with make(handler) as c:
        assert c.get_quote(FOLAD).instrument.currency is None
        with pytest.raises(UnsupportedQuoteUnitError):
            c.get_price(FOLAD)


def test_retry_is_bounded_and_succeeds(monkeypatch):
    base = sample_transport(); calls = []
    def handler(r):
        calls.append(r.url.path)
        return httpx.Response(503) if len(calls) == 1 else base.handle_request(r)
    cfg=ClientConfig(network=NetworkConfig(requests_per_second=1_000_000,max_retries=1))
    with Client(storage=False,config=cfg,transport=httpx.MockTransport(handler)) as c:
        monkeypatch.setattr(c._wire, "pause", lambda *a: 0)
        assert not c.search_instruments(FOLAD).empty
        assert c.request_count == 2


def test_retry_after_not_ignored():
    cfg=ClientConfig(network=NetworkConfig(requests_per_second=1_000_000,max_retries=2,operation_timeout=.2))
    with Client(storage=False,config=cfg,transport=httpx.MockTransport(
            lambda r:httpx.Response(429,headers={"Retry-After":"60"}))) as c:
        start=time.monotonic()
        with pytest.raises(RateLimitError):
            c.search_instruments(FOLAD)
        assert c.request_count == 1
        assert time.monotonic()-start < 1


@pytest.mark.parametrize("missing_code", [None, ""])
def test_nullable_quote_identifier_accepted_with_quality_flag(missing_code):
    with make(change_quote(lambda q: q.update({"insCode": missing_code}))) as c:
        quote = c.get_quote(FOLAD)
        assert quote.instrument.ins_code == CODE
        assert "quote_response_identifier_missing" in quote.meta.quality_flags


def test_nullable_identifier_does_not_disable_mismatch_protection():
    with make(change_quote(lambda q: q.update({"insCode": "99999"}))) as c:
        with pytest.raises(DataQualityError):
            c.get_quote(FOLAD)


@pytest.mark.parametrize("wire", [4.634855919322409e16, "4.634855919322409e+16", "46348559193224090.0"])
def test_scientific_quote_identifier_matches_verified_request_with_warning(wire):
    with make(change_quote(lambda q: q.update({"insCode": wire}))) as c:
        quote = c.get_quote(FOLAD)
        assert quote.instrument.ins_code == CODE
        assert "quote_response_identifier_rounded_or_scientific" in quote.meta.quality_flags


@pytest.mark.parametrize("wire", [4.634855919322411e16, "4.634855919322411e+16", "46348559193224091.0"])
def test_scientific_quote_identifier_mismatch_rejected(wire):
    with make(change_quote(lambda q: q.update({"insCode": wire}))) as c:
        with pytest.raises(DataQualityError):
            c.get_quote(FOLAD)


def test_scientific_nonintegral_identifier_rejected():
    with make(change_quote(lambda q: q.update({"insCode": "12.34"}))) as c:
        with pytest.raises(SchemaMismatchError):
            c.get_quote(FOLAD)


@pytest.mark.parametrize("missing_code", ["0", 0, "0.0", "0E+0"])
def test_zero_quote_identifier_placeholder_from_live_tsetmc(missing_code):
    # Regression: GetClosingPriceInfo for Folad returned insCode as string "0".
    # Identity must still come from previously verified GetInstrumentInfo.
    with make(change_quote(lambda q: q.update({"insCode": missing_code}))) as c:
        quote = c.get_quote(FOLAD)
        assert quote.instrument.ins_code == CODE
        assert "quote_response_identifier_zero_placeholder" in quote.meta.quality_flags
        assert c.get_price(FOLAD) == quote.last_price


def test_zero_quote_identifier_not_accepted_as_instrument_identity():
    base = sample_transport()
    def handler(request):
        data = json.loads(base.handle_request(request).content)
        if "instrumentInfo" in data:
            data["instrumentInfo"]["insCode"] = "0"
        return httpx.Response(200, json=data)
    with make(handler) as c:
        with pytest.raises(SchemaMismatchError):
            c.get_quote(FOLAD)
