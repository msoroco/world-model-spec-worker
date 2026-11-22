"""CPU challenge sweep of the authored wheelchair encounter controller.

These samples are engineering probes, not statutory thresholds or CARLA evidence.
"""
import hashlib
import json
from pathlib import Path

from runner import control, encounter, load_scene

ROOT = Path(__file__).resolve().parent


def body(x, y):
    return [[x, y, 0], [x + 1, y, 0], [x + 1, y + 1, 0], [x, y + 1, 0]]


def probe(scene, speed, target_ttc, path):
    # The body gap is measured from the ego front to the person/chair back.
    # This placement makes target_ttc the measured, not merely declared, TTC.
    ego = body(-1 - speed * target_ttc, 0)
    y = -3 if path == 'crossing' else 5
    person = {'role': 'person_in_manual_wheelchair', 'source_ref': 'cpu/person',
              'body_vertices_m': body(0, y)}
    chair = {'kind': 'manual_wheelchair', 'source_ref': 'cpu/chair',
             'body_vertices_m': body(0, y)}
    measurement = encounter(scene, ego, person, chair, speed,
                            scene['pedestrian_target_speed_mps'] if path == 'crossing' else 0)
    command = control(scene, measurement)
    return {'path': path, 'ego_speed_mps': speed, 'target_ttc_s': target_ttc,
            'measured_ttc_s': measurement['time_to_path_s'],
            'surface_gap_m': measurement['surface_gap_m'],
            'brake': command['brake'], 'legal_due_care_verdict': command['legal_due_care_verdict']}


def sweep(scene=None):
    scene = scene or load_scene()
    boundary = scene['engineering_ttc_brake_s']
    if boundary <= 0 or scene['pedestrian_target_speed_mps'] <= 0:
        raise ValueError('invalid authored engineering response inputs')
    records = [probe(scene, speed, boundary + offset, path)
               for speed in (2.0, 4.0)
               for offset in (-0.5, 0.0, 0.5)
               for path in ('crossing', 'clear_path')]
    for row in records:
        expected = float(row['path'] == 'crossing' and
                         row['target_ttc_s'] <= boundary)
        if abs(row['measured_ttc_s'] - row['target_ttc_s']) > 1e-9 or row['brake'] != expected:
            raise ValueError('constructed geometry or engineering response differs from sweep')
        if row['legal_due_care_verdict'] is not None:
            raise ValueError('engineering sweep asserted a legal verdict')
    return {'format': 'worker-wheelchair-engineering-sweep',
            'assignment_id': ROOT.name,
            'scene_sha256': hashlib.sha256((ROOT/'scene.json').read_bytes()).hexdigest(),
            'source': 'worker-authored scene and body geometry; synthetic CPU challenge only',
            'engineering_ttc_brake_s': boundary, 'records': records,
            'legal_due_care_verdict': None,
            'remaining': 'Source-backed feasible encounter range and original Native response sweep require review.'}


if __name__ == '__main__':
    print(json.dumps(sweep(), indent=2))
