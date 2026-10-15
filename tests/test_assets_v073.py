"""Regression tests: market labels can be incomplete in live watch feeds."""
import pandas as pd
from pydara import tse


def test_mixed_market_rows_returns_only_verified(monkeypatch):
    source = pd.DataFrame({'ins_code':['11','22','33','44'], 'symbol':['A','B','C','D'], 'market':['TSE',None,'IFB','TSE']})
    called = []
    def fetch(**kw):
        called.append(kw.get('market'))
        return source.copy()
    monkeypatch.setattr(tse._client(), 'get_instruments', fetch)
    found = tse.assets(markets='TSE')
    assert found.inscode.tolist() == ['11','44']
    assert found.attrs['pydara']['unknown_market_rows_excluded'] == 1
    assert found.attrs['pydara']['market_filter_incomplete'] is True
    assert called == ['TSE']


def test_without_markets_keeps_unknown_rows(monkeypatch):
    source = pd.DataFrame({'ins_code':['11','22'], 'symbol':['A','B'], 'market':['TSE',None]})
    monkeypatch.setattr(tse._client(), 'get_instruments', lambda **kw: source.copy())
    found = tse.assets()
    assert len(found) == 2


def test_requested_multiple_markets(monkeypatch):
    source = pd.DataFrame({'ins_code':['11','22','33'], 'symbol':['A','B','C'], 'market':['TSE',None,'IFB']})
    monkeypatch.setattr(tse._client(), 'get_instruments', lambda **kw: source.copy())
    found = tse.assets(markets=['TSE','IFB'])
    assert found.inscode.tolist() == ['11','33']
