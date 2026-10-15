"""Generate release documentation from actual Python signatures (no network)."""
from __future__ import annotations
import dataclasses
import inspect
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from pydara import tse as data,__version__
from pydara.tse import Client,AsyncClient

NETWORK = ('NetworkError','ApiError','SchemaMismatchError','DataQualityError',
           'UnknownInstrumentError','AmbiguousInstrumentError','StaleDataError','OfflineDataUnavailableError')
PARAMETERS={
 'instrument':'Symbol string or explicit InstrumentRef. A bare numeric string is not inferred as ins_code.',
 'instruments':'Nonempty ordered list/tuple, Pandas Series/Index or a one-dimensional NumPy array. Duplicates preserved; nulls rejected.',
 'query':'Nonempty text to search. Search does not guess which result the user meant.',
 'market':'TSE/IFB/BASE enum or documented string. Support depends on endpoint; index/overview support TSE/IFB only. None never certifies historical coverage.',
 'include_inactive':'Include inactive/unknown entries. False requires verified active status from the response.',
 'limit':'Positive local display limit; None keeps all returned matches. Does not change server paging.',
 'as_of':'Timezone-aware cutoff for locally stored history; online historical reconstruction is not implemented.',
 'known_at':'Historical identity knowledge cutoff; reserved and explicitly rejected in this release.',
 'policy':"FetchPolicy, None, or shorthand 'auto'/'online'/'offline'. Offline shorthand does not authorize stale data.",
 'freshness':'Explicit FreshnessPolicy, with precedence over policy freshness for quotes.',
 'field':"One of 'last', 'closing', 'previous_reference'; not a raw API field name.",
 'on_error':"'raise' stops with partial_result; 'collect' records errors without losing other inputs.",
 'start':'Inclusive date, ISO YYYY-MM-DD string or timezone-naive midnight Pandas Timestamp. None means available start.',
 'end':'Inclusive date, ISO string or timezone-naive midnight Pandas Timestamp. None means available end.',
 'calendar':"'gregorian' or 'jalali' for date strings. Python date/Pandas Timestamp always mean Gregorian dates.",
 'adjustment':"Only 'none' is implemented; 'source' raises UnsupportedCapabilityError, never a fabricated adjusted series.",
 'series':"Only 'listing' is implemented. 'continuous_verified' requires a verified historical identity chain.",
 'include_jdate':'Add a textual Jalali date column. It does not change the primary Gregorian date column.',
 'chunk_days':'Positive calendar-day span for local output chunks. Not server-side streaming or pagination.',
 'full':'Force a full source-history recheck instead of the calculated tail request.',
 'overlap_days':'Positive calendar-day overlap window for rechecking recent corrections.',
 'full_refresh_days':'After this many days since a full fetch, the next explicit sync performs a full audit. No scheduler.',
 'wait':'Wait for storage only in explicit sync. False may return queued state, not durable data.',
 'timeout':'Bounded seconds for the explicit storage wait; not an exchange availability guarantee.',
 'on_storage_error':"'report' retains downloaded data with a failure report; 'raise' requires successful explicit storage.",
 'receipt_id':'Receipt identifier created in this running process, not a reusable authentication token.',
 'flush_timeout':'Maximum seconds to attempt flushing on close; inspect the returned complete flag.',
 'raise_on_error':'Whether detected errors should raise instead of only returning a report.',
 'df':'An ordinary Pandas DataFrame; input is never modified in place by local helpers.',
 'path':'Nonempty path string or pathlib.Path, not the working cache database for archive exports.',
 'format':'csv/excel/parquet/sqlite, or None to infer from the supported file suffix.',
 'dataset':'Name of a stored table archive inside a snapshot SQLite database.',
 'metadata':'Keep dataframe attrs as well as structural schema; False omits attrs, not required type/checksum metadata.',
 'overwrite':'Explicit consent to replace this export path/dataset. Default False.',
 'safe_text':'Protect dangerous formula-like text on export; decoding reverses the protection.',
 'verify':'Check archive checksums and structure. Not a cryptographic signature of a trusted sender.',
 'schema':'Name of an implemented structural schema. For load, this argument remains reserved; use None.',
 'numeric':"'analysis' gives nullable Float64; 'exact' uses Decimal for price/quantity fields. Identifiers always remain text.",
 'columns':'Explicit column list/preset for selection or old-name -> new-name mapping for normalization.',
 'check_order':'Report ascending natural-key order violations without sorting input.',
 'timezone':'Explicit timezone for otherwise-naive real timestamps. Daily dates remain timezone-naive.',
 'sort':'Explicitly reorder normalized rows by request_index/ins_code/date if present. No rows are dropped.',
 'name':'Optional exact public API name to select from the installed reference.',
 'config':'Immutable ClientConfig; supplied constructor overrides take precedence.',
 'source':"Only 'public' is supported; official authentication is not pretended to work.",
 'mode':"auto/online/offline; fresh cached responses may be reused in online. FetchPolicy.fresh() bypasses the cache.",
 'storage':'Boolean enabling the default best-effort local response storage, or None to use config.',
 'data_dir':'Directory containing pydara.sqlite3. Does not move or delete old databases.',
 'credentials':'Reserved for official provider; any non-None value is rejected.',
 'transport':'Explicit HTTPX transport test hook. It must never be used as an auth workaround.',
 '_namespace':'Internal/testing cache namespace; normally leave unchanged.',
 'value':'Input date or identifier; use the documented constructor to state its kind.',
 'allow_stale':'Explicit permission to use old cached data; never relabels it as live.',
 'max_stale':'Optional nonnegative timedelta limiting age since response retrieval.',
 'index':'Exact index code (string/int/InstrumentRef) or exact normalized catalog name. No first-match guess.',
 'indices':'Ordered index names/codes, including Series/Index or a one-dimensional array; duplicates preserved.',
 'day':'Optional explicit single Gregorian/Jalali day; latest intraday index endpoint only supports None.',
 'backend':'auto/json/legacy; auto uses legacy only after valid empty JSON, not after auth/HTTP/schema errors.',
 'show_traded':'Return only rows with a reported positive trade_count. Unknown is not treated as proof of no trading.',
 'include_order_book':'Add reported depth 1..5 columns with separate provenance; no forward fill.',
 'include_client_types':'Fetch and join a separate bulk response by exact ID; timestamps may be absent/different.',
 'sector_code':'Exact short sector code returned by get_sectors(), preserving leading zeros.',
 'ins_code':'Exact positive integer identifier; on bulk key statistics this is a local filter.',
 'interval':'Polling sleep seconds after the previous returned snapshot; local minimum 1 second, not an exchange limit.',
 'max_updates':'Maximum yielded snapshots (default 10); None explicitly opts into indefinite polling.',
 'coverage':"'report' preserves unknown/partial coverage; 'raise' requires the available evidence.",
}
SPECIAL={
 'save':['InvalidArgumentError','FileExistsDataError','StorageError','OptionalDependencyError'],
 'load':['InvalidArgumentError','StorageError','OptionalDependencyError'],
 'Client':['ConfigurationError','UnsupportedCapabilityError'],
 'AsyncClient':['ConfigurationError','UnsupportedCapabilityError'],
 'ClientConfig':['ConfigurationError'], 'NetworkConfig':['ConfigurationError'],
 'StorageConfig':['ConfigurationError'], 'FreshnessPolicy':['ConfigurationError'],
 'FetchPolicy':['ConfigurationError'], 'configure':['ConfigurationError'], 'load_sample':['InvalidArgumentError'],
 'validate':['InvalidArgumentError','DataQualityError'],
 'normalize':['InvalidArgumentError','DataQualityError','UnsupportedCapabilityError'], 'get_config':[], 'api_reference':['InvalidArgumentError'],
 'schema_info':['InvalidArgumentError'], 'select_columns':['InvalidArgumentError'],
 'frame_metadata':['InvalidArgumentError'], 'normalize_data':['InvalidArgumentError'],
 'validate_data':['InvalidArgumentError','DataQualityError'],
 'flush':['StorageError','StorageFlushTimeout','ConfigurationError'],
 'close':['ConfigurationError'], 'capabilities':[], 'storage_status':[],
 'get_write_receipt':['UnknownReceiptError'],
 'load_stored_history':['OfflineDataUnavailableError','StorageError','InvalidArgumentError','AmbiguousInstrumentError'],
 'history_status':['StorageError'], 'get_history_revisions':['StorageError','OfflineDataUnavailableError','InvalidArgumentError'],
 'reindex_history':['StorageError'], 'to_gregorian':['InvalidArgumentError'],'to_jalali':['InvalidArgumentError'],
}

