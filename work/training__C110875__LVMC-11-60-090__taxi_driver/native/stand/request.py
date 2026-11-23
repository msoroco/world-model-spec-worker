"""Source-bound, unselected taxi-stand departure requests for CPU diagnosis."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parents[1]
ROOT = CASE.parents[1]
SOURCE = HERE / 'assignment-source.json' if (HERE / 'assignment-source.json').is_file() else ROOT / 'inputs' / CASE.name / 'assignment.json'
PLAN = HERE / 'case-plan.json' if (HERE / 'case-plan.json').is_file() else CASE / 'case-plan.json'
SOURCE_SHA = '966c41984789f72b6a2f89785fcb6abdfbc7c9e5a1a57a38db7dd920eef1f863'
PLAN_SHA = 'd4059f6ec667b0a709dc41a5279486f7b906982b77d87751d12ba74e2f89227a'
FRAMES = 600
RATE = 20
CASES = {'probe_01': 'right', 'probe_02': 'straight'}
LAW = ('Any cab, upon leaving any stand designated in accordance with the provisions '
       'of this Section, shall execute a right-hand turn, when a sign is posted giving '
       'notice of this requirement, at the first street intersection after it leaves such stand.')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def route(direction):
    """Authored path: stand, first crossing at x=80, second crossing at x=130."""
    rows = []
    for frame in range(FRAMES):
        t = (frame + 1) / RATE
        x = min(80.0, 5.0 + 5.0 * t)
        south = max(0.0, 5.0 * t - 75.0) if direction == 'right' else 0.0
        if direction == 'straight' and 5.0 * t > 75.0:
            x = min(145.0, 80.0 + 5.0 * t - 75.0)
        rows.append({'frame': frame, 'time_s': t, 'requested_x_m': round(x, 6),
                     'requested_y_m': round(-south, 6), 'requested_heading_deg':
                     -90 if direction == 'right' and south > 0 else 0,
                     'first_intersection_station_m': 80.0,
                     'next_intersection_station_m': 130.0,
                     'cab_stand_departure_station_m': 5.0,
                     'stand_designation_verified': False,
                     'posted_notice_verified': False,
                     'taxi_license_verified': False,
                     'first_intersection_native_verified': False,
                     'original_native_observed': False,
                     'legal_verdict': None})
    return rows


def build():
    source = json.loads(SOURCE.read_text())
    plan = json.loads(PLAN.read_text())
    if (sha(SOURCE) != SOURCE_SHA or sha(PLAN) != PLAN_SHA or
            source['law']['text'] != LAW or plan['source_law_text'] != LAW or
            source['cell']['layout'] != 'intersection' or
            source['cell']['maneuver'] != 'right_turn' or
            source['cell']['control'] != 'mandatory_turn_sign' or
            source['actor'] != 'taxi_driver'):
        raise ValueError('Current taxi law, cell or actor source changed')
    entries = []
    for suffix, direction in CASES.items():
        directory = HERE / 'drafts' / suffix
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'assignment-source.json').write_bytes(SOURCE.read_bytes())
        (directory / 'case-plan.json').write_bytes(PLAN.read_bytes())
        path = directory / 'requested-tracks.jsonl'
        path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in route(direction)))
        config = {'format': 'c110875-taxi-stand-request-v1', 'assignment_id': CASE.name,
                  'case_id': CASE.name + '__' + suffix, 'candidate_id': 'primary',
                  'requested_first_turn': direction, 'assignment_sha256': sha(SOURCE),
                  'case_plan_sha256': sha(PLAN), 'tracks_sha256': sha(path),
                  'rate_hz': RATE, 'frames': FRAMES, 'duration_s': FRAMES / RATE,
                  'stand_designation_verified': False, 'posted_notice_verified': False,
                  'taxi_license_verified': False, 'first_intersection_native_verified': False,
                  'original_native_observed': False, 'legal_verdict': None,
                  'status': 'unselected_cpu_request'}
        cfg = directory / 'config.json'
        cfg.write_text(json.dumps(config, indent=2) + '\n')
        entries.append({'case_id': config['case_id'], 'candidate_id': 'primary',
                        'config_sha256': sha(cfg), 'tracks_sha256': sha(path)})
    manifest = {'format': 'c110875-taxi-stand-draft-requests-v1',
                'assignment_id': CASE.name, 'assignment_sha256': sha(SOURCE),
                'case_plan_sha256': sha(PLAN), 'entries': entries,
                'original_native_observed': False, 'delivery_ready': False}
    (HERE / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    print(json.dumps({'requests': len(build()['entries'])}))
