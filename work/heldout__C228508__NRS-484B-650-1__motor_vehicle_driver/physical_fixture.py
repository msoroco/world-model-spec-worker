"""Source-joined synthetic route-motion and lifecycle preparation protocol.

This tests classification and closure order only. It does not report a CARLA run,
completed statutory act, physical hazard, or legal violation.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
EVENTS=['capture_finished','encoders_closed','restoration_verified','native_exit','owner_released','saved_processing_started']

def digest(path):return sha256(Path(path).read_bytes()).hexdigest()
def rows(value):return [json.loads(x) for x in value.splitlines() if x]

def evaluate(case,kind):
    manifest=json.loads((HERE/'execution-manifest.json').read_text())
    entry=next((x for x in manifest['cases'] if x['case_id']==case),None)
    if entry is None or kind not in ('complete_motion','incomplete_motion','missing_evidence'):
        raise ValueError('Unknown exact case or fixture kind')
    construction=HERE/entry['construction']
    if digest(construction)!=entry['construction_sha256']:
        raise ValueError('Exact construction changed')
    recipe=json.loads((HERE/Path(entry['fixture_recipe']).relative_to(Path('work')/HERE.name)).read_text())
    source=HERE.parents[1]/recipe['sources'][0]['source']
    if digest(source)!=recipe['sources'][0]['sha256']:
        raise ValueError('Diagnostic source changed')
    diagnostic=json.loads(source.read_text());files=diagnostic['files']
    frame_map=rows(files['video_frames.jsonl']);trace=rows(files['driving_trace.jsonl']);following=rows(files['following_sources.jsonl'])
    if len(frame_map)<3 or len(frame_map)!=len(trace) or len(frame_map)!=len(following):
        raise ValueError('Native-shaped source coverage differs')
    for f,t,s in zip(frame_map,trace,following):
        if (f['carla_frame'],f['time_s'])!=(t['frame'],t['time_s']) or (t['frame'],t['time_s'])!=(s['frame'],s['time_s']):
            raise ValueError('Diagnostic original source frame join differs')
    if {v['path'] for v in diagnostic['videos']}!={'overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv'}:
        raise ValueError('Four camera fixture specification missing')
    synthetic=[{'frame':7000+i,'time_s':i*.05,'ego_station_m':i*.9 if kind=='complete_motion' else 0.0} for i in range(40)] if kind!='missing_evidence' else None
    progress=synthetic[-1]['ego_station_m']-synthetic[0]['ego_station_m'] if synthetic else None
    status='unverified' if synthetic is None else 'met' if progress>1 else 'not_met'
    expected={'complete_motion':'met','incomplete_motion':'not_met','missing_evidence':'unverified'}[kind]
    if status!=expected:raise ValueError('Physical fixture classification differs')
    return {'format':'worker-physical-fixture-outcome','case_id':case,'fixture_kind':kind,'fixture_only':True,
        'diagnostic_fixture':True,'actual_native_capture':False,'source_shape_kind':'Native-shaped synthetic',
        'physical_checks':{'maneuver':{'status':status,'method':'20 Hz source-joined synthetic route-motion classifier; no listed act or hazard finding',
            'sources':{'construction':entry['construction'],'construction_sha256':entry['construction_sha256'],
                'diagnostic':recipe['sources'][0]['source'],'diagnostic_sha256':digest(source),
                'synthetic_trace_sha256':sha256(json.dumps(synthetic).encode()).hexdigest() if synthetic else None},
            'missing_evidence':['synthetic route-motion trace'] if synthetic is None else []}},
        'maneuver_completed':status=='met','realized_observables':{'synthetic_route_progress_m':progress,'synthetic_frames':40} if status=='met' else {},
        'provenance_kind':'native','provenance_note':'Native-shaped synthetic protocol only; no CARLA capture or physical/legal completion',
        'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}

def lifecycle(out_of_order=False):
    events=EVENTS.copy()
    if out_of_order:events[-2:]=events[-2:][::-1]
    if events!=EVENTS:raise ValueError('Saved processing precedes Native owner release')
    return {'events':events,'fixture_only':True,'actual_native_capture':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case');p.add_argument('--kind');p.add_argument('--output');p.add_argument('--lifecycle',action='store_true');p.add_argument('--out-of-order',action='store_true');a=p.parse_args()
    result=lifecycle(a.out_of_order) if a.lifecycle else evaluate(a.case,a.kind)
    if a.output:Path(a.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':True,'case_id':a.case,'kind':a.kind,'status':result.get('physical_checks',{}).get('maneuver',{}).get('status'),'events':result.get('events')}))
