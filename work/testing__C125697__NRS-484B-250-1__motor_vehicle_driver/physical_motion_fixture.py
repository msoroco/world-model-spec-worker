"""Source-bound synthetic CPU check of the authored intersection-clearance rule."""
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


def read(path):
    return json.loads(Path(path).read_text())


def run(case, kind, output=None):
    manifest = read(HERE / 'execution-manifest.json')
    entry = next((e for e in manifest['cases'] if e['case_id'] == case), None)
    if entry is None:
        raise ValueError('Unknown exact case')
    construction_path = HERE / entry['construction']
    if sha(construction_path) != entry['construction_sha256']:
        raise ValueError('Exact construction changed')
    construction = read(construction_path)
    config = json.loads(next(f['content'] for f in construction['files'] if f['path'] == 'config.json'))
    criterion = config['physical_completion']
    if (criterion['criterion'] != 'intersection_clearance' or
            criterion['motion_source'] != 'crossing_history.jsonl' or
            criterion['body_key'] != 'ego.body_vertices_xy_m' or
            criterion['intersection_polygon_xy_m'] != config['site']['crossing_polygon_xy_m'] or
            criterion['exit_axis'] != 0 or criterion['exit_sign'] != 1):
        raise ValueError('Authored physical completion criterion changed')
    recipe = read(REPO / entry['fixture_recipe'])
    source = REPO / recipe['generator']['source']
    if sha(source) != recipe['generator']['sha256']:
        raise ValueError('Synthetic diagnostic source changed')
    files = read(source)['files']
    with tempfile.TemporaryDirectory(prefix='c125697-sub1-physical-') as temp:
        attempt = Path(temp)
        (attempt / 'config.json').write_text(json.dumps(config) + '\n')
        for name in ('trace.jsonl', 'video_frames.jsonl', 'crossing_history.jsonl', 'junction_context.json'):
            (attempt / name).write_text(files[name])
        (attempt / 'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}) + '\n')
        motion = attempt / 'crossing_history.jsonl'
        if kind == 'missing_evidence':
            motion.unlink()
        else:
            rows = [json.loads(line) for line in motion.read_text().splitlines()]
            first = copy.deepcopy(rows[0]['ego']['body_vertices_xy_m'])
            for index, row in enumerate(rows):
                offset = 29.0 * index / (len(rows) - 1) if kind == 'complete_motion' else 0.0
                body = [[x + offset, y] for x, y in first]
                row['ego']['body_vertices_xy_m'] = body
                row['ego_vertices_m'] = copy.deepcopy(body)
            motion.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        result = physical_result(attempt, {'target_checks': []})
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    actual = result['physical_checks']['maneuver']
    if (actual['status'] != expected or result['maneuver_completed'] != (expected == 'met') or
            not actual['method'] or not actual['sources'] or
            result['provenance_kind'] != 'synthetic_fixture' or
            result['diagnostic_fixture'] is not True or
            result['physical_acceptance_claimed'] is not False):
        raise AssertionError('Physical classifier did not establish expected synthetic outcome')
    if expected == 'met' and not result['realized_observables']:
        raise AssertionError('Complete synthetic motion has no diagnostic observations')
    if output:
        Path(output).write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return {'case_id': case, 'kind': kind, 'status': expected,
            'diagnostic_fixture': True, 'physical_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion', 'missing_evidence'), required=True)
    parser.add_argument('--output')
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.kind, args.output), sort_keys=True))
