"""Exercise physical outcome classifications on synthetic, source-bound fixtures.

These are diagnostic classifier tests, not Native physical-preparation receipts.
"""

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.native_output import assess_physical

SOURCE = REPO / '.runtime-work/c158190-yield_nearest_view_through_approaches-primary-stable-v1-compat'
NEEDED = ('config.json', 'video_frames.jsonl', 'trace.jsonl',
          'interaction_history.jsonl', 'control_context.json')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def result(root, kind):
    cfg = json.loads((root / 'config.json').read_text())
    assessment = assess_physical(root, cfg, [])
    check = assessment['physical_checks']['maneuver']
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    if check['status'] != expected or assessment['maneuver_completed'] != (expected == 'met'):
        raise AssertionError(f'{kind}: expected {expected}, got {check["status"]}')
    if not check['method'] or not check['sources']:
        raise AssertionError(f'{kind}: missing source-bound assessment')
    return {'kind': kind, 'status': check['status'], 'method': check['method'],
            'source_sha256': check['sources'],
            'maneuver_completed': assessment['maneuver_completed'],
            'diagnostic_fixture': True, 'provenance_kind': 'synthetic_fixture',
            'physical_acceptance_claimed': False}


def main():
    if not all((SOURCE / name).is_file() for name in NEEDED):
        raise ValueError('Fresh stable compatibility attempt is missing')
    original_result = json.loads((SOURCE / 'result.json').read_text())
    if (original_result.get('provenance_kind') != 'synthetic_fixture'
            or original_result.get('physical_acceptance_claimed') is not False):
        raise ValueError('Diagnostic source provenance is not explicitly synthetic')
    source_hashes = {name: sha(SOURCE / name) for name in NEEDED}
    outcomes = []
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work', prefix='c158190-outcomes-') as temp:
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            root = Path(temp) / kind
            root.mkdir()
            for name in NEEDED:
                shutil.copyfile(SOURCE / name, root / name)
            if kind == 'incomplete_motion':
                path = root / 'interaction_history.jsonl'
                rows = [json.loads(line) for line in path.read_text().splitlines()]
                first = rows[0]['ego']
                for row in rows:
                    row['ego']['body_vertices_m'] = first['body_vertices_m']
                    row['ego']['road_id'] = first['road_id']
                    row['ego']['lane_id'] = first['lane_id']
                path.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))
            elif kind == 'missing_evidence':
                (root / 'interaction_history.jsonl').unlink()
            outcomes.append(result(root, kind))
    if any(sha(SOURCE / name) != digest for name, digest in source_hashes.items()):
        raise AssertionError('Diagnostic outcome tests changed original attempt')
    report = {'format': 'worker-c158190-physical-outcome-diagnostic',
              'source_attempt': str(SOURCE.relative_to(REPO)),
              'source_sha256': source_hashes, 'fixtures': outcomes,
              'physical_preparation_receipt': False,
              'limitation': 'Synthetic sources exercise classifier branches; no Native provenance or physical acceptance.'}
    output = HERE / 'physical-outcome-diagnostics.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'statuses': [f['status'] for f in outcomes],
                      'physical_preparation_receipt': False,
                      'report': str(output.relative_to(REPO))}))


if __name__ == '__main__':
    main()
