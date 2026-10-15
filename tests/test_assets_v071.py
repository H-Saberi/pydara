"""Regression coverage for asset lookup syntax and network budget boundary."""
import pandas as pd
import pytest
from pydara import tse
from pydara.tse._core.exceptions import InvalidArgumentError, RequestBudgetExceededError


def test_positional_symbol_routes_through_named_search(monkeypatch):
    captured = []
    def fake(**kwargs):
        captured.append(kwargs)
        return pd.DataFrame({'ins_code':['123'], 'symbol':['فولاد']})
    monkeypatch.setattr(tse, '_legacy_instrument', fake)
    assert tse.assets('فولاد').iloc[0].symbol == 'فولاد'
    assert captured[0]['symbol'] == 'فولاد'
    assert tse.assets(symbol='فولاد').iloc[0].symbol == 'فولاد'


def test_explicit_codes_scalar_and_list_preserved(monkeypatch):
    seen=[]
    def fake(**kwargs):
        seen.append(kwargs['ins_code'])
        codes=kwargs['ins_code']
        return pd.DataFrame({'ins_code': codes if isinstance(codes,list) else [codes], 'symbol':['نماد'] * (len(codes) if isinstance(codes,list) else 1)})
    monkeypatch.setattr(tse, '_legacy_instrument', fake)
    assert len(tse.assets(ins_code=['123','456'])) == 2
    assert tse.assets(ins_code='123').iloc[0].inscode == '123'
    assert tse.assets('123').iloc[0].inscode == '123'
    assert seen == [['123','456'], '123', '123']


def test_missing_selector_lists_observed_catalog(monkeypatch):
    monkeypatch.setattr(tse._client(), 'get_instruments', lambda **kw: pd.DataFrame({'ins_code':['123'],'symbol':['الف'],'market':['TSE']}))
    assert list(tse.assets().symbol)==['الف']
    assert list(tse.assets(markets='TSE').symbol)==['الف']


def test_conflict_and_invalid_positional(monkeypatch):
    with pytest.raises(InvalidArgumentError):
        tse.assets('فولاد', symbol='فملی')
    with pytest.raises(InvalidArgumentError):
        tse.assets('فولاد', ins_code='123')
    with pytest.raises(InvalidArgumentError):
        tse.assets([])


def test_budget_error_not_swallowed(monkeypatch):
    def exhausted(**kwargs):
        raise RequestBudgetExceededError('This client\'s network request budget is exhausted.')
    monkeypatch.setattr(tse, '_legacy_instrument', exhausted)
    with pytest.raises(RequestBudgetExceededError):
        tse.assets(ins_code=['123','456'])
