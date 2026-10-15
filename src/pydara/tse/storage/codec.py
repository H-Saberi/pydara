"""Safe, versioned DataFrame wire codec. No pickle, eval, or executable metadata.

The interchange format preserves supported Pandas dtypes and one-level indexes.
Object values have a tagged JSON representation. Unsupported values fail closed.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from hashlib import sha256
import json
import math
import re

import numpy as np
import pandas as pd
from pandas.api.types import (is_bool_dtype, is_float_dtype, is_integer_dtype,
                             is_datetime64_any_dtype, is_timedelta64_dtype)
from pydara.tse._core.exceptions import InvalidArgumentError, StorageError

CODEC_VERSION = 1
NULL = '\\N'


def pack(value, depth=0):
    """Only a small allowlist of inert Python values may enter an archive."""
    if depth > 32:
        raise InvalidArgumentError('Metadata is too deeply nested.')
    if value is pd.NA:
        return {'$':'pd.NA'}
    if value is pd.NaT:
        return {'$':'pd.NaT'}
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, np.generic):
        return pack(value.item(), depth+1)
    if isinstance(value, float):
        if not math.isfinite(value):
            return {'$':'float','v':repr(value)}
        return value
    if isinstance(value, Decimal):
        return {'$':'decimal','v':str(value)}
    if isinstance(value, pd.Timestamp):
        return {'$':'timestamp','v':value.isoformat()}
    if isinstance(value, datetime):
        return {'$':'datetime','v':value.isoformat()}
    if isinstance(value, date):
        return {'$':'date','v':value.isoformat()}
    if isinstance(value, time):
        return {'$':'time','v':value.isoformat()}
    if isinstance(value, pd.Timedelta):
        return {'$':'timedelta_ns','v':str(value.value)}
    if isinstance(value, timedelta):
        return {'$':'timedelta_us','v':str((value.days*86400+value.seconds)*1000000+value.microseconds)}
    if isinstance(value, (list, tuple)):
        return {'$':'tuple' if isinstance(value, tuple) else 'list',
                'v':[pack(v, depth+1) for v in value]}
    if isinstance(value, dict):
        if not all(isinstance(k, str) for k in value):
            raise InvalidArgumentError('Metadata dictionary keys must be strings.')
        return {'$':'dict','v':{k:pack(v, depth+1) for k,v in value.items()}}
    raise InvalidArgumentError(f'Unsupported archive value: {type(value).__name__}.')


def unpack(value, depth=0):
    """Perform the unpack operation.
    
    Args:
        value (Any): Input for the unpack operation.
        depth (Any): Input for the unpack operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        StorageError: When the corresponding validation or operation fails."""
    if depth > 32:
        raise StorageError('Archive metadata is too deeply nested.')
    if not isinstance(value, dict):
        if value is None or isinstance(value,(str,int,float,bool)):
            return value
        raise StorageError('Malformed tagged value.')
    tag, v = value.get('$'), value.get('v')
    if tag == 'pd.NA': return pd.NA
    if tag == 'pd.NaT': return pd.NaT
    if tag == 'decimal': return Decimal(v)
    if tag == 'float' and v in ('nan','inf','-inf'): return float(v)
    if tag == 'timestamp': return pd.Timestamp(v)
    if tag == 'datetime': return datetime.fromisoformat(v)
    if tag == 'date': return date.fromisoformat(v)
    if tag == 'time': return time.fromisoformat(v)
    if tag == 'timedelta_ns': return pd.Timedelta(int(v), unit='ns')
    if tag == 'timedelta_us': return timedelta(microseconds=int(v))
    if tag in ('tuple','list') and isinstance(v,list):
        items=[unpack(x,depth+1) for x in v]
        return tuple(items) if tag=='tuple' else items
    if tag=='dict' and isinstance(v,dict):
        return {k:unpack(x,depth+1) for k,x in v.items()}
    raise StorageError(f'Unknown inert metadata tag: {tag!r}.')


def dumps(value):
    """Perform the dumps operation.
    
    Args:
        value (Any): Input for the dumps operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',',':'), allow_nan=False)


