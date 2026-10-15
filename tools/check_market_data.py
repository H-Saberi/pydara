"""Bounded market-extension diagnostics. Default is synthetic and offline.

--live runs four read operations; --probe-raw additionally downloads up to five
bounded public responses. Never contains credentials or submits orders.
"""
from __future__ import annotations
import argparse
from datetime import UTC, datetime
from decimal import Decimal
import json
from pathlib import Path
import platform
import tempfile
import sys


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--probe-raw',action='store_true')
    parser.add_argument('--symbol',default='\u0641\u0648\u0644\u0627\u062f')
    parser.add_argument('--index',default='32097828799138957')
    parser.add_argument('--output',type=Path,default=Path('pydara_market_check.json'))
    args=parser.parse_args(argv)
    if args.probe_raw and not args.live:parser.error('--probe-raw requires explicit --live')
    import pandas as pd
    import pydara
    from pydara import tse as data
    from pydara.tse.samples.market import sample_market_client
    report={'version':pydara.__version__,'python':platform.python_version(),'platform':platform.platform(),
        'executable':sys.executable,'pandas':pd.__version__,'at':datetime.now(UTC).isoformat(),
        'live_requested':args.live,'checks':[],'raw_probes':[]}
    def check(name,fn):
        try:
            value=fn()
            if isinstance(value,pd.DataFrame):
                result={'rows':len(value),'dtypes':{k:str(v) for k,v in value.dtypes.items()},
                    'metadata':value.attrs.get('pydara',{}),'head':value.head(2).to_dict('records')}
            else:result=value
            report['checks'].append({'name':name,'state':'passed','result':result})
        except Exception as exc:
            report['checks'].append({'name':name,'state':'failed','error':type(exc).__name__,'message':str(exc)})
    with tempfile.TemporaryDirectory(prefix='pydara-market-check-') as folder:
        with sample_market_client(storage=True,data_dir=folder) as c:
            check('synthetic_watch',lambda:c.get_market_watch(include_order_book=True,include_client_types=True))
            check('synthetic_client_history',lambda:c.get_client_type_history('\u0641\u0648\u0644\u0627\u062f'))
            check('synthetic_index_history',lambda:c.get_index_history('32097828799138957'))
            c.flush(timeout=10)
        with sample_market_client(storage=True,data_dir=folder,mode='offline') as c:
            check('offline_watch',lambda:c.get_market_watch(include_order_book=True,include_client_types=True,
                                                           policy=data.FetchPolicy.offline(allow_stale=True)))
            report['offline_network_requests']=c.request_count
    if args.live:
        with data.Client(storage=False,config=data.ClientConfig(network=data.NetworkConfig(
            request_budget=12,max_retries=0,operation_timeout=30,connect_timeout=8,read_timeout=15))) as c:
            check('live_watch',lambda:c.get_market_watch())
            check('live_client_history',lambda:c.get_client_type_history(args.symbol))
            check('live_indices',lambda:c.get_indices())
            check('live_index_history',lambda:c.get_index_history(args.index))
        if args.probe_raw:
            import httpx
            import time
            from pydara.tse.providers.market import request_spec
            endpoints=[request_spec('market.watch'),request_spec('clients.market'),
                       request_spec('indices.list',flow='1'),request_spec('indices.impact',flow='1',top=7),request_spec('market.watch.legacy')]
            with httpx.Client(timeout=15,follow_redirects=False,headers={'User-Agent':f'pydara/{pydara.__version__}'}) as http:
                for spec in endpoints:
                    entry={'endpoint':spec.endpoint_id}
                    try:
                        url=spec.path if spec.path.startswith('https://') else 'https://cdn.tsetmc.com/api/'+spec.path
                        with http.stream('GET',url) as response:
                            entry['status_code']=response.status_code
                            entry['content_type']=response.headers.get('content-type')
                            response.raise_for_status();chunks=[];size=0
                            for chunk in response.iter_bytes():
                                size+=len(chunk)
                                if size>8*1024*1024:raise ValueError('Diagnostic byte limit exceeded')
                                chunks.append(chunk)
                        content=b''.join(chunks)
                        if spec.endpoint_id=='market.watch.legacy':
                            text=content.decode('utf8',errors='replace')
                            parts=text.split('@')
                            entry.update(bytes=len(content),sections=len(parts),preview=text[:1200])
                            if len(parts)==5:
                                entry['price_rows']=len([r for r in parts[2].split(';') if r])
                                entry['order_rows']=len([r for r in parts[3].split(';') if r])
                            report['raw_probes'].append(entry);time.sleep(2);continue
                        value=json.loads(content,parse_float=Decimal)
                        entry['bytes']=len(content)
                        entry['root_keys']=list(value) if isinstance(value,dict) else type(value).__name__
                        rows=value.get(spec.root) if isinstance(value,dict) else value
                        entry['row_count']=len(rows) if isinstance(rows,list) else None
                        entry['sample']=rows[:2] if isinstance(rows,list) else rows
                    except Exception as exc:entry.update(error=type(exc).__name__,message=str(exc))
                    report['raw_probes'].append(entry);time.sleep(2)
    report['failed']=sum(x['state']=='failed' for x in report['checks'])
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf8')
    print('Version:',report['version'],'Failures:',report['failed'],'Report:',args.output.resolve())
    return 1 if report['failed'] else 0
if __name__=='__main__':raise SystemExit(main())
