"""Public assets multi-symbol and market source fallback regression tests."""
import pandas as pd
import pytest
from pydara import tse
from pydara.tse._core.exceptions import InvalidArgumentError, UnsupportedCapabilityError


def test_multiple_symbols_and_dedup(monkeypatch):
    visited=[]
    def lookup(**kw):
        visited.append(kw['symbol'])
        return pd.DataFrame({'ins_code':[str(len(visited))], 'symbol':[kw['symbol']], 'market':['TSE']})
    monkeypatch.setattr(tse, '_legacy_instrument', lookup)
    result=tse.assets(symbol=['فولاد','وبملت','فولاد'],markets='TSE')
    assert result.symbol.tolist()==['فولاد','وبملت']
    assert visited==['فولاد','وبملت']

@pytest.mark.parametrize('bad', [[], ['فولاد', ''], ['فولاد', 42], 42])
def test_invalid_symbol_list(bad):
    with pytest.raises(InvalidArgumentError):
        tse.assets(symbol=bad)

def test_watch_missing_market_retries_legacy(monkeypatch):
    seen=[]
    def get_instruments(**kw):
        seen.append(kw.get('backend', 'auto'))
        if kw.get('backend')=='legacy':
            return pd.DataFrame({'ins_code':['1'], 'symbol':['الف'], 'market':['TSE']})
        raise UnsupportedCapabilityError('The response does not identify each row market; use backend="legacy" or omit market. No market is guessed.')
    monkeypatch.setattr(tse._client(),'get_instruments',get_instruments)
    assert tse.assets(markets='TSE').inscode.tolist()==['1']
    assert seen==['auto','legacy']

def test_watch_missing_market_not_guessed(monkeypatch):
    def get_instruments(**kw):
        return pd.DataFrame({'ins_code':['1'],'symbol':['الف'],'market':[None]})
    monkeypatch.setattr(tse._client(),'get_instruments',get_instruments)
    result = tse.assets(markets='TSE')
    assert result.empty
    assert result.attrs['pydara']['unknown_market_rows_excluded'] == 1

def test_market_keyword_removed():
    with pytest.raises(TypeError):
        tse.assets(market='TSE')
