"""Bind synthetic physical-outcome and lifecycle CPU proofs to each case."""
import hashlib
import json
from pathlib import Path

from build_selected import CASES

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
SCRIPT = 'work/' + PACKAGE.name + '/native/prove_physical.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = PACKAGE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for suffix, entry in zip(CASES, manifest['cases']):
        folder = PACKAGE / 'physical' / suffix
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            result = folder / (kind + '.json')
            log = folder / (kind + '.log')
            record = json.loads(result.read_text())
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            if (record['physical_checks']['maneuver']['status'] != expected or
                    record['construction_sha256'] != entry['construction_sha256']):
                raise ValueError('Physical fixture incomplete: ' + suffix + ' ' + kind)
            fixtures.append({'kind': kind,
                             'command': '.venv-cpu/bin/python ' + SCRIPT + ' --case ' +
                                        entry['case_id'] + ' --kind ' + kind + ' --output work/' +
                                        PACKAGE.name + '/physical/' + suffix + '/' + kind + '.json',
                             'exit_code': 0,
                             'log': str(log.relative_to(PACKAGE)),
                             'log_sha256': sha(log),
                             'result': str(result.relative_to(PACKAGE)),
                             'result_sha256': sha(result)})
        lifecycle_result = folder / 'lifecycle.json'
        lifecycle_log = folder / 'lifecycle.log'
        lifecycle = json.loads(lifecycle_result.read_text())
        if lifecycle['events'] != ['capture_finished', 'encoders_closed',
                                   'restoration_verified', 'native_exit',
                                   'owner_released', 'saved_processing_started']:
            raise ValueError('Lifecycle order changed')
        proof = {'format': 'c245490-physical-preparation-v1',
                 'case_id': entry['case_id'],
                 'construction_sha256': entry['construction_sha256'],
                 'script': SCRIPT, 'script_sha256': sha(PACKAGE / 'native/prove_physical.py'),
                 'fixtures': fixtures,
                 'lifecycle': {'events': lifecycle['events'], 'exit_code': 0,
                               'command': '.venv-cpu/bin/python ' + SCRIPT + ' --case ' +
                                          entry['case_id'] + ' --kind lifecycle --output work/' +
                                          PACKAGE.name + '/physical/' + suffix + '/lifecycle.json',
                               'log': str(lifecycle_log.relative_to(PACKAGE)),
                               'log_sha256': sha(lifecycle_log)},
                 'original_native_motion_verified': False,
                 'scope': 'labelled synthetic source outcomes and lifecycle order only'}
        path = folder / 'proof.json'
        path.write_text(json.dumps(proof, indent=2) + '\n')
        entry['physical_preparation'] = {'receipt': str(path.relative_to(PACKAGE)),
                                         'sha256': sha(path)}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'physical_bound': len(manifest['cases']),
                      'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
