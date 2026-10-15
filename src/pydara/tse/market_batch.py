"""Consistent ordered batch reports for new tabular datasets."""
from __future__ import annotations
from collections.abc import Sequence
from copy import deepcopy
import pandas as pd
import numpy as np
from pydara import __version__
from pydara.tse._core.models import InstrumentRef
from pydara.tse._core.exceptions import InvalidArgumentError
from .history_models import BatchFrames
from .market_schemas import empty_market_frame


def validate_index_batch(items,on_error):
    """Validate index batch.
    
    Args:
        items (Any): Input for the validate_index_batch operation.
        on_error (Any): Policy for handling errors in multi-item requests.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        InvalidArgumentError: When the corresponding validation or operation fails."""
    from .market import _index_query
    if isinstance(items,(pd.Series,pd.Index,np.ndarray)):
        if isinstance(items,pd.MultiIndex) or getattr(items,'ndim',1)!=1:raise InvalidArgumentError('Use a one-dimensional sequence of indices.')
        items=items.tolist()
    if isinstance(items,(str,bytes)) or not isinstance(items,Sequence) or not 1<=len(items)<=10000:
        raise InvalidArgumentError('Use 1..10000 ordered index names/codes.')
    if on_error not in ('raise','collect'):raise InvalidArgumentError('on_error must be raise or collect.')
    for item in items:_index_query(item)
    return tuple(items)


class TableBatchBuilder:
    """Encapsulate table batch builder behavior in the TSE module.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    def __init__(self,schema,total,numeric,include_jdate=False):
        """Initialize the instance and its configured state.
        
        Args:
            schema (Any): Input for the __init__ operation.
            total (Any): Input for the __init__ operation.
            numeric (Any): Numeric conversion or output representation setting.
            include_jdate (Any): Input for the __init__ operation."""
        self.schema,self.total,self.numeric,self.include_jdate=schema,total,numeric,include_jdate
        self.frames=[];self.requests=[];self.errors=[];self.manifests=[]

    @staticmethod
    def label(item):
        """Perform the label operation.
        
        Args:
            item (Any): Input for the label operation.
        
        Returns:
            Implementation-defined result or generator output; see the calling API."""
        return item.value if isinstance(item,InstrumentRef) else str(item)

    def success(self,pos,item,frame):
        """Perform the success operation.
        
        Args:
            pos (Any): Input for the success operation.
            item (Any): Input for the success operation.
            frame (Any): DataFrame to convert, validate, process or store."""
        self.manifests.append({'request_index':pos,'metadata':deepcopy(frame.attrs.get('pydara',{}))})
        f=frame.copy(deep=True);f.attrs={}
        f['request_index']=pd.Series(pos,index=f.index,dtype='Int64')
        f['input_symbol']=pd.Series(self.label(item),index=f.index,dtype='string')
        self.frames.append(f)
        self.requests.append(dict(request_index=pos,input_symbol=self.label(item),status='ok',row_count=len(f),error_code=None,error_message=None))

    def failure(self,pos,item,exc):
        """Perform the failure operation.
        
        Args:
            pos (Any): Input for the failure operation.
            item (Any): Input for the failure operation.
            exc (Any): Input for the failure operation."""
        row=dict(request_index=pos,input_symbol=self.label(item),error_code=type(exc).__name__,error_message=str(exc))
        self.errors.append(row);self.requests.append(dict(row,status='error',row_count=0))

    def result(self):
        """Perform the result operation.
        
        Returns:
            Implementation-defined result or generator output; see the calling API."""
        frame=pd.concat(self.frames,ignore_index=True) if self.frames else empty_market_frame(self.schema,self.numeric,self.include_jdate)
        if 'request_index' not in frame:
            frame['request_index']=pd.Series(dtype='Int64');frame['input_symbol']=pd.Series(dtype='string')
        requests=pd.DataFrame(self.requests,columns=['request_index','input_symbol','status','row_count','error_code','error_message'])
        errors=pd.DataFrame(self.errors,columns=['request_index','input_symbol','error_code','error_message'])
        for f in (requests,errors):
            for c in f:f[c]=f[c].astype('Int64' if c in ('request_index','row_count') else 'string')
        meta=dict(schema_id=self.schema+'.batch',base_schema=self.schema,schema_version='1',package_version=__version__,
            coverage_status='unknown',requested_items=self.total,processed_items=len(requests),failed_items=len(errors),
            unprocessed_items=self.total-len(requests),items=deepcopy(self.manifests),numeric=self.numeric)
        frame.attrs['pydara']=deepcopy(meta)
        return BatchFrames(data=frame,errors=errors,requests=requests,manifest=meta)
