"""Explicit, bounded installation check. Synthetic by default; --live is opt-in."""
import argparse
import importlib.metadata
import json
import platform
from pathlib import Path
from datetime import UTC, datetime


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Make a real, bounded TSETMC request")
    parser.add_argument("--symbol", default="\u0641\u0648\u0644\u0627\u062f")
    parser.add_argument("--output", default="pydara_check.json")
    args = parser.parse_args()
    import pydara
    from pydara.tse import Client
    from pydara.tse.samples import sample_client
    report = {"checked_at":datetime.now(UTC).isoformat(),"mode":"live" if args.live else "synthetic",
              "python":platform.python_version(),"platform":platform.platform(),
              "pydara":pydara.__version__,"module_file":pydara.__file__}
    report["dependencies"]={p:importlib.metadata.version(p) for p in ['pandas','httpx','platformdirs','tzdata']}
    try:
        with (Client(storage=False) if args.live else sample_client()) as client:
            quote=client.get_quote(args.symbol)
            report.update(success=True, symbol=quote.instrument.symbol, ins_code=quote.instrument.ins_code,
                last_price=str(quote.last_price), closing_price=str(quote.closing_price),
                currency=quote.instrument.currency, source_timestamp=str(quote.source_timestamp),
                retrieved_at=str(quote.retrieved_at), flags=quote.meta.quality_flags,
                requests=client.request_count)
    except Exception as exc:
        report.update(success=False,error_type=type(exc).__name__,error=str(exc))
    path=Path(args.output)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    print(f"Report saved: {path.resolve()}")
    return 0 if report['success'] else 1


if __name__=='__main__':
    raise SystemExit(main())
