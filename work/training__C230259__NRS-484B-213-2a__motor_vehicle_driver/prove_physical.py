"""Exercise physical outcomes and saved processing ownership order on CPU fixtures."""
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
NAMES = ('probe_a', 'probe_b', 'curve_right', 'curve_left', 'one_way_crest', 'one_way_curve')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def source(suffix):
    return ROOT / '.runtime-work/nrs213-resume-3' / ('compat-primary-' + suffix)


def evaluate(suffix, kind, scratch, result):
    sys.path[:0] = [str(ROOT / 'runtime'), str(ROOT / 'runtime/scenario_pipeline')]
    from scenario_pipeline.worker_exchange.native_output import assess_physical

    original = source(suffix)
    if not (original / 'compatibility.json').is_file():
        raise ValueError('Selected positive compatibility source missing: ' + suffix)
    scratch.mkdir(parents=True, exist_ok=False)
    for name in ('config.json', 'trace.jsonl', 'video_frames.jsonl'):
        shutil.copyfile(original / name, scratch / name)
    if kind == 'incomplete_motion':
        rows = [json.loads(line) for line in (scratch / 'trace.jsonl').read_text().splitlines()]
        first = rows[0]['position_m']
        for row in rows:
            row['position_m'] = first
        (scratch / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    elif kind == 'missing_evidence':
        (scratch / 'trace.jsonl').unlink()
    elif kind != 'complete_motion':
        raise ValueError('Unknown fixture kind')
    config = json.loads((scratch / 'config.json').read_text())
    assessed = assess_physical(scratch, config, [])
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    if assessed['physical_checks']['maneuver']['status'] != expected:
        raise ValueError('Expected ' + expected + ', got ' +
                         assessed['physical_checks']['maneuver']['status'])
    result_value = {'case_id': config['selected_case_id'],
                    'provenance_kind': 'synthetic_fixture',
                    'diagnostic_fixture': True,
                    'physical_checks': assessed['physical_checks'],
                    'realized_observables': assessed['realized_observables'],
                    'maneuver_completed': assessed['maneuver_completed'],
                    'source_hashes': {name: sha(original / name)
                                      for name in ('config.json', 'trace.jsonl', 'video_frames.jsonl')},
                    'legal_verdict_claimed': False}
    save(result, result_value)
    print(json.dumps({'case_id': result_value['case_id'], 'kind': kind,
                      'status': expected, 'result_sha256': sha(result)}))


def lifecycle(suffix):
    if not (source(suffix) / 'compatibility.json').is_file():
        raise ValueError('Selected positive compatibility source missing')
    if EVENTS.index('saved_processing_started') <= EVENTS.index('owner_released'):
        raise ValueError('Saved processing precedes owner release')
    print(json.dumps({'case': suffix, 'events': EVENTS,
                      'native_owner_released_in_fixture': False}))


def prove(only=None):
    selected = json.loads((HERE / 'selected-construction-draft.json').read_text())
    target = HERE / 'physical-proof'
    target.mkdir(exist_ok=True)
    for entry in selected['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        if only and suffix != only:
            continue
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            scratch = ROOT / '.runtime-work/nrs213-resume-3' / ('physical-' + suffix + '-' + kind)
            result = target / (suffix + '-' + kind + '.json')
            log = target / (suffix + '-' + kind + '.log')
            command = [sys.executable, '-B', str(Path(__file__).resolve()), '--evaluate',
                       '--case', suffix, '--kind', kind, '--scratch', str(scratch),
                       '--result', str(result)]
            with log.open('w') as out:
                completed = subprocess.run(command, cwd=ROOT, env=os.environ.copy(),
                                           stdout=out, stderr=subprocess.STDOUT)
            if completed.returncode:
                raise RuntimeError('Physical fixture failed: ' + str(log))
            fixtures.append({'kind': kind, 'command': ' '.join(command),
                             'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                             'result': str(result.relative_to(HERE)),
                             'result_sha256': sha(result), 'exit_code': 0})
        life_log = target / (suffix + '-lifecycle.log')
        life_command = [sys.executable, '-B', str(Path(__file__).resolve()),
                        '--lifecycle', '--case', suffix]
        with life_log.open('w') as out:
            completed = subprocess.run(life_command, cwd=ROOT, env=os.environ.copy(),
                                       stdout=out, stderr=subprocess.STDOUT)
        if completed.returncode:
            raise RuntimeError('Lifecycle fixture failed: ' + str(life_log))
        receipt = {'format': 'c230259-213-2a-physical-preparation-v1',
                   'case_id': entry['case_id'],
                   'construction_sha256': entry['construction_sha256'],
                   'fixtures': fixtures,
                   'lifecycle': {'events': EVENTS, 'exit_code': 0,
                                 'log': str(life_log.relative_to(HERE)),
                                 'log_sha256': sha(life_log),
                                 'actual_native_owner_released': False}}
        receipt_path = target / (suffix + '-receipt.json')
        save(receipt_path, receipt)
        print(json.dumps({'case_id': entry['case_id'], 'receipt_sha256': sha(receipt_path)}),
              flush=True)


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
        prove(args.case)
    else:
        parser.error('Select a proof mode')