def loads(text):
    """Perform the loads operation.
    
    Args:
        text (Any): Input for the loads operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        StorageError: When the corresponding validation or operation fails."""
    def unique(pairs):
        """Perform the unique operation.
        
        Args:
            pairs (Any): Input for the unique operation.
        
        Returns:
            Implementation-defined result or generator output; see the calling API.
        
        Raises:
            StorageError: When the corresponding validation or operation fails."""
        out={}
        for k,v in pairs:
            if k in out: raise StorageError('Duplicate metadata key.')
            out[k]=v
        return out
    return json.loads(text, object_pairs_hook=unique,
                      parse_constant=lambda s: (_ for _ in ()).throw(StorageError('Nonfinite JSON token.')))


def missing(value):
    """Perform the missing operation.
    
    Args:
        value (Any): Input for the missing operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    return value is None or value is pd.NA or value is pd.NaT or (
        isinstance(value, (float,np.floating)) and math.isnan(value))


def string_wire(value, safe):
    """Perform the string wire operation.
    
    Args:
        value (Any): Input for the string_wire operation.
        safe (Any): Input for the string_wire operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    if missing(value): return NULL
    value=str(value)
    if value=='': return '\\E'
    if value.startswith('\\'): value='\\'+value
    if safe and (value.startswith("'") or value[:1] in ('\t','\r','\n') or
                 value.lstrip()[:1] in ('=','+','-','@')):
        value="'"+value
    return value


