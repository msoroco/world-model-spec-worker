"""Exercise original-motion completion classifier on synthetic 2b sources.

No fixture result is a claim about realized Native driving or legal compliance.
"""
import argparse
import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.native_output import physical_result, seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release
from worker_exchange.common import sha

SOURCES = ('config.json', 'road_geometry.json', 'body_history.jsonl',
           'video_frames.jsonl', 'trace.jsonl')


def check(attempt):
    case = json.loads((attempt / 'config.json').read_text())['selected_case_id']
    manifest = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    selected = [(i, c) for i, c in enumerate(manifest['cases']) if c['case_id'] == case]
    entry = selected[0][1] if len(selected) == 1 else None
    if entry is None or sha(HERE / entry['construction']) != entry['construction_sha256']:
        raise ValueError('Exact selected construction absent or changed')
    with TemporaryDirectory(dir=REPO / '.runtime-work', prefix='c109705-2b-motion-') as temp:
        root = Path(temp)
        for name in SOURCES:
            os.link(attempt / name, root / name)
        (root / 'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'native', 'diagnostic_fixture': True,
            'scope': 'source-shaped CPU protocol proof only'}) + '\n')
        good = physical_result(root, {'case_id': case, 'target_checks': []})
        if (good['physical_checks']['maneuver']['status'] != 'met' or
                good['physical_checks']['setup']['status'] != 'not_met' or
                good['physical_acceptance_claimed'] is not False):
            raise AssertionError('Expected synthetic motion and incomplete setup')
        body = root / 'body_history.jsonl'
        original = body.read_text()
        body.unlink()
        missing = physical_result(root, {'case_id': case, 'target_checks': []})
        if missing['physical_checks']['maneuver']['status'] != 'unverified':
            raise AssertionError('Missing original body source was not rejected')
        rows = [json.loads(line) for line in original.splitlines() if line.strip()]
        for row in rows:
            if row['road_id'] == 2:
                row['road_id'] = 3
                row['body_vertices_m'] = [[x, 0.0, z] for x, _, z in row['body_vertices_m']]
        body.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        incomplete = physical_result(root, {'case_id': case, 'target_checks': []})
        if incomplete['physical_checks']['maneuver']['status'] != 'not_met':
            raise AssertionError('Incomplete destination turn was not rejected')
        # Lifecycle checker uses source-shaped attempt files and an exact
        # construction. The saved-processing event is bound to the prior
        # successful recorded-only proof, not simulated by this fixture.
        construction = json.loads((HERE / entry['construction']).read_text())
        (root / 'construction.json').write_text(json.dumps(construction) + '\n')
        runner = next(f['content'] for f in construction['files'] if f['path'] == 'runner.py')
        (root / 'runner.py').write_text(runner)
        try:
            seal_capture(root, frames=9, restoration={'restored': True}, errors=[],
                         encoder_exit_codes={'fixture_encoder': 1}, context={'diagnostic_fixture': True})
        except ValueError as error:
            if 'unclosed/failed encoders' not in str(error):
                raise
        else:
            raise AssertionError('Failed encoder was sealed')
        seal = seal_capture(root, frames=9, restoration={'restored': True}, errors=[],
                            encoder_exit_codes={'fixture_encoder': 0}, context={'diagnostic_fixture': True})
        try:
            acknowledge_owner_release(root, root / 'owner-release.json', True)
        except ValueError as error:
            if 'Native process has not exited' not in str(error):
                raise
        else:
            raise AssertionError('Premature owner release passed')
        native = record_native_exit(root)
        owner = acknowledge_owner_release(root, root / 'owner-release.json', True)
        bundle_path = HERE / entry['post_capture']['test_log']
        bundle = json.loads(bundle_path.read_text())
        proof_key = ('saved_processing_probe', 'saved_processing_far',
                     'saved_processing_imaginary_near', 'saved_processing_imaginary_far')[selected[0][0]]
        saved_proof = bundle[proof_key]
        receipt_path = REPO / saved_proof['receipt']
        saved = json.loads(receipt_path.read_text())
        if (sha(bundle_path) != entry['post_capture']['test_log_sha256'] or
                saved_proof['case_id'] != case or saved_proof['exit_code'] != 0 or
                saved_proof['recorded_only'] is not True or
                sha(receipt_path) != saved_proof['receipt_sha256'] or
                saved.get('passed') is not True or saved.get('recorded_only') is not True or
                saved.get('events', [None])[0] != 'saved_processing_started'):
            raise ValueError('Current saved-processing proof absent')
        events = seal['events'] + [native['event'], owner['event'], saved['events'][0]]
        if events != ['capture_finished', 'encoders_closed', 'restoration_verified',
                      'native_exit', 'owner_released', 'saved_processing_started']:
            raise AssertionError('Lifecycle ordering differs')
        return {'case_id': case, 'synthetic_motion': 'met',
                'incomplete_setup': 'not_met', 'missing_body': 'unverified',
                'incomplete_turn': 'not_met', 'lifecycle_events': events,
                'failed_encoder_rejected': True, 'premature_release_rejected': True,
                'physical_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('attempts', nargs='+', type=Path)
    args = parser.parse_args()
    for attempt in args.attempts:
        print(json.dumps(check(attempt), sort_keys=True))


if __name__ == '__main__':
    main()
