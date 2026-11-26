"""Exercise the authored walker progress criterion on source-shaped CPU traces."""

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime'))
from scenario_pipeline.worker_exchange.native_output import assess_physical


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def prove(side, kind):
    source = BASE / 'diagnostic' / side / 'sources'
    config = json.loads((BASE / ('construction.json' if side == 'a' else
                                  'cases/condition_b/construction.json')).read_text())
    config = json.loads(next(item['content'] for item in config['files']
                             if item['path'] == 'config.json'))
    scratch = ROOT / '.runtime-work'
    with tempfile.TemporaryDirectory(prefix='c230259-physical-', dir=scratch) as temporary:
        attempt = Path(temporary)
        for name in ('video_frames.jsonl', 'trace.jsonl', 'reviewed-road-source.json'):
            if kind == 'missing_evidence' and name == 'reviewed-road-source.json':
                continue
            shutil.copy2(source / name, attempt / name)
        write(attempt / 'config.json', config)
        if kind == 'incomplete_motion':
            rows = [json.loads(line) for line in (attempt / 'trace.jsonl').read_text().splitlines()]
            for row in rows:
                row['position_m'][0] = 20.0
                row['position']['x'] = 20.0
                row['velocity_mps'] = [0.0, 0.0, 0.0]
                row['speed_mps'] = 0.0
            (attempt / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
        assessment = assess_physical(attempt, config)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        observed = assessment['physical_checks']['maneuver']['status']
        if observed != expected or assessment['maneuver_completed'] != (expected == 'met'):
            raise AssertionError(f'{kind}: expected {expected}, got {observed}')
        result = {**assessment, 'provenance_kind': 'synthetic_fixture',
                  'diagnostic_fixture': True, 'original_native_observed': False,
                  'accepted': False, 'legal_verdict_claimed': False}
        folder = BASE / 'physical-proof' / ('condition_' + side)
        result_path = folder / (kind + '.json')
        log_path = folder / (kind + '.log')
        write(result_path, result)
        log_path.write_text(f'{kind}: {expected}; sampled physical criterion only\n')
        return {'kind': kind,
                'command': '.venv-cpu/bin/python -B work/' + BASE.name + '/native/prove_physical.py',
                'exit_code': 0, 'log': str(log_path.relative_to(BASE)),
                'log_sha256': sha(log_path), 'result': str(result_path.relative_to(BASE)),
                'result_sha256': sha(result_path)}


def main():
    runner = (BASE / 'native/runner.py').read_text()
    ordered = ('capture.close(', 'encoder.stdin.close()', 'restored = restore(',
               'compose_four_views(', 'seal_capture(', 'write_result(output, physical_result(')
    positions = [runner.rfind(item) for item in ordered]
    if -1 in positions or positions != sorted(positions):
        raise AssertionError('Native capture closure/restoration/seal order changed')
    events = ['capture_finished', 'encoders_closed', 'restoration_verified',
              'native_exit', 'owner_released', 'saved_processing_started']
    manifest = json.loads((BASE / 'execution-manifest.json').read_text())
    for side, entry in zip('ab', manifest['cases']):
        fixtures = [prove(side, kind) for kind in
                    ('complete_motion', 'incomplete_motion', 'missing_evidence')]
        folder = BASE / 'physical-proof' / ('condition_' + side)
        life_log = folder / 'lifecycle.log'
        life_log.write_text('Native source order checked: ' + ', '.join(ordered) + '\n' +
                            '\n'.join(events) + '\n')
        proof = {'format': 'worker-physical-preparation-proof-v1',
                 'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
                 'fixtures': fixtures, 'lifecycle': {'events': events, 'exit_code': 0,
                                                       'log': str(life_log.relative_to(BASE)),
                                                       'log_sha256': sha(life_log)},
                 'original_native_observed': False}
        proof_path = folder / 'proof.json'
        write(proof_path, proof)
        entry['physical_preparation'] = {'receipt': str(proof_path.relative_to(BASE)),
                                         'sha256': sha(proof_path)}
    write(BASE / 'execution-manifest.json', manifest)
    print(json.dumps({'physical_cases_proven': [entry['case_id'] for entry in manifest['cases']]}))


if __name__ == '__main__':
    main()
