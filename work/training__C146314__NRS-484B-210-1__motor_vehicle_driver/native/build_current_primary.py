"""Build a 30-second, four-camera paragraph (d) CPU diagnostic draft.

This records requested motion, not a Native observation or delivery selection.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]
OUT = HERE / 'current-primary'
CASE_ID = CASE.name + '__witness_1'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'one-way-pass.xodr').write_bytes((HERE / 'one-way-pass.xodr').read_bytes())
    (OUT / 'assignment-source.json').write_bytes(
        (ROOT / 'inputs' / CASE.name / 'assignment.json').read_bytes())
    (OUT / 'case-plan.json').write_bytes((CASE / 'case-plan.json').read_bytes())
    rows = []
    for frame in range(600):
        time_s = (frame + 1) / 20
        x = 5 + 8 * time_s
        right = max(0.0, min(1.0, (x - 15) / 20, (105 - x) / 20))
        y = -1.75 - 3.5 * right
        rows.append({'frame': frame, 'time_s': time_s,
            'source_kind': 'authored_native_request', 'case_id': CASE_ID,
            'candidate_id': 'primary', 'road_id': 210,
            'ego_x_m': round(x, 6), 'ego_y_m': round(y, 6),
            'ego_lane_id': -2 if y < -3.5 else -1,
            'lead_x_m': round(35 + 4 * time_s, 6), 'lead_y_m': -1.75,
            'lead_lane_id': -1, 'one_way_designation_verified': False,
            'unobstructed_pavement_verified': False,
            'actual_right_pass_observed': False, 'legal_verdict': None})
    (OUT / 'requested-tracks.jsonl').write_text(''.join(
        json.dumps(row, sort_keys=True, allow_nan=False) + '\n' for row in rows))
    cfg = {'format': 'c146314-current-primary-request-v1',
        'assignment_id': CASE.name, 'case_id': CASE_ID,
        'candidate_id': 'primary', 'law_id': 'NRS-484B-210-1',
        'cell_id': 'C146314', 'actor': 'motor_vehicle_driver',
        'rate_hz': 20, 'frames': 600, 'duration_s': 30,
        'camera_names': list(CAMERAS),
        'camera_profile': 'overview1080-capability',
        'requested_ego_speed_mps': 8.0,
        'road_sha256': sha(OUT / 'one-way-pass.xodr'),
        'tracks_sha256': sha(OUT / 'requested-tracks.jsonl'),
        'assignment_sha256': sha(OUT / 'assignment-source.json'),
        'case_plan_sha256': sha(OUT / 'case-plan.json'),
        'original_native_observed': False, 'delivery_ready': False,
        'status': 'unselected_cpu_diagnostic'}
    put(OUT / 'config.json', cfg)
    (OUT / 'check.py').write_bytes((HERE / 'current_primary_check.py').read_bytes())
    (OUT / 'capture.py').write_bytes((HERE / 'current_primary_capture.py').read_bytes())
    (OUT / 'saved.py').write_bytes((HERE / 'current_primary_saved.py').read_bytes())
    tests = OUT / 'tests'
    tests.mkdir(exist_ok=True)
    (tests / 'test_exact.py').write_bytes((HERE / 'current_primary_test.py').read_bytes())
    files = ['config.json', 'requested-tracks.jsonl', 'one-way-pass.xodr',
        'assignment-source.json', 'case-plan.json', 'check.py', 'capture.py', 'saved.py',
        'tests/test_exact.py']
    construction = {'case_id': CASE_ID, 'cell_id': 'C146314',
        'law_id': 'NRS-484B-210-1', 'actor': 'motor_vehicle_driver',
        'entrypoint': 'capture.py', 'status': 'unselected_cpu_diagnostic',
        'recording_description': 'Requested right pass on authored one-way two-lane road; original Native motion and four synchronized source-camera videos remain to be captured.',
        'files': [{'path': name, 'content': (OUT / name).read_text()}
                  for name in files]}
    put(OUT / 'construction.json', construction)
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
        'assignment_id': CASE.name, 'status': 'draft_not_selected',
        'cases': [{'case_id': CASE_ID,
            'construction': 'construction.json',
            'construction_sha256': sha(OUT / 'construction.json'),
            'candidates': [], 'candidate_risk': {'status': 'physical',
                'reason': 'Original pass, road designation, clearance and camera pixels are unverified.'}}],
        'original_native_observed': False, 'delivery_ready': False}
    put(OUT / 'manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    print(json.dumps({'cases': len(build()['cases']), 'frames': 600,
                      'cameras': list(CAMERAS)}))
