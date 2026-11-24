"""Source-bound diagnostic for the two NRS 484B.400(1) lane branches.

The right-only design predicate must come from a retained Native map survey.
An authored arrow or requested lane ID cannot establish that predicate.
"""
import hashlib
import json
from pathlib import Path

FRAMES=600
LAW_PATHS={
    '400-1':'inputs/training__C382355__NRS-484B-400-1__motor_vehicle_driver/assignment.json',
    '223-4a':'inputs/training__C382355__NRS-484B-223-4a__motor_vehicle_driver/assignment.json',
    '223-4b':'inputs/training__C382389__NRS-484B-223-4b__motor_vehicle_driver/assignment.json',
}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(repo,source_dir,case_id):
    repo=Path(repo);source_dir=Path(source_dir)
    law_file=source_dir/'law-bindings.json'
    design_file=source_dir/'lane-design.json'
    actors_file=source_dir/'actor-lane-sources.jsonl'
    laws=json.loads(law_file.read_text());design=json.loads(design_file.read_text())
    for key,path in LAW_PATHS.items():
        assignment=repo/path
        if laws.get(key,{}).get('input_sha256')!=sha(assignment):
            raise ValueError('Frozen law input binding changed: '+key)
        data=json.loads(assignment.read_text())
        if laws[key].get('law_sha256')!=data['local_snapshot']['law_sha256']:
            raise ValueError('Frozen law text binding changed: '+key)
    if design.get('case_id')!=case_id:
        raise ValueError('Lane design case mismatch')
    if design.get('source_kind') not in ('synthetic_cpu','original_native'):
        raise ValueError('Lane design source kind missing')
    if design.get('design_source')!='native_map_survey':
        raise ValueError('Native lane design survey required')
    if not isinstance(design.get('single_right_only_turn_lane'),bool):
        raise ValueError('Single right-only lane design fact missing')
    if not isinstance(design.get('rightmost_lane_id'),int):
        raise ValueError('Rightmost lane readback missing')
    if not isinstance(design.get('turn_connector_lane_id'),int):
        raise ValueError('Turn connector readback missing')
    if design['single_right_only_turn_lane']:
        if not isinstance(design.get('designated_turn_lane_id'),int):
            raise ValueError('Designated right-turn lane readback missing')
        required=design['designated_turn_lane_id']
        branch='single_right_only_turn_lane'
    else:
        required=design['rightmost_lane_id']
        branch='extreme_right_lane'
    rows=[json.loads(line) for line in actors_file.read_text().splitlines()]
    if len(rows)!=FRAMES or [r.get('frame') for r in rows]!=list(range(FRAMES)):
        raise ValueError('Incomplete original actor lane frames')
    approach=[];turn=[]
    for frame,row in enumerate(rows):
        if row.get('case_id')!=case_id or abs(float(row.get('time_s',-1))-frame/20)>1e-5:
            raise ValueError('Actor source case/frame time mismatch')
        phase=row.get('phase')
        if phase not in ('approach','turn','post_turn'):
            raise ValueError('Source phase missing')
        if not isinstance(row.get('road_id'),int) or not isinstance(row.get('lane_id'),int):
            raise ValueError('Native road/lane readback missing')
        if phase=='approach':approach.append(row['lane_id']==required)
        if phase=='turn':turn.append(row['lane_id']==design['turn_connector_lane_id'])
    if not approach or not turn:
        raise ValueError('Approach and turn source spans required')
    return {'format':'c382355-400-1-lane-branch-measurement-v1',
            'case_id':case_id,'source_kind':design['source_kind'],
            'branch':branch,'required_approach_lane_id':required,
            'required_turn_connector_lane_id':design['turn_connector_lane_id'],
            'approach_frames':len(approach),'turn_frames':len(turn),
            'required_approach_fraction':sum(approach)/len(approach),
            'required_turn_fraction':sum(turn)/len(turn),
            'all_required_spans_observed':True,
            'authored_arrow_establishes_design':False,
            'native_design_physically_verified':False,
            'intention_observed_directly':False,
            'legal_verdict':None,'delivery_ready':False,
            'source_sha256':{'law-bindings.json':sha(law_file),
                             'lane-design.json':sha(design_file),
                             'actor-lane-sources.jsonl':sha(actors_file)}}
