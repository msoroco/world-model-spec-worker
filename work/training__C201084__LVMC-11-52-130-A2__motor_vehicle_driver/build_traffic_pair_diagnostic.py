"""Make a labelled 600-frame optional-lead diagnostic from synthetic sources."""
import argparse
import json
import shutil
from pathlib import Path

from traffic_pair_controller import request

HERE=Path(__file__).resolve().parent
ASSIGNMENT=HERE.name
CAMERAS=('overview','approach','reference_corner','driver_reference')
LEAD_FIELDS=('lead_actor_id','lead_road_id','lead_lane_id',
             'lead_pose_xyz_m','lead_yaw_deg','lead_velocity_xyz_mps',
             'lead_body_vertices_xyz_m')


def build(source, output, mode):
    if mode not in ('near_lead','absent_lead'):
        raise ValueError('Unknown traffic-pair mode')
    source,output=Path(source).resolve(),Path(output).resolve()
    if '.runtime-work' not in source.parts or '.runtime-work' not in output.parts:
        raise ValueError('Diagnostic source and output must stay under .runtime-work')
    if output.exists():
        raise ValueError('Retain prior diagnostic output; choose a fresh directory')
    output.mkdir(parents=True)
    for name in ('video_frames.jsonl',*[camera+'.mkv' for camera in CAMERAS]):
        shutil.copyfile(source/name,output/name)
    provenance=json.loads((source/'acquisition-provenance.json').read_text())
    if provenance.get('provenance_kind')!='synthetic_fixture' or \
            provenance.get('diagnostic_fixture') is not True:
        raise ValueError('Source is not an explicitly synthetic fixture')
    (output/'acquisition-provenance.json').write_text(
        json.dumps(provenance,indent=2)+'\n')
    plan=json.loads((source/'native-survey-readback.json').read_text())
    present=mode=='near_lead'
    plan['traffic_pair']={'mode':mode,'lead_present':present,
        'destination_xy_m':[30,1],
        'statutory_necessity_verified':False,
        'original_review_required':True}
    if not present:
        plan.pop('conflict_probe',None)
    (output/'native-survey-readback.json').write_text(
        json.dumps(plan,indent=2)+'\n')
    actors=[json.loads(line) for line in
            (source/'native-actors.jsonl').read_text().splitlines()]
    if len(actors)!=600 or any(row.get('source_kind')!='synthetic_native_sample'
                               for row in actors):
        raise ValueError('Expected 600 explicitly synthetic source rows')
    for actor in actors:
        if not present:
            for key in LEAD_FIELDS:
                actor.pop(key,None)
        actor['lead_present']=present
        actor['requested_control']=request(
            actor['ego_pose_xyz_m'][:2], actor['ego_yaw_deg'],
            actor['ego_velocity_xyz_mps'], [30,1],
            lead_xy_m=actor['lead_pose_xyz_m'][:2] if present else None,
            lead_velocity_xyz_mps=actor['lead_velocity_xyz_mps'] if present else None)
        actor['physical_completion_claimed']=False
        actor['statutory_necessity_claimed']=False
    (output/'native-actors.jsonl').write_text(''.join(
        json.dumps(row,allow_nan=False)+'\n' for row in actors))
    reference=json.loads((HERE/'draft-reference-construction.json').read_text())
    config=json.loads(next(row['content'] for row in reference['files']
                           if row['path']=='config.json'))
    case=ASSIGNMENT+'__'+mode
    config.update(case_id=case, selected_case_id=case,
                  case_suffix=mode,candidate_id='primary',
                  comparison_requested_value=present)
    config['recording_description']['channels'].append({
        'name':'lead_traffic_presence','unit':'bool',
        'sampling_rate_hz':20,
        'reference_frame':'original CARLA actor and frame source',
        'time_window':'all 600 frames / 30 seconds',
        'method':'source-joined lead actor presence and optional relation',
        'uncertainty':'50 ms sample clock; statutory necessity requires original review'})
    (output/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    return {'case_id':case,'source_frames':600,'diagnostic_fixture':True,
            'physical_acceptance_claimed':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mode',choices=('near_lead','absent_lead'),required=True)
    args=parser.parse_args()
    print(json.dumps(build(args.source,args.output,args.mode),sort_keys=True))
