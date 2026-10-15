from datetime import date,datetime,UTC
from decimal import Decimal
from pathlib import Path
import json
import sqlite3
import numpy as np
import pandas as pd
import pytest

from pydara.tse import save,load
from pydara.tse.samples import sample_client
from pydara.tse.storage.codec import pack,unpack,freeze,thaw
from pydara.tse.exceptions import *

FORMATS=['csv','xlsx','sqlite','parquet']
FOLAD='\u0641\u0648\u0644\u0627\u062f'

def needed(ext):
    if ext=='parquet':pytest.importorskip('pyarrow')
    if ext=='xlsx':pytest.importorskip('openpyxl')


@pytest.mark.parametrize('ext',FORMATS)
@pytest.mark.parametrize('numeric',['analysis','exact'])
def test_history_roundtrip(ext,numeric,tmp_path):
    needed(ext)
    from dataclasses import replace
    from pydara.tse import ClientConfig,Client
    from pydara.tse.samples import sample_transport
    with Client(config=ClientConfig(numeric=numeric),storage=False,transport=sample_transport(),_namespace='sample') as c:
        frame=c.get_history(FOLAD,include_jdate=True)
    p=tmp_path/('data.'+ext);receipt=save(frame,p)
    assert receipt.state=='persisted' and receipt.rows==6
    out=load(p);pd.testing.assert_frame_equal(out,frame)
    assert out.attrs==frame.attrs


@pytest.mark.parametrize('ext',FORMATS)
def test_supported_types_and_safe_text(ext,tmp_path):
    needed(ext)
    frame=pd.DataFrame({
      'id':pd.Series(['9007199254740993',None,'0004','123'],dtype='string'),
      'text':pd.Series(['=2+3',"'=actual",'\\N',''],dtype='string'),
      'int':pd.Series([9007199254740993,0,None,-3],dtype='Int64'),
      'uint':pd.Series([2**64-1,0,None,5],dtype='UInt64'),
      'float':pd.Series([1.2345678901234567,-0.0,None,0.1],dtype='Float64'),
      'bool':pd.Series([True,False,None,True],dtype='boolean'),
      'time':pd.Series(pd.to_datetime(['2024-01-01T00:00:00.123456789Z',None,'2024-01-03','2024-01-04'],
                       utc=True,format='mixed')).dt.tz_convert('Asia/Tehran'),
      'object':pd.Series([Decimal('9007199254740993.123'),('flag',),{'a':1},None],dtype=object),
      'category':pd.Series(pd.Categorical(['a','b',None,'a'],categories=['b','a'],ordered=True))})
    frame.attrs={'x':('v',Decimal('2.2')),'date':date(2024,1,1)}
    path=tmp_path/('test.'+ext);save(frame,path);result=load(path)
    pd.testing.assert_frame_equal(frame,result)
    assert frame.attrs==result.attrs
    if ext=='xlsx':
        import openpyxl
        wb=openpyxl.load_workbook(path)
        assert wb['data']['A2'].data_type=='s'
        assert all(cell.data_type!='f' for row in wb['data'] for cell in row)
        wb.close()


@pytest.mark.parametrize('value',['','\\N','\\E','\\hello',"'x",'=cmd',' -bad','+bad','@bad','\t=bad','\nhello'])
@pytest.mark.parametrize('safe',[True,False])
def test_text_reversibility(value,safe,tmp_path):
    df=pd.DataFrame({'s':pd.Series([value,None],dtype='string')})
    p=tmp_path/'t.csv';save(df,p,safe_text=safe);pd.testing.assert_frame_equal(load(p),df)


@pytest.mark.parametrize('ext',FORMATS)
def test_empty_and_nonstandard_index(ext,tmp_path):
    needed(ext)
    for i,df in enumerate([pd.DataFrame({'s':pd.Series(dtype='string'),'n':pd.Series(dtype='Float64')}),
        pd.DataFrame({'a':[1,2]},index=pd.date_range('2024-01-01',periods=2,name='when')),
        pd.DataFrame({'a':[1,2]},index=pd.RangeIndex(4,8,2,name='row')),
        pd.DataFrame({'a':[1,2]},index=pd.Index(['one','two'],name='name'))]):
        p=tmp_path/f't{i}.{ext}';save(df,p);pd.testing.assert_frame_equal(load(p),df)


def test_csv_sidecar_tampering_and_missing(tmp_path):
    p=tmp_path/'x.csv';save(pd.DataFrame({'price':[10]}),p)
    p.write_text(p.read_text(encoding='utf-8-sig').replace('10','11'),encoding='utf-8-sig')
    with pytest.raises(StorageError,match='checksum'):load(p)
    assert load(p,verify=False).price.iloc[0]==11
    p.with_name(p.name+'.pydara.json').unlink()
    with pytest.raises(StorageError,match='sidecar'):load(p)


@pytest.mark.parametrize('ext',['csv','xlsx','sqlite'])
def test_no_overwrite_unless_explicit(ext,tmp_path):
    a=pd.DataFrame({'p':[1]});b=pd.DataFrame({'p':[2]});p=tmp_path/('x.'+ext)
    save(a,p)
    with pytest.raises(FileExistsDataError):save(b,p)
    assert load(p).p.iloc[0]==1
    save(b,p,overwrite=True);assert load(p).p.iloc[0]==2


