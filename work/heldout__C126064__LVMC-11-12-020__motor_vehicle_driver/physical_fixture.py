"""Exercise three source-shaped marked-turn motion outcomes, without CARLA."""
import argparse
from hashlib import sha256
import json
from math import hypot
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def rows(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def run(case, kind):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next((item for item in manifest['cases'] if item['case_id'] == case), None)
    if entry is None or kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown marked-turn physical fixture')
    recipe = json.loads((REPO / entry['fixture_recipe']).read_text())
    files = json.loads((REPO / recipe['generator']['source']).read_text())['files']
    names = ('turn_body.jsonl', 'video_frames.jsonl', 'trace.jsonl', 'marked_intersection.json')
    if any(name not in files for name in names):
        raise ValueError('Missing original-shaped marked-turn source')
    sources = {name: sha256(files[name].encode()).hexdigest() for name in names}
    if kind == 'missing_evidence':
        sources.pop('turn_body.jsonl')
        status, observed = 'unverified', {}
    else:
        body = rows(files['turn_body.jsonl'])
        mapping = rows(files['video_frames.jsonl'])
        trace = rows(files['trace.jsonl'])
        if not len(body) == len(mapping) == len(trace) or len(body) < 2:
            raise ValueError('Original marked-turn motion inventory incomplete')
        identities = [(row['frame'], row['time_s']) for row in body]
        if (identities != [(row['carla_frame'], row['time_s']) for row in mapping]
                or identities != [(row['frame'], row['time_s']) for row in trace]):
            raise ValueError('Original marked-turn frame join differs')
        points = [[sum(corner[i] for corner in row['corners_xy_m']) / 4 for i in (0, 1)]
                  for row in body]
        if kind == 'incomplete_motion':
            points = [points[0] for _ in points]
            sources['turn_body.jsonl'] = sha256(json.dumps(points).encode()).hexdigest()
        path = sum(hypot(b[0]-a[0], b[1]-a[1]) for a, b in zip(points, points[1:]))
        status = 'met' if path > 4 and hypot(points[-1][0]-points[0][0],
                                            points[-1][1]-points[0][1]) > 4 else 'not_met'
        observed = {'first_frame': identities[0][0], 'last_frame': identities[-1][0],
                    'sampled_body_path_m': path, 'first_body_centre_xy_m': points[0],
                    'last_body_centre_xy_m': points[-1],
                    'engineering_criterion_not_legal': True}
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    if status != expected:
        raise ValueError('Marked-turn fixture did not exercise requested outcome')
    return {'case_id': case, 'fixture_kind': kind, 'diagnostic_fixture': True,
            'actual_native_capture': False, 'provenance_kind': 'native',
            'physical_checks': {'maneuver': {'status': status,
                'method': 'joined original-shaped full-body turn path; 4 m engineering fixture criterion only',
                'sources': sources,
                'missing_evidence': ['turn_body.jsonl'] if kind == 'missing_evidence' else []}},
            'maneuver_completed': status == 'met', 'realized_observables': observed,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = run(args.case, args.kind)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(args.case, args.kind, result['physical_checks']['maneuver']['status'],
          'synthetic_fixture_only')
