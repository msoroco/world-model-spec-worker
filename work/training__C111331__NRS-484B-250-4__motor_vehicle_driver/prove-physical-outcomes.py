"""Test three source-derived physical outcomes per exact case on CPU fixtures."""
import argparse
import json
import os
from pathlib import Path
import shutil

from worker_exchange.native_output import physical_result

ROOT=Path(__file__).resolve().parent
MANIFEST=ROOT/'stop-reference-construction-manifest.json'
EXPECTED={'complete_motion':'met','incomplete_motion':'not_met','missing_evidence':'unverified'}


def write(path,value):path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
def write_rows(path,rows):path.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))


def run(case,kind):
    if kind not in EXPECTED:raise ValueError('Select a physical fixture kind')
    manifest=json.loads(MANIFEST.read_text())
    entry=next((e for e in manifest['cases'] if e['case_id']==case),None)
    if entry is None:raise ValueError('Select an exact case')
    suffix=entry['id'];output_root=Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
    if '.runtime-work' not in output_root.parts:raise ValueError('Use ignored scratch')
    scratch=output_root/('physical-'+suffix+'-'+kind)
    if scratch.exists():shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    construction=json.loads((ROOT/entry['construction']).read_text())
    config=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
    write(scratch/'config.json',config)
    source=(ROOT/'selected-candidates'/suffix/'sources' if suffix.startswith('controlled_') else
            ROOT/'precedence'/suffix/'sources')
    if not source.is_dir():
        source=ROOT/('current-v2-primary-sources' if suffix=='controlled_1' else 'current-v2-contrast-sources')
    shutil.copyfile(source/'video_frames.jsonl',scratch/'video_frames.jsonl')
    shutil.copyfile(source/'trace.jsonl',scratch/'trace.jsonl')
    if kind!='missing_evidence':
        complete=kind=='complete_motion';rows=[]
        for i in range(600):
            x=-35+75*i/599 if complete else -35
            y=-1.75
            body=[[x+dx,y+dy,z] for dx in (-2,2) for dy in (-.9,.9) for z in (0,1.5)]
            rows.append({'frame':i,'time_s':i/20,
                         'ego':{'body_native_xyz_m':body},
                         'synthetic_fixture':True})
        write_rows(scratch/'native-raw-actors.jsonl',rows)
        write(scratch/'native-map-readback.json',{'source_kind':'synthetic_fixture',
            'intersection_polygon_xy_m':[[-20,-20],[20,-20],[20,20],[-20,20]]})
    result=physical_result(scratch,{'case_id':case,
        'target_checks':[{'target':'source_join','requested':True,'measured':True,
            'method':'source-bounded fixture check','tolerance':0,'matched':True,
            'physical_cause_confirmed':False,
            'cause_evidence':['native-raw-actors.jsonl','video_frames.jsonl']}],
        'physical_acceptance_claimed':False,'legal_acceptance_claimed':False})
    status=result['physical_checks']['maneuver']['status']
    if status!=EXPECTED[kind] or result['maneuver_completed']!=(kind=='complete_motion'):
        raise AssertionError('Physical fixture status differs: '+status)
    if result['provenance_kind']!='synthetic_fixture' or result['diagnostic_fixture'] is not True:
        raise AssertionError('Fixture provenance lost')
    if kind=='complete_motion' and not result['realized_observables']:
        raise AssertionError('Measured fixture progress missing')
    destination=ROOT/'physical-preparation'/suffix;destination.mkdir(parents=True,exist_ok=True)
    write(destination/(kind+'-result.json'),result)
    (destination/(kind+'.log')).write_text('PASS '+case+' '+kind+' source-derived maneuver '+status+'\n')
    print(destination/(kind+'-result.json'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',required=True)
    p.add_argument('--kind',choices=EXPECTED,required=True);a=p.parse_args()
    run(a.case,a.kind)
