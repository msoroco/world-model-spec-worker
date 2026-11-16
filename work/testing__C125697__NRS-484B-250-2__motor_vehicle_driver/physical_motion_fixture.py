"""CPU proof of the first case's source-bound crossing completion classifier.

The fixture alters synthetic original bodies in a temporary directory. It does
not amend captured evidence or assert that CARLA can realize the path.
"""
import argparse
import copy
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))

from worker_exchange.common import sha  # noqa: E402
from worker_exchange.native_output import physical_result  # noqa: E402


CASE = HERE.name + '__off_ego_left_near_time'


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def run(kind):
    manifest = read(HERE / 'execution-manifest.json')
    entry = next(row for row in manifest['cases'] if row['case_id'] == CASE)
    construction_path = HERE / entry['construction']
    if sha(construction_path) != entry['construction_sha256']:
        raise ValueError('Exact primary construction changed')
    construction = read(construction_path)
    config = json.loads(next(row['content'] for row in construction['files']
                             if row['path'] == 'config.json'))
    recipe = read(REPO / entry['fixture_recipe'])
    source_path = REPO / recipe['generator']['source']
    if sha(source_path) != recipe['generator']['sha256']:
        raise ValueError('Synthetic diagnostic source changed')
    sources = read(source_path)['files']
    polygon = config['site']['crossing_polygon_xy_m']
    config['physical_completion'] = {
        'criterion': 'intersection_clearance',
        'motion_source': 'crossing_history.jsonl',
        'body_key': 'ego_vertices_m',
        'intersection_polygon_xy_m': polygon,
        'exit_axis': 0,
        'exit_sign': 1,
        'minimum_progress_m': 0.25,
        'engineering_tolerances_not_legal': True,
    }
    with tempfile.TemporaryDirectory(prefix='c125697-motion-') as temporary:
        attempt = Path(temporary)
        write(attempt / 'config.json', config)
        for name in ('trace.jsonl', 'video_frames.jsonl', 'crossing_history.jsonl'):
            (attempt / name).write_text(sources[name])
        write(attempt / 'acquisition-provenance.json', {
            'provenance_kind': 'native', 'diagnostic_fixture': True,
            'scope': 'Synthetic CPU classifier fixture only',
        })
        motion = attempt / 'crossing_history.jsonl'
        if kind == 'missing_evidence':
            motion.unlink()
        else:
            rows = [json.loads(line) for line in motion.read_text().splitlines()]
            first = copy.deepcopy(rows[0]['ego_vertices_m'])
            for index, row in enumerate(rows):
                offset = (29.0 * index / (len(rows) - 1)) if kind == 'complete_motion' else 0.0
                body = [[x + offset, y] for x, y in first]
                row['ego_vertices_m'] = body
                row['ego']['body_vertices_xy_m'] = copy.deepcopy(body)
            motion.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))
        result = physical_result(attempt, {'target_checks': []})
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        check = result['physical_checks']['maneuver']
        if check['status'] != expected or result['maneuver_completed'] != (expected == 'met'):
            raise AssertionError(f'Expected {expected}; got {check["status"]}')
        if not check['method'] or not check['sources']:
            raise AssertionError('Classifier omitted original source binding')
        if result['physical_acceptance_claimed'] is not False:
            raise AssertionError('Synthetic fixture claimed physical acceptance')
        return {'case_id': CASE, 'fixture': kind, 'maneuver_status': expected,
                'diagnostic_fixture': True, 'source_hashes': check['sources']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', required=True, choices=('complete_motion',
                        'incomplete_motion', 'missing_evidence'))
    args = parser.parse_args()
    print(json.dumps(run(args.kind), sort_keys=True))
