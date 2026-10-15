from datetime import date
import pandas as pd
import pytest
from pydara import tse
from pydara.tse._core.exceptions import InvalidArgumentError
from pydara.tse.trades_workflow import trades

class FakeClient:
    def __init__(self): self.calls=[]
    def get_trades(self, ref, **kwargs):
        self.calls.append((ref.value, kwargs))
        df=pd.DataFrame({'ins_code':[ref.value]*3,'symbol':['فولاد']*3,
          'date':[date(2026,10,15)]*3,'price':[100,101,102],
          'quantity':[3,5,2],'trade_id':['a','b','c'],
          'source_timestamp':['2026-10-15T05:00:00Z','2026-10-15T08:00:00Z',None]})
        df.attrs['pydara']={'synthetic':True,'is_stale':False}
        return df


def test_clock_and_codes():
    fake=FakeClient()
    data=trades(fake, ins_code=['123456','123456','98765'], start='1405-07-23',
        end='1405-07-23', starttime='09:00',endtime='12:00')
    assert len(fake.calls)==2
    assert len(data)==2
    assert list(data['time'])==['11:30:00','11:30:00']
    assert 'inscode' in data and 'tradeid' in data
    assert data.attrs['pydara']['synthetic'] is True


def test_assets_dataframe_and_defaults():
    df=pd.DataFrame({'inscode':['123456'],'symbol':['فولاد'],'market':['TSE']})
    result=trades(FakeClient(),assets=df,start='2026-10-15',end='2026-10-15')
    assert len(result)==3
    assert set(result['market'])=={'TSE'}


@pytest.mark.parametrize('kwargs',[
    {'ins_code':'123','starttime':'25:00'},
    {'ins_code':'123','starttime':'13:00','endtime':'09:00'},
    {'ins_code':'123','start':'1405-07-23','end':'1405-07-22'},
    {'ins_code':'123','start':'1405-01-01','end':'1405-07-01'},
    {'ins_code':'123','on_error':'invalid'},
    {'start':'1405-07-23'},
])
def test_validation(kwargs):
    with pytest.raises(InvalidArgumentError):trades(FakeClient(),**kwargs)


def test_public_export_and_signature():
    import inspect
    assert callable(tse.trades)
    assert 'starttime' in inspect.signature(tse.trades).parameters
    assert 'endtime' in inspect.signature(tse.trades).parameters
    assert 'DataFrame' in tse.trades.__doc__
