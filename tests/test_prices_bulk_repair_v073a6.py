import pandas as pd
import pytest
from pydara import tse
from pydara.tse import public_workflows


def _assets(n):
    return pd.DataFrame({'inscode':[str(1000+i) for i in range(n)], 'market':['TSE']*n})


def _watch(n):
    frame=pd.DataFrame({'inscode':[str(1000+i) for i in range(n)],'closingprice':[0]*n,
                        'previousreferenceprice':[100]*n,'date':[pd.NaT]*n,'market':[pd.NA]*n})
    return public_workflows.returns(frame)


def test_incomplete_watch_bounded_repair(monkeypatch):
    calls=[]
    monkeypatch.setattr(public_workflows,'quote_watch',lambda *a,**k: _watch(30))
    def repair(*a,**k):
        codes=k['ins_code'];calls.extend(codes)
        return pd.DataFrame({'ins_code':codes,'closing_price':[105]*len(codes),
            'previous_reference_price':[100]*len(codes),'date':['2026-10-14']*len(codes)})
    monkeypatch.setattr(tse,'_legacy_price',repair)
    result=tse.prices(_assets(30),include_queues=False)
    assert len(calls)==20
    assert len(result)==30
    assert result['returnpct'].notna().sum()==20
    assert result['returnpct'].isna().sum()==10
    assert set(result['market'].dropna())=={'TSE'}
    meta=result.attrs['pydara']
    assert meta['repair_deferred']==[str(1000+i) for i in range(20,30)]
    assert meta['repair_succeeded']==20


def test_no_unbounded_fallback(monkeypatch):
    monkeypatch.setattr(public_workflows,'quote_watch',lambda *a,**k: _watch(30))
    monkeypatch.setattr(tse,'_legacy_price',lambda *a,**k: (_ for _ in ()).throw(AssertionError('no requests')))
    df=tse.prices(_assets(30),include_queues=False,max_quote_fallback=0)
    assert df['returnpct'].isna().all()
    assert len(df.attrs['pydara']['repair_deferred'])==30


def test_invalid_fallback_limit():
    from pydara.tse._core.exceptions import InvalidArgumentError
    with pytest.raises(InvalidArgumentError):
        tse.prices(max_quote_fallback=-1)
