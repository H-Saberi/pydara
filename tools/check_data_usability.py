"""Run bounded data-only checks; real TSETMC access requires --live."""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import UTC, datetime
from importlib import metadata, util
import json
from pathlib import Path
import platform
import tempfile


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--live',action='store_true')
    p.add_argument('--symbol',default='\u0641\u0648\u0644\u0627\u062f')
    p.add_argument('--output',type=Path,default=Path('pydara_data_review_check.json'))
    args=p.parse_args(argv)
    import pandas as pd
    import pydara
    from pydara import tse as data
    from pydara.tse.samples import sample_client
    report={'time':datetime.now(UTC).isoformat(),'python':platform.python_version(),
            'platform':platform.system(),'pydara':pydara.__version__,'pandas':pd.__version__,
            'live_requested':args.live,'checks':[]}
    def check(name,fn):
        try:
            detail=fn()
            report['checks'].append({'name':name,'status':'passed','detail':detail})
        except Exception as exc:
            report['checks'].append({'name':name,'status':'failed','type':type(exc).__name__,'message':str(exc)})
    df=data.load_sample()
    def validate():
        issues=data.validate(df,schema='daily_bars')
        return {'rows':len(df),'issues':len(issues),'synthetic':True}
    check('synthetic_schema',validate)
    def batch():
        with sample_client() as c:
            result=c.get_quotes(pd.Series([args.symbol,args.symbol]),on_error='collect')
        if result.status.ne('ok').any():raise AssertionError(result.error_message.tolist())
        return {'rows':len(result),'input_order_preserved':True}
    # The synthetic fixture has only its documented tickers; custom --symbol is for --live.
    if args.symbol=='\u0641\u0648\u0644\u0627\u062f':check('pandas_series_batch',batch)
    with tempfile.TemporaryDirectory(prefix='pydara-check-') as directory:
        root=Path(directory)
        for ext,mod in [('csv',None),('xlsx','openpyxl'),('sqlite',None),('parquet','pyarrow')]:
            if mod is not None and util.find_spec(mod) is None:
                report['checks'].append({'name':'roundtrip_'+ext,'status':'skipped','reason':f'{mod} not installed'})
                continue
            def run(ext=ext):
                path=root/f'frame.{ext}';data.save(df,path)
                pd.testing.assert_frame_equal(df,data.load(path),check_dtype=True)
                return {'rows':len(df),'dtype_preserved':True}
            check('roundtrip_'+ext,run)
    if args.live:
        def run_live():
            with data.Client() as c:
                q=c.get_quote(args.symbol,policy=data.FetchPolicy.fresh())
            return {'ins_code':q.instrument.ins_code,'price':str(q.last_price),
                    'trade_date':str(q.trade_date),'quality_flags':q.meta.quality_flags}
        check('live_quote',run_live)
    report['failed']=sum(c['status']=='failed' for c in report['checks'])
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return bool(report['failed'])
if __name__=='__main__':raise SystemExit(main())
