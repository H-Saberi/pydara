"""Large selected tables use bulk quotes without per-instrument requests."""
import pandas as pd
from pydara import tse
from pydara.tse import public_workflows


def test_prices_large_assets_single_bulk_call(monkeypatch):
    codes = [str(1000 + n) for n in range(30)]
    assets = pd.DataFrame({'inscode': codes, 'symbol': [f'S{n}' for n in range(30)]})
    seen = []
    def bulk(client, **kwargs):
        seen.append(kwargs)
        result = pd.DataFrame({
            'inscode': codes[::-1], 'symbol': assets.symbol.tolist()[::-1],
            'closingprice': [200.0] * 30, 'date': ['2026-10-14'] * 30, 'return': [0.1] * 30,
            'returnpct': [10.0] * 30, 'change': [20.0] * 30,
        })
        result.attrs['pydara'] = {'source': 'test', 'synthetic': True}
        return result
    monkeypatch.setattr(public_workflows, 'quote_watch', bulk)
    def forbid(*args, **kwargs):
        raise AssertionError('Unexpected N individual quote requests')
    monkeypatch.setattr(tse, '_legacy_price', forbid)
    result = tse.prices(assets)
    assert result.inscode.tolist() == codes
    assert len(seen) == 1
    assert result.attrs['pydara']['selection'] == 'bulk_watch_then_validated_quote_repair'
    assert result.attrs['pydara']['requested_assets'] == 30
    assert result.attrs['pydara']['unmatched_assets'] == []


def test_prices_small_assets_uses_old_individual_path(monkeypatch):
    assets = pd.DataFrame({'inscode':['1001'], 'symbol':['S1']})
    def individual(*args, **kwargs):
        return pd.DataFrame({'ins_code':['1001'], 'closing_price':[200]})
    monkeypatch.setattr(tse, '_legacy_price', individual)
    result = tse.prices(assets, include_queues=False)
    assert result.inscode.tolist() == ['1001']