def ann(a):
 if a is inspect.Parameter.empty or a is inspect.Signature.empty:return 'documented in source'
 return a if isinstance(a,str) else getattr(a,'__name__',str(a))

def build():
 names=[n for n in dict.fromkeys(data.__all__) if inspect.isfunction(getattr(data,n,None))]
 names+=['Client','AsyncClient','ClientConfig','NetworkConfig','StorageConfig','FreshnessPolicy','FetchPolicy']
 rows=[]
 for name in names:
  obj=getattr(data,name);sig=inspect.signature(obj)
  params=[]
  for key,p in sig.parameters.items():
   desc=PARAMETERS.get(key, 'Validated setting; see the constructor docstring and configuration source.')
   params.append({'name':key,'type':ann(p.annotation),
                 'default':'required' if p.default is inspect.Parameter.empty else repr(p.default),
                 'kind':str(p.kind),'description':desc})
  return_type=ann(sig.return_annotation)
  if inspect.isclass(obj): return_type=name
  deps=['pandas','Python standard library']
  if name in ('save','load'):deps+=['openpyxl only for Excel','pyarrow only for Parquet','sqlite3 for SQLite']
  elif name.startswith(('get_','search_','iter_','sync_')) and hasattr(Client,name) and name not in ('get_write_receipt','get_history_revisions'):
   deps+=['HTTPX for network','platformdirs','tzdata','optional best-effort SQLite']
  errors=SPECIAL.get(name,['InvalidArgumentError',*NETWORK])
  if name.startswith(('get_history','get_index','get_market','get_client','search_indices','watch_market')):errors+=['UnsupportedCapabilityError','PointInTimeUnavailableError','CoverageError']
  if name in ('get_quotes','get_history_many','get_client_types_many','get_client_type_history_many','get_index_history_many'):errors+=['BatchDataError']
  if name=='get_price':errors+=['MissingValueError','UnsupportedQuoteUnitError']
  if name == 'load_sample':
   params[0]['description'] = 'Synthetic fixture: daily_prices_v1, quote_v1, market_watch_v1, client_types_v1, indices_v1 or index_history_v1.'
  if name == 'normalize':
   for p in params:
    if p['name'] == 'source': p['description'] = "Only 'canonical' is supported; raw provider column names are not inferred."
  if name in ('get_instrument','get_instrument_frame'):
   for p in params:
    if p['name'] == 'as_of': p['description'] = 'Reserved economic identity date; historical identity lookup is explicitly unsupported.'
  if name not in ('load','normalize'):
   for p in params:
    if p['name'] == 'schema': p['description'] = 'An implemented schema name returned by capabilities()/the dataset metadata; includes daily_bars, quote, market_watch, client_types, indices, index_history and related new schemas.'
  if name=='get_index_members':
   for p in params:
    if p['name']=='as_of':p['description']='Only None is supported; historical membership raises before HTTP.'
  if name in ('get_market_map','get_index_impact'):
   for p in params:
    if p['name']=='limit':p['description']='Requested server output bound; not a coverage guarantee. Index impact other than the reviewed limit 7 is unverified.'
  rows.append({'name':name,'signature':f'{name}{sig}','parameters':params,'returns':return_type,
               'description':inspect.getdoc(obj) or '', 'exceptions':list(dict.fromkeys(errors)),
               'dependencies':deps,'async_available':hasattr(AsyncClient,name),
               'status':'experimental_raw_only' if name=='get_index_impact' else 'implemented', 'release':__version__})
 (ROOT/'src/pydara/tse/api_catalog.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
 out=['# Implemented API reference','',f'Release {__version__}. Generated from the actual installed Python signatures.',
      'All functions below are implemented; deferred blueprint functions are in ROADMAP_FA.md.',
      'Signatures with reserved arguments document their explicit failure behavior. Do not treat existence as support for every option.','']
 for row in rows:
  out += ['## '+row['name'],'','```python',row['signature'],'```','',row['description'],'',
          '|Parameter|Type|Default|Meaning|','|---|---|---|---|']
  for p in row['parameters']:
   out.append('|'+ '|'.join(str(p[k]).replace('|','\\|').replace('\n',' ') for k in ('name','type','default','description'))+'|')
  out += ['', '**Returns:** '+row['returns'], '**Errors:** '+', '.join(row['exceptions']),
          '**Dependencies:** '+', '.join(row['dependencies']),
          '**AsyncClient counterpart:** '+str(row['async_available']),'']
 (ROOT/'docs/API_REFERENCE.md').write_text('\n'.join(out),encoding='utf-8')
 return rows
if __name__=='__main__':
 print('Catalog entries:',len(build()))
