"""Independent fixed-source and declared-variable audit of exact parking cases."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from parking_source import sha
from delivery_audit import audit,required

ROOT=Path(__file__).resolve().parent
ALL_SOURCE_KEYS=('map','street','device','person','rack','sidewalk','curb','building','pedestrian_context','parking_history')

def compare(comparison_id,attempts,diagnostic=False):
    plan=json.loads((ROOT/'case-plan.json').read_text())
    declared=next((r for r in plan['comparisons'] if r['comparison_id']==comparison_id),None)
    if declared is None:raise ValueError('unknown exact parking comparison')
    paths=[Path(path).resolve() for path in attempts]
    if len(paths)!=len(declared['case_ids']) or len(set(paths))!=len(paths):
        raise ValueError('comparison requires distinct exact captures for every selected case')
    reports=[audit(path,cid,diagnostic) for path,cid in zip(paths,declared['case_ids'])]
    cfg=[json.loads(required(path,'config.json').read_text()) for path in paths]
    sites=[json.loads(required(path,'reviewed-site/site.json').read_text()) for path in paths]
    for key in ('law_id','cell_id','actor','rate_hz','duration_s','cameras'):
        if any(row.get(key)!=cfg[0].get(key) for row in cfg[1:]):raise ValueError('fixed capture condition differs: '+key)
    variable={'rack_pedestrian_passing':{'pedestrian_context'},'covered_device_class':{'device'},
              'placement_alternatives':set()}.get(comparison_id)
    if variable is None:raise ValueError('unknown comparison variable')
    for key in ALL_SOURCE_KEYS:
        if key in variable:continue
        hashes=[site['sources'][key]['sha256'] for site in sites]
        if any(value!=hashes[0] for value in hashes[1:]):raise ValueError('fixed original source differs: '+key)
    configured=[]
    for cid,config,report in zip(declared['case_ids'],cfg,reports):
        planned=next(case for case in plan['cases'] if case['case_id']==cid)
        expected=(planned['device_class'],planned['placement'],planned['pedestrian_passing_context'])
        selected=(config['case']['device_class'],config['case']['placement'],config['case']['pedestrian_context'])
        if selected!=expected:raise ValueError('declared exact placement/device context changed')
        if report['measurement']['legal_least_obstruction']!='unresolved':
            raise ValueError('qualitative legal judgment must remain unresolved')
        configured.append(selected)
    if len(set(configured))!=len(configured):raise ValueError('declared parking comparison contrast absent')
    measured=[r['measurement'] for r in reports]
    if comparison_id=='rack_pedestrian_passing' and measured[0]['observed_pedestrian_device_min_distance_m']==measured[1]['observed_pedestrian_device_min_distance_m']:
        raise ValueError('original pedestrian passage contrast absent')
    if comparison_id=='covered_device_class' and len({r['device_class'] for r in measured})!=len(measured):
        raise ValueError('original covered-device class contrast absent')
    if comparison_id=='placement_alternatives' and len({r['observed_placement'] for r in measured})!=len(measured):
        raise ValueError('original placement contrast absent')
    return {'format':'worker-covered-device-parking-comparison-audit','comparison_id':comparison_id,
            'case_ids':declared['case_ids'],'passed':True,'diagnostic_only':diagnostic,
            'physical_acceptance':False,'legal_acceptance':False,
            'fixed_conditions':declared['fixed_conditions'],'deliberate_differences':declared['deliberate_differences'],
            'configured_values':configured,'site_source_sha256':[sha(path/'reviewed-site/site.json') for path in paths]}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--comparison',required=True)
    parser.add_argument('--attempt',type=Path,action='append',required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--diagnostic-fixture',action='store_true')
    args=parser.parse_args();result=compare(args.comparison,args.attempt,args.diagnostic_fixture)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'comparison_id':args.comparison,'passed':True,'diagnostic_only':args.diagnostic_fixture}))
if __name__=='__main__':main()
