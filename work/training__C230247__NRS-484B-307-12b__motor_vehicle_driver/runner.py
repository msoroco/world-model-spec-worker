"""Exact Native red-X lane runner with separate saved analysis."""
import argparse
import json
from pathlib import Path

from capture import check as capture_check, execute as capture_execute
from draft_runner import check as geometry_check
from finalize import finalize


def check():
    root=Path(__file__).resolve().parent
    cfg=json.loads((root/'config.json').read_text())
    geometry=geometry_check(cfg)
    capture=capture_check(cfg,(root/'road.xodr').read_text())
    return {'case_id':cfg['case_id'],'geometry':geometry,'capture':capture,
            'physical_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--process-saved')
    parser.add_argument('--output-dir')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=2000)
    args=parser.parse_args()
    if sum((args.check,bool(args.process_saved),bool(args.output_dir)))!=1:
        raise SystemExit('Choose one check, saved analysis or Native capture')
    if args.check:
        print(json.dumps(check()))
    elif args.process_saved:
        root=Path(args.process_saved)
        print(json.dumps(finalize(root,root/'red-x-analysis.json')))
    else:
        case=check()['case_id']
        print(json.dumps(capture_execute(case,args.output_dir,args.host,args.port)))


if __name__=='__main__':
    main()
