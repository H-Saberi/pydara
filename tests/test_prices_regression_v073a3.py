import pandas as pd
from pydara import tse
from pydara.tse import public_workflows


def test_returns_no_false_minus_100_on_zero_close():
    inp = pd.DataFrame({'closingprice': [0, -1, 105, 0], 'previousreferenceprice': [100, 100, 100, 0]})
    result = public_workflows.returns(inp)
    assert pd.isna(result.loc[0, 'returnpct'])
    assert pd.isna(result.loc[0, 'change'])
    assert pd.isna(result.loc[1, 'return'])
    assert result.loc[2, 'returnpct'] == 5
    assert pd.isna(result.loc[3, 'returnpct'])


def test_prices_bulk_preserves_market_and_reports_conflicts(monkeypatch):
    codes = [str(1000 + i) for i in range(21)]
    assets = pd.DataFrame({'inscode': codes, 'market': ['TSE'] * 21})
    def fake(*args, **kwargs):
        f = pd.DataFrame({'inscode': codes, 'market': [pd.NA] * 20 + ['IFB'],
                          'closingprice': [0] * 21, 'previousreferenceprice': [100] * 21})
        return public_workflows.returns(f)
    monkeypatch.setattr(public_workflows, 'quote_watch', fake)
    result = tse.prices(assets=assets, max_quote_fallback=0)
    assert result.loc[0, 'market'] == 'TSE'
    assert result.loc[20, 'market'] == 'IFB'
    assert result.attrs['pydara']['asset_market_filled'] == 20
    assert result.attrs['pydara']['asset_market_conflicts'] == 1
    assert result['returnpct'].isna().all()


def test_prices_individual_preserves_market(monkeypatch):
    assets = pd.DataFrame({'inscode': ['123'], 'market': ['TSE']})
    def fake(*args, **kwargs):
        return pd.DataFrame({'ins_code': ['123'], 'market': [pd.NA],
                             'closing_price': [0], 'previous_reference_price': [90]})
    monkeypatch.setattr(tse, '_legacy_price', fake)
    result = tse.prices(assets=assets, include_queues=False)
    assert result.loc[0, 'market'] == 'TSE'
    assert pd.isna(result.loc[0, 'returnpct'])
