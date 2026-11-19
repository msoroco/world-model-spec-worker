"""Exercise three source-joined motion outcomes using synthetic CPU packets.

The displacement is an engineering fixture condition, never a legal finding or
an observation of Native motion.
"""

import argparse
from hashlib import sha256
import json
from math import hypot
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KINDS = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
         'missing_evidence': 'unverified'}


def digest(data):
    return sha256(data.encode()).hexdigest()


def rows(data):
    return [json.loads(line) for line in data.splitlines() if line.strip()]


def center(row):
    vertices = row['vertices_m']
    if len(vertices) < 4:
        raise ValueError('Original-shaped body has too few vertices')
    return [sum(point[axis] for point in vertices) / len(vertices)
            for axis in (0, 1)]


def run(case_id, kind):
    if kind not in KINDS:
        raise ValueError('Unknown physical fixture outcome')
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next((item for item in manifest['cases'] if item['case_id'] == case_id), None)
    if entry is None:
        raise ValueError('Unknown exact case')
    recipe_path = ROOT / entry['fixture_recipe']
    recipe = json.loads(recipe_path.read_text())
    source_path = ROOT / recipe['generator']['source']
    source_bytes = source_path.read_bytes()
    if sha256(source_bytes).hexdigest() != recipe['generator']['sha256']:
        raise ValueError('Diagnostic generator source changed')
    originals = json.loads(source_bytes)['files']
    frames = rows(originals['video_frames.jsonl'])
    body = rows(originals['body_history.jsonl'])
    if len(frames) != len(body) or len(body) < 3:
        raise ValueError('Original-shaped body/frame count differs')
    for video, sample in zip(frames, body):
        if (video['carla_frame'], video['time_s']) != (sample['frame'], sample['time_s']):
            raise ValueError('Original-shaped body/frame join differs')
    if kind == 'complete_motion':
        for index, sample in enumerate(body):
            sample['vertices_m'] = [[point[0] + index, *point[1:]]
                                    for point in sample['vertices_m']]
    if kind == 'missing_evidence':
        measured = None
        status = 'unverified'
        body_hash = None
    else:
        first, last = center(body[0]), center(body[-1])
        measured = hypot(last[0] - first[0], last[1] - first[1])
        status = 'met' if measured >= 5.0 else 'not_met'
        body_hash = digest(''.join(json.dumps(row, sort_keys=True) + '\n' for row in body))
    if status != KINDS[kind]:
        raise ValueError('Synthetic motion outcome differs: ' + status)
    return {
        'format': 'worker-physical-fixture-outcome', 'case_id': case_id,
        'fixture_kind': kind, 'diagnostic_fixture': True,
        'actual_native_capture': False, 'provenance_kind': 'synthetic_fixture',
        'physical_checks': {'maneuver': {
            'status': status,
            'method': 'join synthetic original-shaped body/frame packets and measure body-center displacement; five meters is only a fixture test threshold',
            'sources': {'diagnostic': str(source_path.relative_to(ROOT)),
                        'diagnostic_sha256': sha256(source_bytes).hexdigest(),
                        'video_frames_sha256': digest(originals['video_frames.jsonl']),
                        'body_history_sha256': body_hash,
                        'construction_sha256': entry['construction_sha256']},
            'missing_evidence': ['body_history.jsonl'] if kind == 'missing_evidence' else [],
        }},
        'maneuver_completed': status == 'met',
        'realized_observables': ({'synthetic_body_center_displacement_m': measured,
                                  'synthetic_frames': len(frames)} if status == 'met' else {}),
        'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
    }


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
