"""Author eight exact one-way Native requests without claiming sign authority."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]
CASES = ('designated', 'opposite')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    assignment = ROOT/'inputs'/CASE.name/'assignment.json'
    plan = CASE/'case-plan.json'
    road = HERE/'road.xodr'
    assert all(path.exists() for path in (assignment, plan, road))
    entries = []
    for case in CASES:
        for candidate in CANDIDATES:
            folder = HERE/'drafts'/case/candidate
            folder.mkdir(parents=True, exist_ok=True)
            lane = -2 if candidate == 'fallback2' else -1
            speed = 4 if candidate == 'fallback1' else 8
            if candidate == 'fallback3': speed = 3
            direction = 1 if case == 'designated' else -1
            start_x = -20 if direction == 1 else 220
            rows = []
            for frame in range(240):
                t = round((frame+1)/20, 3)
                if candidate == 'fallback3':
                    distance = min(speed*t, 12)
                    current_speed = speed if speed*t < 12 else 0
                else:
                    distance = speed*t
                    current_speed = speed
                rows.append({'frame': frame, 'time_s': t,
                             'ego_x_m': round(start_x+direction*distance, 4),
                             'ego_y_m': -1.75 if lane == -1 else -5.25,
                             'ego_heading_deg': 0 if direction == 1 else 180,
                             'ego_speed_mps': current_speed,
                             'lane_id': lane, 'requested_direction': case,
                             'source_kind': 'authored_request'})
            track = folder/'requested-tracks.jsonl'
            track.write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in rows))
            config = {'format': 'c150916-native-request-v1',
                      'assignment_id': CASE.name,
                      'case_id': CASE.name+'__'+case,
                      'candidate_id': candidate, 'rate_hz': 20, 'frames': 240,
                      'ego_blueprint': 'vehicle.tesla.model3',
                      'lane_id': lane, 'requested_direction': case,
                      'policy': {'primary': 'constant_speed_traverse',
                                 'fallback1': 'slow_sign_approach',
                                 'fallback2': 'outer_lane_traverse',
                                 'fallback3': 'stop_before_entry'}[candidate],
                      'assignment_sha256': sha(assignment),
                      'case_plan_sha256': sha(plan), 'road_sha256': sha(road),
                      'tracks_sha256': sha(track),
                      'status': 'unselected_native_request'}
            (folder/'config.json').write_text(json.dumps(config, indent=2)+'\n')
            entries.append({'case_id': config['case_id'], 'candidate_id': candidate,
                            'config': str((folder/'config.json').relative_to(CASE)),
                            'config_sha256': sha(folder/'config.json'),
                            'tracks_sha256': sha(track),
                            'status': 'unselected_native_request'})
    result = {'format': 'c150916-native-construction-manifest-v1',
              'assignment_id': CASE.name, 'assignment_sha256': sha(assignment),
              'case_plan_sha256': sha(plan), 'road_sha256': sha(road),
              'entries': entries, 'original_native_observed': False,
              'sign_authority_verified': False, 'delivery_ready': False}
    (HERE/'drafts'/'manifest.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    print(json.dumps({'requests': len(build()['entries'])}))
