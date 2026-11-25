"""Bind exact diagnostic physical outcomes and Native closure logs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.removeprefix(HERE.name + '__')
        if suffix == case:
            raise ValueError('foreign exact case')
        fixtures = []
        for kind, status in (('complete_motion', 'met'),
                             ('incomplete_motion', 'not_met'),
                             ('missing_evidence', 'unverified')):
            result = HERE / ('physical-' + suffix + '-' + kind + '.json')
            log = HERE / ('cpu-physical-' + suffix + '-' + kind + '.log')
            measured = json.loads(result.read_text())
            if (measured['diagnostic_fixture'] is not True or
                    measured['physical_checks']['maneuver']['status'] != status):
                raise ValueError('diagnostic fixture outcome differs: ' + case)
            fixtures.append({
                'kind': kind,
                'command': '.venv-cpu/bin/python work/' + HERE.name +
                           '/prove_physical.py --case ' + case + ' --kind ' + kind +
                           ' --scratch .runtime-work/c111304-physical --result work/' +
                           HERE.name + '/' + result.name,
                'exit_code': 0, 'log': log.name, 'log_sha256': sha(log),
                'result': result.name, 'result_sha256': sha(result),
            })
        life_log = HERE / ('cpu-lifecycle-' + suffix + '.log')
        life = json.loads(life_log.read_text())
        if life['case_id'] != case or life['diagnostic_fixture'] is not True:
            raise ValueError('lifecycle fixture differs: ' + case)
        receipt = {
            'format': 'worker-physical-preparation-proof', 'case_id': case,
            'construction_sha256': sha(HERE / entry['construction']),
            'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
            'fixtures': fixtures,
            'lifecycle': {
                'command': '.venv-cpu/bin/python work/' + HERE.name +
                           '/prove_lifecycle.py --case ' + case +
                           ' --scratch .runtime-work/c111304-physical',
                'events': life['events'], 'exit_code': 0,
                'log': life_log.name, 'log_sha256': sha(life_log),
            },
        }
        (HERE / ('physical-preparation-' + suffix + '.json')).write_text(
            json.dumps(receipt, indent=2) + '\n')
    print('bound', len(manifest['cases']), 'exact diagnostic physical and lifecycle receipts')


if __name__ == '__main__':
    main()
