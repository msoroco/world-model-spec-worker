"""Saved-only exact pedestrian crossing measurement and Native-result bridge."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from saved_measurement import read_attempt


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_crossing_route(attempt):
    """Selected measurement contract method, using original-shaped saved sources."""
    return read_attempt(attempt)['measurement']


def _write_rows(path, rows):
    with path.open('x') as stream:
        for row in rows: stream.write(json.dumps(row,allow_nan=False)+'\n')


def build_report(attempt):
    root=Path(attempt).resolve()
    saved=read_attempt(root)
    scene=json.loads((root/'scene.json').read_text())
    config=json.loads((root/'config.json').read_text())
    if config['selected_case_id']!=scene['case_id'] or saved['case_id']!=scene['case_id']:
        raise ValueError('saved exact case identity mismatch')
    description=config['case']['recording_description']
    trace=[json.loads(line) for line in (root/'trace.jsonl').read_text().splitlines() if line]
    bodies=[json.loads(line) for line in (root/'walker-body-history.jsonl').read_text().splitlines() if line]
    if len(trace)!=len(bodies) or any(t.get('frame')!=b.get('frame') or abs(t.get('time_s',-1)-b.get('time_s',0))>1e-4 for t,b in zip(trace,bodies)):
        raise ValueError('original trace and walker body join mismatch')
    values={
      'walker_body_route':[b['body_xy_m'] for b in bodies],
      'curb_and_crosswalk_geometry':[{'starting_curb_xy_m':scene['starting_curb_xy_m'],
          'opposite_curb_xy_m':scene['opposite_curb_xy_m'],
          'crosswalk_boundaries_xy_m':scene['crosswalk_boundaries_xy_m']} for _ in bodies],
      'route_angle_and_length':[saved['measurement'] for _ in bodies],
      'governing_context':[{'control_context':scene['control_context'],
          'jurisdiction_source':scene['jurisdiction_source'],'site_context_status':scene['site_context_status']} for _ in bodies],
    }
    channels=root/'channels';channels.mkdir(exist_ok=True)
    evidence=[]
    for item in description['channels']:
        name=item['name']
        if name not in values:raise ValueError('unsupported channel: '+name)
        path=channels/(name+'.jsonl')
        _write_rows(path,[{'time_s':b['time_s'],'value':value} for b,value in zip(bodies,values[name])])
        evidence.append({'name':name,'unit':item['unit'],'reference':str(path.relative_to(root))})
    context={'roadway_and_jurisdiction':{'road_sha256':sha(root/'road.xodr'),
       'site_context_status':scene['site_context_status'],'crosswalk_context':scene['crosswalk_context'],
       'camera_sources_sha256':{name:sha(root/(name+'.mkv')) for name in ('overview','approach','reference_corner','driver_reference')}}}
    context_path=channels/'context.json';context_path.write_text(json.dumps(context,allow_nan=False)+'\n')
    for item in description['context_inputs']:
        evidence.append({'name':item['name'],'unit':item['unit'],'reference':str(context_path.relative_to(root))})
    measurement=saved['measurement']
    report={'format':'worker-analysis-report','analysis_complete':True,'case_id':scene['case_id'],
       'provenance_kind':'synthetic_fixture' if saved['diagnostic_fixture'] else 'native',
       'diagnostic_fixture':saved['diagnostic_fixture'],
       'measurements':{'crossing_route_geometry':{'method':'measure_crossing_route','value':measurement,
          'sources':{key:value for key,value in saved['sources_sha256'].items() if key!='scene.json'}}},
       'construction_scene_sha256':saved['sources_sha256']['scene.json'],
       'legal_verdict_claimed':False,
       'limitations':['Authored curb and crosswalk context is not original map confirmation.',
                      'Synthetic diagnostic pixels and motion are software compatibility only.']}
    target={'target':'original walker crossing route measured against sourced curbs',
       'requested':scene['construction_intent'],'measured':measurement,
       'method':'saved original body centers, finite curb nearest point and crosswalk polygon',
       'tolerance':'engineering source agreement only; no legal tolerance',
       'matched':False,'physical_cause_confirmed':False,
       'cause_evidence':saved['sources_sha256']}
    result={'case_id':scene['case_id'],'measured_values':measurement,
       'target_checks':[target],'setup_confirmed':False,'behavior_attempted':False,
       'maneuver_completed':False,'termination_reason':'Saved source assessment pending',
       'physical_failure_flags':[],'trace_reference':'trace.jsonl',
       'video_references':[name+'.mkv' for name in ('overview','approach','reference_corner','driver_reference')],
       'video_frame_map_reference':'video_frames.jsonl','recording_description':description,
       'recording_evidence':evidence,'realized_observables':{}}
    return report,result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();root=Path(args.attempt).resolve()
    report,result=build_report(root)
    from worker_exchange.native_output import physical_result, write_result
    result=physical_result(root,result)
    write_result(root,result)
    report['physical_checks']=result['physical_checks']
    report['realized_observables']=result['realized_observables']
    Path(args.output).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'case_id':report['case_id'],'analysis_complete':True,
                      'diagnostic_fixture':report['diagnostic_fixture']}))

if __name__=='__main__':main()
