"""Unselected, source-bound between-intersections crossing requests."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parents[1]
ROOT = CASE.parents[1]
SOURCE = HERE / 'assignment-source.json' if (HERE / 'assignment-source.json').is_file() else ROOT / 'inputs' / CASE.name / 'assignment.json'
PLAN = HERE / 'case-plan.json' if (HERE / 'case-plan.json').is_file() else CASE / 'case-plan.json'
SOURCE_SHA = '2254705a424b298452a063dfb5d4f1f6d67754ab8b055d5cac789935e7252d07'
PLAN_SHA = '6f0e6cb201c525afd05d718702178be731e185b6360a403aaa218b60b6b37c0c'
LAW = ('Except as provided in NRS 484B.290 [LVMC-11-30-140-B]: Between adjacent '
       'intersections at which official traffic-control devices are in operation '
       'pedestrians shall not cross at any place except in a marked crosswalk.')
FRAMES = 600
RATE = 20
CASES = {'marked_crosswalk': 40.0, 'unmarked_midblock': 60.0}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(crossing):
    """Requested pedestrian path across an authored road between x=0 and x=100."""
    x = CASES[crossing]
    for frame in range(FRAMES):
        time_s = (frame + 1) / RATE
        y = max(-10.0, min(10.0, (time_s - 15.0) * 2.0))
        yield {'frame': frame, 'time_s': time_s, 'requested_x_m': x,
               'requested_y_m': round(y, 6), 'roadway_entry_y_m': -4.0,
               'intersection_a_x_m': 0.0, 'intersection_b_x_m': 100.0,
               'marked_crosswalk_x_m': 40.0,
               'requested_crossing_location': crossing,
               'adjacent_intersections_native_verified': False,
               'official_devices_operating_verified': False,
               'crosswalk_marking_native_verified': False,
               'pedestrian_native_observed': False, 'legal_verdict': None}


def build():
    assignment = json.loads(SOURCE.read_text())
    plan = json.loads(PLAN.read_text())
    if (sha(SOURCE) != SOURCE_SHA or sha(PLAN) != PLAN_SHA or
            assignment['law']['text'] != LAW or plan['source_law_text'] != LAW or
            assignment['actor'] != 'pedestrian' or
            assignment['cell']['layout'] != 'intersection' or
            {c['requested_setting'] for c in plan['cases']} != set(CASES)):
        raise ValueError('Frozen source or crossing plan changed')
    entries = []
    for crossing in CASES:
        bundle = HERE / 'drafts' / crossing
        bundle.mkdir(parents=True, exist_ok=True)
        (bundle / 'assignment-source.json').write_bytes(SOURCE.read_bytes())
        (bundle / 'case-plan.json').write_bytes(PLAN.read_bytes())
        track = bundle / 'requested-tracks.jsonl'
        track.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows(crossing)))
        cfg = {'format': 'c109166-pedestrian-crossing-request-v1',
               'assignment_id': CASE.name, 'case_id': CASE.name + '__' + crossing,
               'candidate_id': 'primary', 'requested_crossing_location': crossing,
               'assignment_sha256': sha(SOURCE), 'case_plan_sha256': sha(PLAN),
               'tracks_sha256': sha(track), 'frames': FRAMES, 'rate_hz': RATE,
               'duration_s': 30, 'adjacent_intersections_native_verified': False,
               'official_devices_operating_verified': False,
               'crosswalk_marking_native_verified': False,
               'pedestrian_native_observed': False, 'legal_verdict': None,
               'status': 'unselected_cpu_request'}
        config = bundle / 'config.json'
        config.write_text(json.dumps(cfg, indent=2) + '\n')
        entries.append({'case_id': cfg['case_id'], 'config_sha256': sha(config),
                        'tracks_sha256': sha(track)})
    manifest = {'format': 'c109166-unselected-crossing-requests-v1',
                'assignment_id': CASE.name, 'assignment_sha256': sha(SOURCE),
                'case_plan_sha256': sha(PLAN), 'entries': entries,
                'pedestrian_native_observed': False, 'delivery_ready': False}
    (HERE / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    print(json.dumps({'requests': len(build()['entries'])}))
