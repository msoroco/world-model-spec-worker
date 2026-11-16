"""CPU protocol for road-half motion from joined original-shaped diagnostic sources.

All three outcomes are synthetic and establish no realized CARLA or legal fact.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(case_id, kind):
    if kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('unknown physical outcome')
    cases = json.loads((HERE / 'execution-manifest.json').read_text())['cases']
    entry = next((item for item in cases if item['case_id'] == case_id), None)
    if entry is None:
        raise ValueError('unknown exact road-half case')
    recipe = json.loads((ROOT / entry['fixture_recipe']).read_text())
    source = ROOT / recipe['generator']['source']
    if sha(source) != recipe['generator']['sha256']:
        raise ValueError('diagnostic source hash changed')
    originals = json.loads(source.read_text())['files']
    module = importlib.util.spec_from_file_location('road_half_fixture_measure', HERE / 'road_half.py')
    road_half = importlib.util.module_from_spec(module)
    module.loader.exec_module(road_half)
    names = ('road_geometry.json', 'exception_context.json', 'body_history.jsonl',
             'video_frames.jsonl')
    context = json.loads(originals['exception_context.json'])
    feature = {'posted_one_way': 'one_way_sign_original.json',
               'right_half_closed': 'closure_original.json',
               'overtaking_same_direction': 'passed_vehicle_original.json',
               'insufficient_width': 'width_survey_original.json',
               'three_lanes': 'lane_survey_original.json'}.get(context['exception'])
    if feature:
        names += (feature,)
    with TemporaryDirectory(prefix='road-half-motion-', dir=ROOT / '.runtime-work') as tmp:
        base = Path(tmp)
        for name in names:
            (base / name).write_text(originals[name])
        body_path = base / 'body_history.jsonl'
        if kind == 'missing_evidence':
            body_path.unlink()
        elif kind == 'complete_motion':
            rows = [json.loads(line) for line in body_path.read_text().splitlines()]
            if len(rows) < 2:
                raise ValueError('no original body sequence')
            for i, row in enumerate(rows):
                progress = 8.0 * i / (len(rows) - 1)
                row['ground_corners'] = [[x + progress, y] for x, y in row['ground_corners']]
            body_path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
        sources = {name: sha(base / name) for name in names if (base / name).is_file()}
        if not body_path.is_file():
            status = 'unverified'
            measured = None
            observables = {}
        else:
            measured = road_half.measure_saved(base)
            body = [json.loads(line) for line in body_path.read_text().splitlines()]
            centers = [[sum(p[j] for p in row['ground_corners']) / 4 for j in (0, 1)]
                       for row in body]
            from math import hypot
            displacement = hypot(centers[-1][0] - centers[0][0],
                                 centers[-1][1] - centers[0][1])
            status = 'met' if displacement >= 5.0 else 'not_met'
            observables = {'first_frame': measured['original_frames'][0],
                           'last_frame': measured['original_frames'][-1],
                           'center_displacement_m': displacement,
                           'any_left_half_body': measured['any_left_half_body']}
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError('fixture motion outcome differs: ' + status + ' != ' + expected)
        return {'case_id': case_id, 'fixture_kind': kind, 'diagnostic_fixture': True,
                'actual_native_capture': False, 'provenance_kind': 'native',
                'provenance_note': 'Native-shaped synthetic source protocol only',
                'physical_checks': {'maneuver': {'status': status,
                    'method': 'join original-shaped body and frame sources, validate road/exception source hashes, measure center displacement; five-meter engineering fixture criterion',
                    'sources': sources, 'missing_evidence': ['body_history.jsonl'] if kind == 'missing_evidence' else []}},
                'maneuver_completed': status == 'met', 'realized_observables': observables,
                'road_half_measurement': measured,
                'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = run(args.case, args.kind)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(args.case, args.kind, result['physical_checks']['maneuver']['status'], 'synthetic_fixture_only')
