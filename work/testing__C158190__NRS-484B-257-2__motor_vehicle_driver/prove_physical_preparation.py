"""Exercise physical outcome and ownership lifecycle on source-shaped CPU fixtures."""
import argparse
import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))

from worker_exchange.common import sha
from worker_exchange.native_output import physical_result, seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release

SOURCES = ('config.json', 'entry_history.jsonl', 'intersection_context.json',
           'video_frames.jsonl', 'trace.jsonl')


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def check(attempt, saved_receipt, output):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    case = json.loads((attempt / 'config.json').read_text())['selected_case_id']
    entries = [item for item in manifest['cases'] if item['case_id'] == case]
    if len(entries) != 1 or sha(HERE / entries[0]['construction']) != entries[0]['construction_sha256']:
        raise ValueError('Exact selected construction absent or changed')
    saved = json.loads(saved_receipt.read_text())
    if (saved.get('case_id') != case or saved.get('passed') is not True or
            saved.get('recorded_only') is not True or
            saved.get('events', [None])[0] != 'saved_processing_started'):
        raise ValueError('Current recorded-only saved-processing proof absent')
    with TemporaryDirectory(dir=REPO / '.runtime-work', prefix='c158190-motion-') as temporary:
        root = Path(temporary)
        for name in SOURCES:
            os.link(attempt / name, root / name)
        write(root / 'acquisition-provenance.json', {
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'native_capture': False, 'physical_acceptance_claimed': False})
        template = {'case_id': case, 'target_checks': []}
        good = physical_result(root, dict(template))
        if good['physical_checks']['maneuver']['status'] != 'met' or not good['realized_observables']:
            raise AssertionError('Original fixture did not complete authored clearance')
        write(output / 'complete_motion.json', good)

        history = root / 'entry_history.jsonl'
        original = history.read_text()
        history.unlink()
        missing = physical_result(root, dict(template))
        if missing['physical_checks']['maneuver']['status'] != 'unverified':
            raise AssertionError('Missing motion source was not rejected')
        write(output / 'missing_evidence.json', missing)

        rows = [json.loads(line) for line in original.splitlines() if line.strip()]
        for row in rows:
            vertices = row['ego']['body_vertices_m']
            if row['frame'] >= rows[-1]['frame']:
                row['ego']['body_vertices_m'] = [[min(x, 5.0), y, z] for x, y, z in vertices]
        history.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        incomplete = physical_result(root, dict(template))
        if incomplete['physical_checks']['maneuver']['status'] != 'not_met':
            raise AssertionError('Incomplete exit was not rejected')
        write(output / 'incomplete_motion.json', incomplete)

        construction = json.loads((HERE / entries[0]['construction']).read_text())
        write(root / 'construction.json', construction)
        runner = next(item['content'] for item in construction['files'] if item['path'] == 'runner.py')
        (root / 'runner.py').write_text(runner)
        try:
            seal_capture(root, frames=4, restoration={'restored': True}, errors=[],
                         encoder_exit_codes={'fixture_encoder': 1}, context={'diagnostic_fixture': True})
        except ValueError as error:
            if 'unclosed/failed encoders' not in str(error):
                raise
        else:
            raise AssertionError('Failed encoder was sealed')
        seal = seal_capture(root, frames=4, restoration={'restored': True}, errors=[],
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
        events = seal['events'] + [native['event'], owner['event'], saved['events'][0]]
        expected = ['capture_finished', 'encoders_closed', 'restoration_verified',
                    'native_exit', 'owner_released', 'saved_processing_started']
        if events != expected:
            raise AssertionError('Lifecycle ordering differs')
        return {'case_id': case, 'fixture_outcomes': ['met', 'not_met', 'unverified'],
                'lifecycle_events': events, 'failed_encoder_rejected': True,
                'premature_release_rejected': True, 'physical_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('attempt', type=Path)
    parser.add_argument('saved_receipt', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.attempt, args.saved_receipt, args.output), sort_keys=True))