def test_sqlite_datasets_and_unrelated_db_protection(tmp_path):
    p=tmp_path/'x.db';df=pd.DataFrame({'id':['004']})
    save(df,p,dataset='first');save(df,p,dataset='second')
    pd.testing.assert_frame_equal(load(p,dataset='first'),df)
    pd.testing.assert_frame_equal(load(p,dataset='second'),df)
    q=tmp_path/'other.db'
    with sqlite3.connect(q) as c:c.execute('CREATE TABLE important (a int)')
    with pytest.raises(StorageError,match='Not a PyDara'):save(df,q)
    with sqlite3.connect(q) as c:assert c.execute('SELECT count(*) FROM important').fetchone()==(0,)


def test_unsupported_schema_no_file_created(tmp_path):
    for frame in (pd.DataFrame([[1,2]],columns=['a','a']),pd.DataFrame({0:[1]}),
                  pd.DataFrame({'obj':[object()]}),pd.DataFrame({'v':[1]},index=pd.MultiIndex.from_tuples([(1,2)]))):
        p=tmp_path/'x.csv'
        with pytest.raises(InvalidArgumentError):save(frame,p)
        assert not p.exists()


def test_missing_optional_dependency_is_actionable(monkeypatch,tmp_path):
    import importlib
    original=importlib.import_module
    def blocked(name,*a,**k):
        if name.startswith('pyarrow'):raise ImportError('mock missing')
        return original(name,*a,**k)
    monkeypatch.setattr(importlib,'import_module',blocked)
    with pytest.raises(OptionalDependencyError,match='pyarrow'):
        save(pd.DataFrame({'a':[1]}),tmp_path/'x.parquet')


def test_no_pickle_and_unknown_tag_rejected():
    with pytest.raises(StorageError):unpack({'$':'eval','v':'print(1)'})
    with pytest.raises(InvalidArgumentError):pack(object())


def test_path_lock_and_atomic_failure(monkeypatch,tmp_path):
    from pydara.tse import io
    p=tmp_path/'data.csv';df=pd.DataFrame({'v':[1]});save(df,p)
    original=p.read_bytes()
    lock=p.with_name(p.name+'.pydara.lock');lock.touch()
    with pytest.raises(StorageBusyError):save(df,p,overwrite=True)
    lock.unlink()
    def fail(*a,**k):raise OSError('mock full disk')
    monkeypatch.setattr(io,'sync_file',fail)
    with pytest.raises(StorageError):save(pd.DataFrame({'v':[2]}),p,overwrite=True)
    assert p.read_bytes()==original
    assert not lock.exists()


def test_metadata_false_omits_only_attrs(tmp_path):
    df=pd.DataFrame({'a':[1]});df.attrs={'private':'not stored'}
    p=tmp_path/'t.csv';save(df,p,metadata=False);out=load(p)
    assert out.attrs=={} and list(out.a)==[1]


def test_excel_large_cell_rejected(tmp_path):
    needed('xlsx')
    with pytest.raises(StorageError,match='32767'):
        save(pd.DataFrame({'s':pd.Series(['a'*33000],dtype='string')}),tmp_path/'t.xlsx')


def test_csv_header_injection_and_named_column_roundtrip(tmp_path):
    df=pd.DataFrame({'=1+2':[1]});p=tmp_path/'t.csv';save(df,p)
    assert p.read_text(encoding='utf-8-sig').splitlines()[0].startswith("'=1+2")
    pd.testing.assert_frame_equal(load(p),df)


def test_xlsx_formula_edit_rejected(tmp_path):
    needed('xlsx');import openpyxl
    p=tmp_path/'x.xlsx';save(pd.DataFrame({'n':[1]}),p)
    wb=openpyxl.load_workbook(p);wb['data']['A2']='=1+1';wb.save(p);wb.close()
    with pytest.raises(StorageError,match='Formulas'):load(p,verify=False)


@pytest.mark.parametrize('spec', [
    {'kind':'int','dtype':'V1000000000'},
    {'kind':'object','dtype':'datetime64[ns]'},
    {'kind':'datetime','dtype':'datetime64[Y]'},
    {'kind':'imaginary','dtype':'object'},
])
def test_untrusted_dtype_language_rejected(spec):
    frozen=freeze(pd.DataFrame({'v':[1]}))
    frozen.manifest['specs'][0]=spec
    with pytest.raises(StorageError,match='dtype'):
        thaw(frozen.manifest,frozen.rows)


def test_sync_file_opens_writable_descriptor_for_windows(tmp_path, monkeypatch):
    """Windows CRT cannot fsync a read-only descriptor (Errno 9)."""
    from pydara.tse import io as archive_io
    import builtins
    p = tmp_path / 'flush.tmp'
    p.write_bytes(b'file')
    actual_open = builtins.open
    modes = []
    def checking_open(path, mode='r', *args, **kwargs):
        if Path(path) == p:
            modes.append(mode)
            assert '+' in mode or 'w' in mode or 'a' in mode
        return actual_open(path, mode, *args, **kwargs)
    monkeypatch.setattr(builtins, 'open', checking_open)
    archive_io.sync_file(p)
    assert modes == ['r+b']
