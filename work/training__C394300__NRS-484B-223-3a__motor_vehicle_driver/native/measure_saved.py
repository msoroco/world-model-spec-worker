"""Source-bound saved 3(a) movement measurement; no automatic legal verdict."""
import hashlib
import json
import math
from pathlib import Path

LAW_TEXT_SHA256='e60d085d40eefb382cbfc682f8ae76b9930ff54e553d04416af7bb40bc547ab5'
CENTER_ROADS={1,14,2}


def _sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite_pair(value,name):
    if not isinstance(value,list) or len(value)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in value):
        raise ValueError('Invalid '+name)
    return [float(v) for v in value]


def measure(folder):
    folder=Path(folder)
    source=folder/'native_samples.jsonl';survey_file=folder/'road_geometry.json'
    map_file=folder/'scene.xodr'
    purpose_file=folder/'declared_purpose.json'
    rows=[json.loads(s) for s in source.read_text().splitlines() if s.strip()]
    survey=json.loads(survey_file.read_text());purpose=json.loads(purpose_file.read_text())
    if not rows or len(rows)<20:raise ValueError('Saved Native interval too short')
    if survey.get('native_lane_types_verified') is not True or \
            survey.get('authored_map_sha256')!=_sha(map_file):
        raise ValueError('Native lane survey missing')
    if purpose.get('law_text_sha256')!=LAW_TEXT_SHA256 or purpose.get('case') not in ('controlled_1','controlled_2'):
        raise ValueError('Source-bound declared purpose missing')
    kinds={r.get('source_kind') for r in rows}
    if len(kinds)!=1 or kinds.pop() not in ('synthetic_cpu','original_native'):
        raise ValueError('Mixed or missing source provenance')
    kind=rows[0]['source_kind']
    if purpose.get('source_kind')!=kind or survey.get('source_kind')!=kind:
        raise ValueError('Source provenance mismatch')
    frames=[r.get('native_frame') for r in rows]
    if any(type(f) is not int for f in frames) or frames!=sorted(set(frames)):
        raise ValueError('Native frames unordered or duplicated')
    times=[r.get('time_s') for r in rows]
    if any(type(t) not in (int,float) or not math.isfinite(t) for t in times) or \
            any(b<=a for a,b in zip(times,times[1:])):
        raise ValueError('Native time order invalid')
    center=[];first_turn=[];first_exit=[];through=[];later_turn=[];later_exit=[]
    for row in rows:
        road=row.get('native_road_id');lane=row.get('native_lane_id')
        if type(road) is not int or type(lane) is not int:raise ValueError('Native lane identity missing')
        xy=_finite_pair(row.get('native_center_xy_m'),'Native center')
        body=row.get('native_body_xy_m')
        if not isinstance(body,list) or len(body)!=4:raise ValueError('Body footprint missing')
        body=[_finite_pair(p,'body vertex') for p in body]
        if road in CENTER_ROADS and lane==-1 and all(-1.75<=p[1]<=1.75 for p in body):
            center.append(row)
        if road==13 and lane==-1:first_turn.append(row)
        if road==4 and lane==-1:first_exit.append(row)
        if road==2 and lane==-2 and all(1.75<=p[1]<=5.25 for p in body):
            through.append(row)
        if road==23 and lane==-1:later_turn.append(row)
        if road==24 and lane==-1:later_exit.append(row)
    if not center:raise ValueError('No fully occupied center-lane body frames')
    if min(r['native_frame'] for r in center)>=min(frames)+len(frames)//2:
        raise ValueError('Center-lane use occurs too late for comparison')
    first_opportunity_through=[r for r in center if r['native_road_id'] in (14,2)
                               and r['native_center_xy_m'][0]>=-10]
    measured={
        'center_full_body_frames':len(center),
        'center_entry_frame':center[0]['native_frame'],
        'center_exit_frame':center[-1]['native_frame'],
        'center_approach_x_span_m':round(max(r['native_center_xy_m'][0] for r in center)-
                                         min(r['native_center_xy_m'][0] for r in center),4),
        'first_opportunity_center_through_frames':len(first_opportunity_through),
        'first_left_connector_frames':len(first_turn),
        'first_left_exit_frames':len(first_exit),
        'later_through_full_body_frames':len(through),
        'later_left_connector_frames':len(later_turn),
        'later_left_exit_frames':len(later_exit),
    }
    if purpose['case']=='controlled_1':
        movement=bool(first_turn and first_exit and not later_turn and not later_exit)
    else:
        movement=bool(first_opportunity_through and through and later_turn and later_exit and not first_turn)
    return {'format':'c394300-3a-saved-movement-v1','case':purpose['case'],
            'source_kind':kind,'source_hashes':{'native_samples.jsonl':_sha(source),
                'road_geometry.json':_sha(survey_file),'declared_purpose.json':_sha(purpose_file),
                'scene.xodr':_sha(map_file)},
            'map_sha256':survey['authored_map_sha256'],
            'declared_purpose':purpose.get('declaration'),
            'declared_purpose_is_observed_driver_intent':False,
            'measured':measured,'requested_movement_observed_in_saved_rows':movement,
            'actual_native_or_pixels_verified':False,
            'legal_verdict':None}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('folder');args=parser.parse_args()
    print(json.dumps(measure(args.folder),indent=2,sort_keys=True))
