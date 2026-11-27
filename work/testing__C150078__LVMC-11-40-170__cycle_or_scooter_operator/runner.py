"""Exact source-gated bicycle/e-bike/e-scooter rack parking Native entrypoint."""
import argparse
import json
import os
from pathlib import Path
from parking_source import ASSIGNMENT,CASE_SPEC,load_site

ROOT=Path(__file__).resolve().parent


def selected_config():
    cfg=json.loads((ROOT/'config.json').read_text())
    if (cfg.get('assignment_id')!=ASSIGNMENT or cfg.get('law_id')!='LVMC-11-40-170' or
        cfg.get('cell_id')!='C150078' or cfg.get('actor')!='cycle_or_scooter_operator' or
        cfg.get('rate_hz')!=20 or cfg.get('duration_s')!=30 or
        cfg.get('selected_case_id') not in [ASSIGNMENT+'__'+label for label in CASE_SPEC]):
        raise ValueError('exact bicycle parking capture contract differs')
    return cfg


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=2000)
    args=parser.parse_args(argv)
    cfg=selected_config()
    if args.check:
        print(json.dumps({'case_id':cfg['selected_case_id'],'capture_contract_checked':True,'original_site_required_for_native':True}))
        return 0
    if not args.output_dir:parser.error('--output-dir required')
    source_root=os.environ.get('C150078_LVMC_PARKING_SITE_ROOT')
    if not source_root:raise ValueError('C150078_LVMC_PARKING_SITE_ROOT original reviewed site directory required')
    label=cfg['selected_case_id'][len(ASSIGNMENT)+2:]
    site_path=Path(source_root)/(label+'.json')
    site,records=load_site(site_path,cfg['selected_case_id'])
    from parking_native import run_native
    run_native(cfg,site,records,site_path,Path(args.output_dir),args.host,args.port)
    return 0


if __name__=='__main__':raise SystemExit(main())
