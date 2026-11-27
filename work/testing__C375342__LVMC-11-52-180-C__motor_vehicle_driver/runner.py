"""Exact source-gated LVMC 11.52.180(C) Native alley duration entry."""
import argparse
import json
import os
from pathlib import Path
from alley_site import ASSIGNMENT,load_site

ROOT=Path(__file__).resolve().parent


def selected_config():
    cfg=json.loads((ROOT/'config.json').read_text())
    if (cfg.get('assignment_id')!=ASSIGNMENT or cfg.get('law_id')!='LVMC-11-52-180-C'
        or cfg.get('cell_id')!='C375342' or cfg.get('actor')!='motor_vehicle_driver'
        or cfg.get('rate_hz')!=20 or cfg.get('duration_s')!=3600
        or cfg.get('selected_case_id') not in cfg.get('supported_case_ids',[])):
        raise ValueError('exact designated alley rolling-hour capture contract differs')
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
        print(json.dumps({'case_id':cfg['selected_case_id'],'capture_contract_checked':True,
                          'reviewed_original_site_required_for_native':True}))
        return 0
    if not args.output_dir:
        parser.error('--output-dir required')
    root=os.environ.get('C375342_LVMC_ALLEY_SITE_ROOT')
    if not root:
        raise ValueError('C375342_LVMC_ALLEY_SITE_ROOT reviewed source directory required')
    label=cfg['selected_case_id'].rsplit('__',1)[-1]
    site_path=Path(root)/(label+'.json')
    site,records=load_site(site_path,cfg['selected_case_id'])
    if site['requested_intervals_s']!=cfg['case']['requested_intervals_s']:
        raise ValueError('reviewed site differs from exact construction interval schedule')
    from alley_native import run_native
    run_native(cfg,site,records,site_path,Path(args.output_dir),args.host,args.port)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
