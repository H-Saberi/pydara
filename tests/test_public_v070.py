"""Offline API contracts for the market -> assets -> prices/orders workflows."""
from decimal import Decimal
import pandas as pd
import pytest
from pydara import tse
from pydara.tse._core.exceptions import InvalidArgumentError


def _sample_watch():
    f = pd.DataFrame([
        {'ins_code':'123','symbol':'الف','market':'TSE','sector_code':'10',
         'closing_price':110,'previous_reference_price':100,'last_price':111,
         'volume':1200, 'turnover':13000, 'trade_count':20,
         'min_allowed_price':90,'max_allowed_price':120,
         'bid_price_1':120,'ask_price_1':0,'bid_volume_1':1000,'ask_volume_1':0,
         'fetched_at':pd.Timestamp('2026-10-15T10:00:00Z')},
        {'ins_code':'456','symbol':'ب','market':'TSE','sector_code':'20',
         'closing_price':80,'previous_reference_price':100,'last_price':80,
         'volume':1500, 'turnover':20000, 'trade_count':15,
         'min_allowed_price':90,'max_allowed_price':120,
         'bid_price_1':0,'ask_price_1':90,'bid_volume_1':0,'ask_volume_1':500,
         'fetched_at':pd.Timestamp('2026-10-15T10:00:00Z')},
        {'ins_code':'789','symbol':'ج','market':'IFB','sector_code':'20',
         'closing_price':None,'previous_reference_price':None,'last_price':None,
         'volume':0,'turnover':0,'trade_count':0,
         'min_allowed_price':None,'max_allowed_price':None,
         'bid_price_1':None,'ask_price_1':None,'bid_volume_1':None,'ask_volume_1':None,
         'fetched_at':pd.Timestamp('2026-10-15T10:00:00Z')},
    ])
    f.attrs['pydara']={'schema_id':'market_watch','from_cache':True,'is_stale':True,'synthetic':True}
    return f


def _fake(monkeypatch):
    client=tse._client()
    watch = _sample_watch()
    def get_watch(*,market=None,**kwargs):
        f=watch.copy()
        if market is not None:f=f[f.market==str(market)].copy()
        f.attrs.update(watch.attrs)
        return f
    def get_overview(*,market,**kwargs):
        f=pd.DataFrame([{'market':market,'date':'2026-10-15','index_value':1000,
                         'turnover':100000,'volume':50000,'trade_count':30,
                         'fetched_at':pd.Timestamp('2026-10-15T10:01:00Z')}])
        f.attrs['pydara']={'synthetic':True,'is_stale':True}
        return f
    def clients(*,market=None,**kwargs):
        f=pd.DataFrame({'individual_buy_value':[Decimal('200.0')],
                        'individual_sell_value':[Decimal('140.0')]})
        f.attrs['pydara']={'synthetic':True}
        return f
    def get_instruments(*,market=None,**kwargs):
        f=watch[['ins_code','symbol','market','sector_code']].copy()
        if market is not None:f=f[f.market==str(market)].copy()
        return f
    def get_book(ref,**kwargs):
        f=pd.DataFrame([{'ins_code':ref.value,'symbol':'الف','depth':1,
                         'bid_price':120,'ask_price':0,'bid_volume':1000,
                         'ask_volume':0,'bid_order_count':12,'ask_order_count':0,
                         'date':pd.Timestamp('2026-10-15')}])
        f.attrs['pydara']={'synthetic':True}
        return f
    monkeypatch.setattr(client,'get_market_watch',get_watch)
    monkeypatch.setattr(client,'get_market_overview',get_overview)
    monkeypatch.setattr(client,'get_market_client_types',clients)
    monkeypatch.setattr(client,'get_instruments',get_instruments)
    monkeypatch.setattr(client,'get_market_order_book',lambda **k: get_book(type('R',(),{'value':'123'})()))
    monkeypatch.setattr(client,'get_order_book',get_book)
    monkeypatch.setattr(client,'get_order_book_history',lambda ref,**k:get_book(ref))


def test_market_asset_price_chain(monkeypatch):
    _fake(monkeypatch)
    markets=tse.markets()
    assert list(markets.market)==['TSE','IFB']
    assert list(markets.positive)[0] == 1
    assert list(markets.negative)[0] == 1
    assert markets.iloc[0]['buyqueues']==1
    assert markets.iloc[0]['sellqueues']==1
    assert markets.iloc[0]['netreal']==Decimal(60)
    assert markets.attrs['pydara']['synthetic'] is True
    selected=tse.assets(markets=markets,industry_code='10')
    assert list(selected.inscode)==['123']
    prices=tse.prices(markets=markets)
    assert set(prices.inscode)=={'123','456','789'}
    assert prices.loc[prices.inscode=='123','return'].iloc[0] == pytest.approx(0.1)
    assert prices.loc[prices.inscode=='123','returnpct'].iloc[0] == pytest.approx(10.0)
    assert prices.loc[prices.inscode=='456','change'].iloc[0] == pytest.approx(-20)
    assert pd.isna(prices.loc[prices.inscode=='789','return'].iloc[0])
    assert prices.loc[prices.inscode=='123','buyqueue'].iloc[0] == 1000
    assert prices.loc[prices.inscode=='456','sellqueue'].iloc[0] == 500
    assert not any('_' in c for c in selected.columns)
    assert not any('_' in c for c in markets.columns)
    assert not any('_' in c for c in prices.columns)


def test_bulk_prices_missing_prices_are_unknown(monkeypatch):
    _fake(monkeypatch)
    frame=tse.prices(markets='IFB')
    assert len(frame)==1
    assert pd.isna(frame.iloc[0]['return'])
    assert pd.isna(frame.iloc[0]['buyqueue'])


def test_market_selector_conflict_and_shape(monkeypatch):
    _fake(monkeypatch)
    assert list(tse.assets(markets=['TSE']).inscode)==['123','456']
    assert list(tse.assets(markets=tse.markets(market='TSE')).inscode)==['123','456']
    with pytest.raises(InvalidArgumentError):
        tse.assets(markets=pd.DataFrame({'nonmarket':['TSE']}))


def test_order_levels_and_validation(monkeypatch):
    _fake(monkeypatch)
    assets=pd.DataFrame({'inscode':['123','123'], 'symbol':['الف','الف']})
    result=tse.orders(assets=assets,depth=1,side='all')
    assert len(result)==2
    assert set(result.side)=={'buy','sell'}
    assert result['inscode'].tolist()==['123','123']
    assert len(result.attrs['pydara']['requests'])==1
    assert not any('_' in c for c in result.columns)
    assert list(tse.orders(markets='TSE',side='buy').side)==['buy']
    with pytest.raises(InvalidArgumentError):
        tse.orders(depth=6)
    with pytest.raises(InvalidArgumentError):
        tse.orders(day='1403-01-01')
    with pytest.raises(InvalidArgumentError):
        tse.orders(day='1403-01-01', start='1403-01-02',ins_code='123')


def test_historical_order_updates(monkeypatch):
    _fake(monkeypatch)
    frame=tse.orders(ins_code=['123'],day='1403-01-01',calendar='jalali')
    assert len(frame)==2
    assert frame.attrs['pydara']['historical'] is True


def test_public_docs_and_version():
    import pydara
    assert pydara.__version__=='0.7.3a6'
    for name in ('markets','assets','prices','history','traders','orders'):
        f=getattr(tse,name)
        assert 'Args:' in f.__doc__ and 'Returns:' in f.__doc__
        assert name in tse.__all__
