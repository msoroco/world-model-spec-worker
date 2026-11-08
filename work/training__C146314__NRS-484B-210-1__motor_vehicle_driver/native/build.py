"""Author source-bound one-way right-pass requests; never claim observed behavior."""
import hashlib
import json
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parents[1]
NATIVE = CASE / 'native'
POLICIES = {
    'primary': {'ego_speed_mps': 8.0, 'camera': 'standard', 'stop_x_m': None},
    'fallback1': {'ego_speed_mps': 7.0, 'camera': 'standard', 'stop_x_m': None},
    'fallback2': {'ego_speed_mps': 8.0, 'camera': 'elevated_overview', 'stop_x_m': None},
    'fallback3': {'ego_speed_mps': 8.0, 'camera': 'standard', 'stop_x_m': 45.0},
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def put_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, sort_keys=True, allow_nan=False) + '\n'
                            for row in rows))


def road():
    return '''<?xml version="1.0" encoding="UTF-8"?>
<OpenDRIVE><header revMajor="1" revMinor="4" name="C146314 one-way pass request" version="1.00" date="2026-11-08" north="4" south="-8" east="300" west="0" vendor="worker"/>
<road name="two-line one-way authored pavement" length="300" id="210" junction="-1">
<type s="0" type="town"><speed max="35" unit="mph"/></type>
<planView><geometry s="0" x="0" y="0" hdg="0" length="300"><line/></geometry></planView>
<lanes><laneSection s="0"><center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" color="yellow" width="0.15"/></lane></center>
<right><lane id="-1" type="driving" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="broken" color="white" width="0.12"/></lane>
<lane id="-2" type="driving" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" color="white" width="0.12"/></lane></right></laneSection></lanes>
<objects/><signals/></road></OpenDRIVE>
'''


def build():
    NATIVE.mkdir(parents=True, exist_ok=True)
    road_path = NATIVE / 'one-way-pass.xodr'
    road_path.write_text(road())
    assignment = ROOT / 'inputs' / CASE.name / 'assignment.json'
    plan = CASE / 'case-plan.json'
    entries = []
    for witness in ('witness_1', 'witness_2'):
        obstruction = witness == 'witness_2'
        for candidate, policy in POLICIES.items():
            rows = []
            for i in range(240):
                t = (i + 1) / 20
                x = min(policy['stop_x_m'] or 300, policy['ego_speed_mps'] * t)
                # The route requests a lane change and return; observed actor
                # motion and clear pavement must be measured after Native capture.
                right = max(0.0, min(1.0, (x - 15) / 20, (105 - x) / 20))
                y = -1.75 - 3.5 * right
                lead_x = 30 + 4 * t
                phase = ('approach' if x < 15 else 'right_excursion' if x < 85
                         else 'return')
                rows.append({
                    'frame': i, 'time_s': t, 'source_kind': 'authored_native_request',
                    'case_id': CASE.name + '__' + witness,
                    'candidate_id': candidate, 'phase': phase, 'road_id': 210,
                    'ego_x_m': round(x, 6), 'ego_y_m': round(y, 6),
                    'ego_lane_id': -2 if y < -3.5 else -1,
                    'lead_x_m': round(lead_x, 6), 'lead_y_m': -1.75,
                    'lead_lane_id': -1,
                    'right_lane_obstruction_requested': obstruction,
                    'obstruction_x_m': 55 if obstruction else None,
                    'obstruction_lane_id': -2 if obstruction else None,
                    'one_way_designation_verified': False,
                    'unobstructed_pavement_verified': False,
                    'actual_right_pass_observed': False,
                    'legal_verdict': None,
                })
            target = NATIVE / 'drafts' / witness / candidate
            track = target / 'requested-tracks.jsonl'
            put_rows(track, rows)
            cfg = {
                'format': 'c146314-right-pass-request-v1',
                'assignment_id': CASE.name, 'case_id': CASE.name + '__' + witness,
                'candidate_id': candidate, 'law_id': 'NRS-484B-210-1',
                'cell_id': 'C146314', 'actor': 'motor_vehicle_driver',
                'rate_hz': 20, 'frames': 240, 'road_sha256': sha(road_path),
                'tracks_sha256': sha(track), 'assignment_sha256': sha(assignment),
                'case_plan_sha256': sha(plan), 'camera_policy': policy['camera'],
                'requested_ego_speed_mps': policy['ego_speed_mps'],
                'stop_x_m': policy['stop_x_m'],
                'right_lane_obstruction_requested': obstruction,
                'obstruction_x_m': 55 if obstruction else None,
                'actual_right_pass_observed': False,
                'one_way_designation_verified': False,
                'original_native_observed': False,
                'status': 'unselected_native_request',
            }
            put(target / 'config.json', cfg)
            entries.append({'case_id': cfg['case_id'], 'candidate_id': candidate,
                            'config_sha256': sha(target / 'config.json'),
                            'tracks_sha256': sha(track),
                            'status': 'unselected_native_request'})
    manifest = {'format': 'c146314-right-pass-construction-v1',
                'assignment_id': CASE.name, 'assignment_sha256': sha(assignment),
                'case_plan_sha256': sha(plan), 'road_sha256': sha(road_path),
                'entries': entries, 'original_native_observed': False,
                'delivery_ready': False}
    put(NATIVE / 'manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    print(json.dumps({'requests': len(build()['entries'])}))
