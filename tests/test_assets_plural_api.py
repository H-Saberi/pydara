"""Offline behavior contract for the new plural public facade."""
import pandas as pd
import pytest
from pydara import tse


def test_public_plural_names_and_docs():
    for name in ('assets', 'prices', 'traders', 'history'):
        fn = getattr(tse, name)
        assert callable(fn) and fn.__doc__ and 'Args:' in fn.__doc__
    assert not hasattr(tse, 'instrument')
    assert not hasattr(tse, 'clients')
    assert not hasattr(tse, 'price')


def test_assets_listing_and_filters(monkeypatch):
    sample = pd.DataFrame({'ins_code':['123','456'], 'symbol':['الف','ب'],
                           'sector_code':['10','20'], 'market':['TSE','TSE']})
    monkeypatch.setattr(tse._client(), 'get_instruments', lambda **kwargs: sample.copy())
    df = tse.assets()
    assert list(df['inscode']) == ['123','456']
    assert 'ins_code' not in df.columns
    assert list(tse.assets(industry_code='10')['symbol']) == ['الف']
    assert tse.assets(on_multiple='first').shape[0] == 1
    assert 'complete historical' in df.attrs['pydara']['coverage_note']


def test_assets_to_prices_and_traders(monkeypatch):
    source=pd.DataFrame({'inscode':['123'], 'symbol':['الف']})
    monkeypatch.setattr(tse, '_legacy_price',lambda assets, **kwargs: assets.assign(last_price=100))
    monkeypatch.setattr(tse, '_legacy_clients',lambda assets, **kwargs: assets.assign(i_buy_volume=20))
    assert list(tse.prices(source)['inscode']) == ['123']
    assert 'lastprice' in tse.prices(source)
    assert 'ibuyvolume' in tse.traders(source)


def test_history_accepts_new_assets_keyword(monkeypatch):
    monkeypatch.setattr(tse._client(), 'history',lambda assets, **kwargs: assets.assign(closing_price=10))
    frame=tse.history(assets=pd.DataFrame({'inscode':['123']}))
    assert 'closingprice' in frame