def string_unwire(value, safe):
    """Perform the string unwire operation.
    
    Args:
        value (Any): Input for the string_unwire operation.
        safe (Any): Input for the string_unwire operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    if value == NULL: return pd.NA
    if value == '\\E': return ''
    if safe and value.startswith("'"): value=value[1:]
    if value.startswith('\\\\'): value=value[1:]
    return value


def describe(series):
    """Perform the describe operation.
    
    Args:
        series (Any): Input for the describe operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails."""
    dt=series.dtype
    d={'dtype':str(dt)}
    if isinstance(dt,pd.CategoricalDtype):
        d.update(kind='category', categories=pack(dt.categories.tolist()), ordered=dt.ordered)
    elif isinstance(dt,pd.StringDtype) or str(dt)=='str':
        d.update(kind='string', storage=getattr(dt,'storage','python'),
                 na='nan' if getattr(dt,'na_value',pd.NA) is np.nan else 'pd.NA')
    elif isinstance(dt,pd.DatetimeTZDtype):
        d.update(kind='datetime_tz', tz=str(dt.tz))
    elif is_datetime64_any_dtype(dt): d['kind']='datetime'
    elif is_timedelta64_dtype(dt): d['kind']='timedelta'
    elif is_bool_dtype(dt): d['kind']='bool'
    elif is_integer_dtype(dt): d['kind']='int'
    elif is_float_dtype(dt): d['kind']='float'
    elif str(dt)=='object': d['kind']='object'
    else: raise InvalidArgumentError(f'Unsupported archive dtype: {dt}.')
    return d


def encode_cell(value, desc, safe):
    """Encode cell.
    
    Args:
        value (Any): Input for the encode_cell operation.
        desc (Any): Input for the encode_cell operation.
        safe (Any): Input for the encode_cell operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails."""
    kind=desc['kind']
    if kind=='object': return dumps(pack(value))
    if missing(value): return NULL
    if kind=='string': return string_wire(value,safe)
    if kind=='category': return dumps(pack(value))
    if kind=='bool': return '1' if value else '0'
    if kind=='int': return str(int(value))
    if kind=='float': return repr(float(value))
    if kind.startswith('datetime'): return pd.Timestamp(value).isoformat()
    if kind=='timedelta': return str(pd.Timedelta(value).value)
    raise InvalidArgumentError('Unknown column codec.')


def validate_spec(desc):
    """Bound the dtype language accepted from untrusted archive metadata."""
    if not isinstance(desc, dict):
        raise StorageError('Column specification must be an object.')
    kind, dt = desc.get('kind'), desc.get('dtype')
    if not isinstance(dt, str) or len(dt) > 160:
        raise StorageError('Invalid archive dtype.')
    allowed = {
        'object': {'object'}, 'category': {'category'},
        'string': {'string', 'str'}, 'bool': {'bool', 'boolean'},
        'int': {p + n for p in ('int', 'uint', 'Int', 'UInt') for n in ('8', '16', '32', '64')},
        'float': {'float16', 'float32', 'float64', 'Float32', 'Float64'},
    }
    if kind in allowed:
        valid = dt in allowed[kind]
    elif kind in ('datetime', 'timedelta'):
        prefix = 'datetime64' if kind == 'datetime' else 'timedelta64'
        valid = re.fullmatch(prefix + r'\[(s|ms|us|ns)\]', dt) is not None
    elif kind == 'datetime_tz':
        tz = desc.get('tz')
        valid = (isinstance(tz, str) and 0 < len(tz) <= 120
                 and re.fullmatch(r'datetime64\[(s|ms|us|ns), .+\]', dt) is not None)
    else:
        valid = False
    if not valid:
        raise StorageError('Unsupported or inconsistent archive dtype.')


def decode_series(values, desc, safe):
    """Decode series.
    
    Args:
        values (Any): Input for the decode_series operation.
        desc (Any): Input for the decode_series operation.
        safe (Any): Input for the decode_series operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        StorageError: When the corresponding validation or operation fails."""
    validate_spec(desc)
    kind=desc['kind']; dt=desc['dtype']
    if kind=='object': return pd.Series([unpack(loads(v)) for v in values],dtype=object)
    if kind=='category':
        vals=[None if v==NULL else unpack(loads(v)) for v in values]
        return pd.Series(pd.Categorical(vals,categories=unpack(desc['categories']),ordered=desc['ordered']))
    if kind=='string':
        vals=[string_unwire(v,safe) for v in values]
        storage = desc.get('storage', 'python')
        if storage not in ('python', 'pyarrow', 'pyarrow_numpy'):
            raise StorageError('Unknown string storage backend.')
        if dt=='str':
            try:
                return pd.Series(vals, dtype=pd.StringDtype(storage=storage, na_value=np.nan))
            except TypeError:
                return pd.Series(vals, dtype=pd.StringDtype(storage=storage))
        return pd.Series(vals, dtype=pd.StringDtype(storage=storage))
    if kind in ('datetime','datetime_tz'):
        vals=[None if v==NULL else v for v in values]
        # Per-value parsing avoids mixed ISO precision inference across pandas versions.
        result=pd.Series([pd.NaT if v is None else pd.Timestamp(v) for v in vals])
        if kind=='datetime_tz': result=pd.to_datetime(result,utc=True).dt.tz_convert(desc['tz'])
        else: result=pd.to_datetime(result)
        return result.astype(dt)
    if kind=='timedelta':
        return pd.Series([pd.NaT if v==NULL else pd.Timedelta(int(v),unit='ns') for v in values],dtype=dt)
    conv={'int':int,'float':float,'bool':lambda v: {'1':True,'0':False}[v]}[kind]
    na=pd.NA if dt[:1].isupper() else (np.nan if kind=='float' else None)
    return pd.Series([na if v==NULL else conv(v) for v in values],dtype=dt)


@dataclass(frozen=True)
class FrozenFrame:
    """Encapsulate frozen frame behavior in the TSE module.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    manifest: dict
    rows: tuple[tuple[str,...],...]

    def digest(self):
        """Perform the digest operation.
        
        Returns:
            Implementation-defined result or generator output; see the calling API."""
        return sha256(dumps({'columns':self.manifest['columns'], 'rows':self.rows}).encode()).hexdigest()


def canonical_attrs(attrs):
    """Perform the canonical attrs operation.
    
    Args:
        attrs (Any): Input for the canonical_attrs operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API."""
    attrs = dict(attrs)
    if 'tse_dara' in attrs:
        legacy_metadata = attrs.pop('tse_dara')
        attrs.setdefault('pydara', legacy_metadata)
    return attrs


