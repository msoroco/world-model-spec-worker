"""Exact source-gated LVMC 11.52.070 angle-parking Native entry point."""
import argparse
import json
import os
from pathlib import Path
from orientation_site import ASSIGNMENT,load_site
ROOT=Path(__file__).resolve().parent

def selected_config():
    cfg=json.loads((ROOT/'config.json').read_text())
    if (cfg.get('assignment_id')!=ASSIGNMENT or cfg.get('law_id')!='LVMC-11-52-070'
        or cfg.get('cell_id')!='C377875' or cfg.get('actor')!='motor_vehicle_driver'
        or cfg.get('rate_hz')!=20 or cfg.get('duration_s')!=30
        or cfg.get('selected_case_id') not in cfg.get('supported_case_ids',[])):
        raise ValueError('exact Engineer-angle-parking capture contract differs')
    return cfg

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check',action='store_true');p.add_argument('--output-dir')
    p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=2000)
    a=p.parse_args(argv);cfg=selected_config()
    if a.check:
        print(json.dumps({'case_id':cfg['selected_case_id'],'capture_contract_checked':True,'reviewed_original_site_required_for_native':True}))
        return 0
    if not a.output_dir:p.error('--output-dir required')
    root=os.environ.get('C377875_LVMC_ANGLE_SITE_ROOT')
    if not root:raise ValueError('C377875_LVMC_ANGLE_SITE_ROOT reviewed source directory required')
    name=cfg['selected_case_id'].rsplit('__',1)[-1]
    site_path=Path(root)/(name+'.json');site,records=load_site(site_path,cfg['selected_case_id'])
    request=cfg['case']
    if site['requested_activity']!=request['activity_request'] or site['requested_orientation']!=request['orientation_request']:
        raise ValueError('reviewed site differs from exact construction')
    from orientation_native import run_native
    run_native(cfg,site,records,site_path,Path(a.output_dir),a.host,a.port)
    return 0
if __name__=='__main__':raise SystemExit(main())
