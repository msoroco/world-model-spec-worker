"""Audit synthetic lead-position pair from exact saved sources, without a verdict."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from conflict_controller import decision

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
LEAD_FIELDS = ('lead_pose_xyz_m', 'lead_body_vertices_xyz_m')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decoded(path):
    run = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path),
        '-map', '0:v:0', '-f', 'framemd5', '-'], capture_output=True, text=True)
    require(run.returncode == 0, 'Source camera cannot decode: '+str(path))
    lines = [line for line in run.stdout.splitlines()
             if line and not line.startswith('#')]
    require(len(lines) == 600, 'Source camera does not contain 600 frames')
    return hashlib.sha256(('\n'.join(lines)+'\n').encode()).hexdigest()


def audit(conflict, clear):
    conflict, clear = Path(conflict), Path(clear)
    plan = read(HERE/'case-plan.json')
    assignment = HERE.name
    pair = next(row for row in plan['comparisons'] if row['comparison_id'] ==
                assignment+'__comparison_lead_position')
    require(pair['case_ids'] == [assignment+'__conflict', assignment+'__clear'] and
            pair['deliberate_differences'] == ['lead_spawn_xy_m'],
            'Lead comparison plan differs')
    sources = []
    for case, directory in (('conflict', conflict), ('clear', clear)):
        result = read(directory/'result.json')
        report = read(directory/'analysis-report.json')
        provenance = read(directory/'acquisition-provenance.json')
        require(result['case_id'] == assignment+'__'+case and
                report['case_id'] == result['case_id'] and
                result['provenance_kind'] == 'synthetic_fixture' and
                provenance['provenance_kind'] == 'synthetic_fixture' and
                result['accepted'] is False and
                result['physical_acceptance_claimed'] is False and
                result['legal_verdict_claimed'] is False,
                case+' is not an exact unaccepted diagnostic')
        require(result['target_checks'][0]['matched'] is True,
                case+' sampled target failed')
        for name, checksum in report['source_sha256'].items():
            require(sha(directory/name) == checksum,
                    case+' saved source hash differs: '+name)
        actor = rows(directory/'native-actors.jsonl')
        frame = rows(directory/'video_frames.jsonl')
        survey = read(directory/'native-survey-readback.json')
        require(len(actor) == len(frame) == 600 and
                result['measured_values']['source_frames'] == 600,
                case+' source frame count differs')
        sources.append((directory,result,actor,frame,survey))
    left, right = sources
    require(left[3] == right[3] and
            sha(left[0]/'video_frames.jsonl') == sha(right[0]/'video_frames.jsonl'),
            'Lead comparison clocks differ')
    left_survey, right_survey = left[4].copy(), right[4].copy()
    left_probe = left_survey.pop('conflict_probe')
    right_probe = right_survey.pop('conflict_probe')
    require(left_survey == right_survey and
            {key: value for key,value in left_probe.items() if key != 'lead_spawn_xy_m'} ==
            {key: value for key,value in right_probe.items() if key != 'lead_spawn_xy_m'} and
            left_probe['lead_spawn_xy_m'] == [18,1] and
            right_probe['lead_spawn_xy_m'] == [35,1],
            'Lead comparison changed fixed survey or wrong lead position')
    for index,(a,b) in enumerate(zip(left[2],right[2])):
        ac, bc = a.copy(), b.copy()
        a_pose, b_pose = ac.pop('lead_pose_xyz_m'), bc.pop('lead_pose_xyz_m')
        a_body, b_body = ac.pop('lead_body_vertices_xyz_m'), bc.pop('lead_body_vertices_xyz_m')
        a_control, b_control = ac.pop('requested_control'), bc.pop('requested_control')
        expected_a = decision(a['ego_pose_xyz_m'][:2],
                              a['ego_velocity_xyz_mps'][:2],
                              a_pose[:2], a['lead_velocity_xyz_mps'][:2],
                              a['ego_yaw_deg'])
        expected_b = decision(b['ego_pose_xyz_m'][:2],
                              b['ego_velocity_xyz_mps'][:2],
                              b_pose[:2], b['lead_velocity_xyz_mps'][:2],
                              b['ego_yaw_deg'])
        require(ac == bc and a_pose == [18,1,0] and b_pose == [35,1,0] and
                len(a_body) == len(b_body) and
                all([bv[0]-av[0], bv[1]-av[1], bv[2]-av[2]] == [17,0,0]
                    for av,bv in zip(a_body,b_body)) and
                a_control == expected_a and b_control == expected_b,
                'Lead comparison altered another source field at '+str(index))
    require(left[1]['measured_values']['brake_request_frames'] == 1 and
            right[1]['measured_values']['brake_request_frames'] == 0,
            'Lead comparison brake-request counts differ')
    camera_hashes = {}
    for camera in CAMERAS:
        a = decoded(left[0]/(camera+'.mkv'))
        b = decoded(right[0]/(camera+'.mkv'))
        require(a == b, 'Fixed synthetic camera pixels differ: '+camera)
        camera_hashes[camera] = a
    return {'format':'c201084-lead-position-diagnostic-audit-v1',
            'comparison_id':pair['comparison_id'], 'passed':True,
            'diagnostic_only':True, 'source_cases':pair['case_ids'],
            'conflict_result_sha256':sha(left[0]/'result.json'),
            'clear_result_sha256':sha(right[0]/'result.json'),
            'conflict_actor_source_sha256':sha(left[0]/'native-actors.jsonl'),
            'clear_actor_source_sha256':sha(right[0]/'native-actors.jsonl'),
            'decoded_fixed_camera_sha256':camera_hashes,
            'lead_spawn_xy_m':{'conflict':[18,1], 'clear':[35,1]},
            'synthetic_brake_request_frames':{'conflict':left[1]['measured_values']['brake_request_frames'],
                                               'clear':right[1]['measured_values']['brake_request_frames']},
            'statutory_necessity_verified':False,
            'original_native_verified':False,
            'physical_or_legal_acceptance_claimed':False}


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--conflict',type=Path,required=True)
    parser.add_argument('--clear',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    require(not args.output.exists(), 'Retain previous audit output')
    result=audit(args.conflict,args.clear)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'passed':result['passed'],'diagnostic_only':True},sort_keys=True))
