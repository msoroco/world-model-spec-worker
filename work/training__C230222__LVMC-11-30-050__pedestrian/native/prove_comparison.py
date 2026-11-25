"""CPU positive and mutation checks for the independent route comparison."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from comparison_audit import audit, sha
from route_meter import measure_files


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2) + '\n')


def reject(a, b, ca, cb, message, diagnostic=True):
    try:
        audit(a, b, ca, cb, diagnostic)
    except ValueError as exc:
        if message not in str(exc):
            raise AssertionError(f'Wrong rejection: {exc}') from exc
        return str(exc)
    raise AssertionError('Missing rejection: ' + message)


def main():
    root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve() / 'lvmc-route-comparison'
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    context = {'source_kind': 'synthetic_cpu_fixture', 'expected_frames': 600,
               'origin_curb_xy_m': [[-3.5, -20], [-3.5, 20]],
               'opposite_curb_xy_m': [[3.5, -20], [3.5, 20]],
               'crosswalk_polygons_xy_m': [],
               'road_geometry_sha256': sha(HERE / 'road.xodr')}
    rows = {}
    contexts = {}
    for condition in ('a', 'b'):
        path = root / condition
        path.mkdir()
        samples = []
        for frame in range(600):
            fraction = min(1.0, frame / 300)
            y = 0.0 if condition == 'a' else 2.8 * fraction
            samples.append({'native_frame': frame + 10, 'pedestrian_xy_m': [-3.5 + 7 * fraction, y],
                            'pedestrian_id': 11, 'time_s': frame / 20})
        (path / 'samples.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in samples))
        write(path / 'context.json', context)
        rows[condition] = measure_files(path / 'samples.jsonl', path / 'context.json', path / 'report.json')
        contexts[condition] = {**context, 'source_sha256': sha(path / 'context.json')}
    a, b, ca, cb = rows['a'], rows['b'], contexts['a'], contexts['b']
    positive = audit(a, b, ca, cb, diagnostic=True)
    negatives = []
    negatives.append(reject(a, b, ca, cb, 'Original Native route source required', False))
    mutated = copy.deepcopy(b)
    mutated['right_angle_deviation_deg'] = 0
    negatives.append(reject(a, mutated, ca, cb, 'Declared route geometry difference absent'))
    mutated = copy.deepcopy(b)
    mutated['route_excess_length_m'] = 0
    negatives.append(reject(a, mutated, ca, cb, 'Declared route length difference absent'))
    mutated = copy.deepcopy(cb)
    mutated['opposite_curb_xy_m'] = [[4, -20], [4, 20]]
    negatives.append(reject(a, b, ca, mutated, 'Fixed road/curb/crosswalk condition differs'))
    mutated = copy.deepcopy(b)
    mutated['crosswalk_sample_count'] = 1
    negatives.append(reject(a, mutated, ca, cb, 'Outside-crosswalk fixed condition differs'))
    mutated = copy.deepcopy(b)
    mutated['entry_xy_m'] = [-2.5, 0]
    negatives.append(reject(a, mutated, ca, cb, 'Compared entries differ'))
    proof = {'format': 'worker-route-comparison-cpu-proof-v1', 'positive': positive,
             'negative_rejections': negatives, 'source_kind': 'synthetic_cpu_fixture',
             'original_native_observed': False,
             'comparison_auditor_sha256': sha(HERE / 'comparison_audit.py')}
    out = HERE / 'comparison-proof.json'
    write(out, proof)
    print(json.dumps({'proof': str(out), 'sha256': sha(out), 'rejections': len(negatives)}))


if __name__ == '__main__':
    main()