def freeze(df, *, safe_text=True, metadata=True):
    """Perform the freeze operation.
    
    Args:
        df (Any): Input for the freeze operation.
        safe_text (Any): Input for the freeze operation.
        metadata (Any): Input for the freeze operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails."""
    if not isinstance(df,pd.DataFrame): raise InvalidArgumentError('df must be a pandas.DataFrame.')
    if not isinstance(safe_text,bool) or not isinstance(metadata,bool):
        raise InvalidArgumentError('safe_text and metadata must be bool.')
    if isinstance(df.index,pd.MultiIndex) or isinstance(df.columns,pd.MultiIndex):
        raise InvalidArgumentError('MultiIndex is not supported; reset it explicitly first.')
    if not df.columns.is_unique or not all(isinstance(c,str) and c for c in df.columns):
        raise InvalidArgumentError('Columns must be unique nonempty strings.')
    columns=list(df.columns)
    if not columns: raise InvalidArgumentError('At least one column is required.')
    desc=[describe(df[c]) for c in columns]
    if isinstance(df.index,pd.RangeIndex):
        idx={'kind':'range','start':df.index.start,'stop':df.index.stop,'step':df.index.step,'name':pack(df.index.name)}
    else:
        values=pd.Series(df.index,copy=True); idesc=describe(values)
        idx={'kind':'values','spec':idesc,'name':pack(df.index.name),
             'values':[encode_cell(v,idesc,safe_text) for v in values],
             'freq':getattr(df.index,'freqstr',None)}
    rows=tuple(tuple(encode_cell(v,d,safe_text) for v,d in zip(row,desc))
               for row in df.itertuples(index=False,name=None))
    manifest={'format':'pydara-frame','codec_version':CODEC_VERSION,'columns':columns,'specs':desc,
              'index':idx,'column_name':pack(df.columns.name),'row_count':len(df),'safe_text':safe_text,
              'attrs':pack(canonical_attrs(df.attrs) if metadata else {})}
    frozen=FrozenFrame(manifest,rows)
    manifest['matrix_sha256']=frozen.digest()
    return frozen


def thaw(manifest, rows, *, verify=True):
    """Perform the thaw operation.
    
    Args:
        manifest (Any): Input for the thaw operation.
        rows (Any): Input for the thaw operation.
        verify (Any): Input for the thaw operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        StorageError: When the corresponding validation or operation fails."""
    try:
        if manifest.get('format') not in ('pydara-frame','tse-dara-frame') or manifest.get('codec_version')!=CODEC_VERSION:
            raise StorageError('Unrecognized DataFrame archive version.')
        columns=manifest['columns']; specs=manifest['specs']; safe=manifest['safe_text']
        if (not isinstance(columns, list) or not columns
            or not all(isinstance(c, str) and c for c in columns)
            or not isinstance(safe, bool) or len(columns)!=len(specs)
            or len(set(columns))!=len(columns)):
            raise StorageError('Invalid column description.')
        frozen=FrozenFrame(manifest,tuple(tuple(r) for r in rows))
        if len(frozen.rows)!=manifest['row_count'] or any(len(r)!=len(columns) for r in frozen.rows):
            raise StorageError('Archive shape does not match its manifest.')
        if verify and frozen.digest()!=manifest['matrix_sha256']:
            raise StorageError('Data checksum mismatch; file was edited, truncated or mismatched.')
        out=pd.DataFrame({c:decode_series([r[i] for r in frozen.rows],specs[i],safe)
                          for i,c in enumerate(columns)})
        idx=manifest['index']
        if idx['kind']=='range':
            index=pd.RangeIndex(idx['start'],idx['stop'],idx['step'],name=unpack(idx['name']))
        else:
            series=decode_series(idx['values'],idx['spec'],safe)
            index=pd.Index(series,name=unpack(idx['name']))
            if idx.get('freq') and isinstance(index,(pd.DatetimeIndex,pd.TimedeltaIndex)):
                index.freq=idx['freq']
        if len(index)!=len(out): raise StorageError('Index length does not match rows.')
        out.index=index;out.columns.name=unpack(manifest['column_name'])
        out.attrs=canonical_attrs(unpack(manifest['attrs']))
        return out
    except StorageError: raise
    except Exception as exc:
        raise StorageError(f'Cannot decode archived DataFrame ({type(exc).__name__}).') from exc
