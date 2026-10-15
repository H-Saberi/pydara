"""Source-qualified market selection; no external HTTP in these regression tests."""
from copy import deepcopy
from urllib.parse import parse_qs, urlsplit
import pandas as pd
import pytest
from pydara import tse
from pydara.tse._core.exceptions import DataQualityError
from pydara.tse.providers.market import request_spec
from pydara.tse.samples.market import fixtures, sample_market_client


def test_watch_source_selector_url():
    for market, expected in ((None, '0'), ('TSE', '1'), ('IFB', '2')):
        url = request_spec('market.watch', market=market).path
        assert parse_qs(urlsplit(url).query)['market'] == [expected]


def test_all_unknown_flow_stays_unknown_in_unfiltered_watch():
    payload = deepcopy(fixtures()['market.watch'])
    for row in payload['marketwatch']:
        row.pop('flow', None)
    with sample_market_client(responses={'market.watch': payload}) as c:
        result = c.get_instruments()
    assert len(result) == len(payload['marketwatch'])
    assert result['market'].isna().all()


def test_selected_watch_can_use_provider_market_selector():
    payload = deepcopy(fixtures()['market.watch'])
    for row in payload['marketwatch']:
        row.pop('flow', None)
    with sample_market_client(responses={'market.watch': payload}) as c:
        result = c.get_instruments(market='TSE')
    assert len(result) == len(payload['marketwatch'])
    assert set(result['market'].dropna()) == {'TSE'}
    assert result.attrs['pydara']['market_labels_from_server_selector'] == len(result)
    assert all('market_from_server_selector' in fs for fs in result.quality_flags)


def test_source_contradicts_filter_does_not_force_market():
    payload = deepcopy(fixtures()['market.watch'])
    assert set(row['flow'] for row in payload['marketwatch']) == {1,2}
    with sample_market_client(responses={'market.watch': payload}) as c:
        out = c.get_instruments(market='TSE')
    assert len(out) == 1
    assert out.market.iloc[0] == 'TSE'
    assert out.attrs['pydara']['market_selector_conflicting_rows'] == 1
    assert out.attrs['pydara']['market_labels_from_server_selector'] == 0


def test_assets_without_market_is_not_forced_into_tse(monkeypatch):
    frame = pd.DataFrame({'ins_code':['1','2'],'market':[None,'IFB'],'symbol':['A','B']})
    monkeypatch.setattr(tse._client(), 'get_instruments', lambda **kwargs: frame.copy())
    assert len(tse.assets()) == 2
    assert tse.assets(markets='TSE').empty


def test_existing_offline_unfiltered_snapshot_still_usable(monkeypatch):
    from pydara.tse._core.exceptions import OfflineDataUnavailableError
    raw = pd.DataFrame({'ins_code':['11','22'], 'market':['TSE',None], 'symbol':['A','B']})
    calls = []
    def fetch(**kwargs):
        calls.append(kwargs.get('market'))
        if kwargs.get('market') is not None:
            raise OfflineDataUnavailableError('Only unfiltered watch is cached')
        return raw.copy()
    monkeypatch.setattr(tse._client(), 'get_instruments', fetch)
    out = tse.assets(markets='TSE', policy='offline')
    assert out.inscode.tolist() == ['11']
    assert calls == ['TSE', None]
