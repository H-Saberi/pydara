from datetime import date
import pandas as pd
import pytest
from pydara.tse.trades_workflow import trades
from pydara.tse._core.exceptions import InvalidArgumentError

class Fake:
    def __init__(self): self.calls = []
    def get_trades(self, ref, **kwargs):
        self.calls.append(ref.value)
        frame = pd.DataFrame({'ins_code':[ref.value], 'date':[date(2026,10,15)], 'price':[10],
            'source_timestamp':['2026-10-15T08:00:00Z']})
        frame.attrs['pydara']={'source':'fake','synthetic':True}
        return frame

def test_hard_limit_no_network():
    client=Fake()
    with pytest.raises(InvalidArgumentError, match='maxassets'):
        trades(client, ins_code=[str(i+100000) for i in range(21)], progress=False)
    assert not client.calls

def test_checkpoint_resume(tmp_path):
    client=Fake()
    opts=dict(ins_code=['123456','123457'], start='2026-10-15', end='2026-10-15',
        checkpoint=tmp_path, progress=False)
    first=trades(client,**opts)
    assert len(client.calls)==2
    assert len(first)==2
    second=trades(client,**opts)
    assert len(client.calls)==2
    assert second.attrs['pydara']['resumed_items']==2
    assert len(second)==2
    assert len(list(tmp_path.glob('*.json')))==2

def test_reject_unsafe_parallel():
    with pytest.raises(InvalidArgumentError, match='workers'):
        trades(Fake(),ins_code='123456',workers=4)

def test_public_signature():
    import inspect
    from pydara import tse
    signature=inspect.signature(tse.trades)
    assert signature.parameters['maxassets'].default==20
    assert signature.parameters['progress'].default is True
    assert signature.parameters['workers'].default==1
