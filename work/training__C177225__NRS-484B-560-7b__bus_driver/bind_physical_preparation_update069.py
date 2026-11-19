"""Bind source-tested synthetic physical branches and lifecycle contract."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind():
    manifest = json.loads(MANIFEST.read_text())
    life_log = HERE / 'update069-lifecycle-tests.log'
    if 'OK' not in life_log.read_text():
        raise ValueError('Lifecycle contract tests did not pass')
    for entry in manifest['cases']:
        case_id = entry['case_id']
        case = case_id.removeprefix(HERE.name + '__')
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            result_path = HERE / f'update069-{case}-{kind}-physical.json'
            log_path = HERE / f'update069-{case}-{kind}-physical.log'
            result = json.loads(result_path.read_text())
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            if (result['case_id'] != case_id or
                    result['physical_checks']['maneuver']['status'] != expected or
                    result['provenance_kind'] != 'synthetic_fixture' or
                    result['diagnostic_fixture'] is not True or
                    result['physical_acceptance_claimed'] is not False or
                    result['original_native_observed'] is not False):
                raise ValueError('Physical diagnostic claim/status differs: ' + case + '/' + kind)
            attempt = f'.runtime-work/update068-c177225-{case}-' + (
                'compatibility' if kind == 'complete_motion' else kind)
            command = (f'.venv-cpu/bin/python work/{HERE.name}/physical_outcome.py '
                       f'--attempt {attempt} --case {case_id} '
                       f'--output work/{HERE.name}/{result_path.name}')
            fixtures.append({'kind': kind, 'command': command, 'exit_code': 0,
                             'log': log_path.name, 'log_sha256': sha(log_path),
                             'result': result_path.name, 'result_sha256': sha(result_path),
                             'scope': 'synthetic diagnostic only; no original Native'})
        proof = {'format': 'c177225-physical-preparation-cpu-v1',
                 'case_id': case_id,
                 'construction_sha256': entry['construction_sha256'],
                 'fixtures': fixtures,
                 'lifecycle': {'events': EVENTS, 'exit_code': 0,
                               'log': life_log.name, 'log_sha256': sha(life_log),
                               'scope': 'CPU receipt-ordering test only',
                               'original_owner_released': False},
                 'original_native_observed': False,
                 'physical_acceptance_claimed': False,
                 'legal_verdict_claimed': False}
        path = HERE / f'update069-{case}-physical-preparation.json'
        path.write_text(json.dumps(proof, indent=2) + '\n')
        entry['physical_preparation'] = {'receipt': path.name, 'sha256': sha(path)}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest_sha256': sha(MANIFEST), 'cases': len(manifest['cases'])}))


if __name__ == '__main__':
    bind()
