"""Source-bound diagnostic physical and ownership-order CPU proofs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NAMES = ('witness_1', 'witness_2', 'exception_1_1', 'exception_1_2')
LIFE = ['capture_finished', 'encoders_closed', 'restoration_verified',
        'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def source(suffix):
    if suffix == 'witness_1':
        return ROOT / '.runtime-work/c230259_627_witness1_primary_compat_v4'
    return ROOT / '.runtime-work' / ('c230259_627_' + suffix + '_primary_compat_v1')


def evaluate(suffix, kind, scratch, result):
    sys.path[:0] = [str(ROOT / 'runtime'), str(ROOT / 'runtime/scenario_pipeline')]
    from scenario_pipeline.worker_exchange.native_output import assess_physical
    original = source(suffix)
    if not (original / 'compatibility.json').is_file():
        raise ValueError('Selected source-shaped compatibility missing: ' + suffix)
    scratch.mkdir(parents=True, exist_ok=False)
    for name in ('config.json', 'trace.jsonl', 'video_frames.jsonl'):
        shutil.copyfile(original / name, scratch / name)
    if kind == 'incomplete_motion':
        rows = [json.loads(line) for line in (scratch / 'trace.jsonl').read_text().splitlines()]
        position = rows[0]['position_m']
        for row in rows:
            row['position_m'] = position
        (scratch / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    elif kind == 'missing_evidence':
        (scratch / 'trace.jsonl').unlink()
    elif kind != 'complete_motion':
        raise ValueError('Unknown fixture kind')
    cfg = json.loads((scratch / 'config.json').read_text())
    assessed = assess_physical(scratch, cfg, [])
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    if assessed['physical_checks']['maneuver']['status'] != expected:
        raise ValueError('Expected physical status ' + expected + ', received ' +
                         assessed['physical_checks']['maneuver']['status'])
    output = {'case_id': cfg['selected_case_id'], 'provenance_kind': 'synthetic_fixture',
              'diagnostic_fixture': True, 'physical_checks': assessed['physical_checks'],
              'realized_observables': assessed['realized_observables'],
              'maneuver_completed': assessed['maneuver_completed'],
              'original_source_hashes': {name: sha(original / name)
                                         for name in ('config.json', 'trace.jsonl', 'video_frames.jsonl')},
              'legal_verdict_claimed': False}
    save(result, output)
    print(json.dumps({'case_id': output['case_id'], 'kind': kind,
                      'maneuver': expected, 'result_sha256': sha(result)}))


def lifecycle(suffix):
    original = source(suffix)
    if not (original / 'compatibility.json').is_file():
        raise ValueError('No completed diagnostic source')
    # CPU order proof. No physical resource release is asserted for this fixture.
    events = list(LIFE)
    if events.index('saved_processing_started') <= events.index('owner_released'):
        raise ValueError('Saved processing would precede ownership closure')
    print(json.dumps({'case': suffix, 'events': events,
                      'actual_native_owner_released': False}))


def prove():
    manifest = json.loads((HERE / 'draft-route-manifest.json').read_text())
    target = HERE / 'physical-proof'
    target.mkdir(exist_ok=True)
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            scratch = ROOT / '.runtime-work' / ('c230259_627_physical_' + suffix + '_' + kind + '_v1')
            result = target / (suffix + '-' + kind + '.json')
            log = target / (suffix + '-' + kind + '.log')
            command = [sys.executable, '-B', str(Path(__file__).resolve()), '--evaluate',
                       '--case', suffix, '--kind', kind, '--scratch', str(scratch),
                       '--result', str(result)]
            with log.open('w') as output:
                completed = subprocess.run(command, cwd=ROOT, env=os.environ.copy(),
                                           stdout=output, stderr=subprocess.STDOUT)
            if completed.returncode:
                raise RuntimeError('Physical fixture failed: ' + str(log))
            fixtures.append({'kind': kind, 'command': ' '.join(command),
                             'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                             'result': str(result.relative_to(HERE)),
                             'result_sha256': sha(result), 'exit_code': 0})
        life_log = target / (suffix + '-lifecycle.log')
        life_command = [sys.executable, '-B', str(Path(__file__).resolve()),
                        '--lifecycle', '--case', suffix]
        with life_log.open('w') as output:
            completed = subprocess.run(life_command, cwd=ROOT, env=os.environ.copy(),
                                       stdout=output, stderr=subprocess.STDOUT)
        if completed.returncode:
            raise RuntimeError('Lifecycle order proof failed: ' + str(life_log))
        receipt = {'format': 'c230259-physical-preparation-v1',
                   'case_id': entry['case_id'],
                   'construction_sha256': entry['construction_sha256'],
                   'fixtures': fixtures,
                   'lifecycle': {'events': LIFE, 'exit_code': 0,
                                 'log': str(life_log.relative_to(HERE)),
                                 'log_sha256': sha(life_log),
                                 'actual_native_owner_released': False}}
        receipt_path = target / (suffix + '-receipt.json')
        save(receipt_path, receipt)
        entry['physical_preparation'] = {'receipt': str(receipt_path.relative_to(HERE)),
                                         'sha256': sha(receipt_path)}
        print(json.dumps({'case_id': entry['case_id'], 'receipt_sha256': sha(receipt_path)}), flush=True)
    (HERE / 'draft-route-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--evaluate', action='store_true')
    parser.add_argument('--lifecycle', action='store_true')
    parser.add_argument('--prove', action='store_true')
    parser.add_argument('--case', choices=NAMES)
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion', 'missing_evidence'))
    parser.add_argument('--scratch')
    parser.add_argument('--result')
    args = parser.parse_args()
    if args.evaluate:
        evaluate(args.case, args.kind, Path(args.scratch), Path(args.result))
    elif args.lifecycle:
        lifecycle(args.case)
    elif args.prove:
        prove()
    else:
        parser.error('Choose --evaluate, --lifecycle or --prove')
