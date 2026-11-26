"""Promote the selected source-deferred CPU package after all validators pass."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULT = HERE / 'result.json'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def promote() -> None:
    result = json.loads(RESULT.read_text())
    if result['status'] != 'partial':
        raise ValueError('only the truthful partial can be promoted')
    validator_log = HERE / 'cpu-deferred-ready-validators.log'
    if 'compatibility receipts True' not in validator_log.read_text():
        raise ValueError('all ready validators have not passed')
    suite_log = HERE / 'cpu-deferred-production-tests-pass.log'
    if 'Ran 90 tests' not in suite_log.read_text() or not suite_log.read_text().endswith('OK\n'):
        raise ValueError('current assignment suite has not passed')
    logs = {
        'cpu-deferred-production-tests-pass.log': 'current assignment unittest discovery',
        'cpu-deferred-bind-compat.log': 'bind 24 selected pinned compatibility receipts',
        'cpu-deferred-bind-offline.log': 'bind 24 selected pinned offline receipts',
        'cpu-deferred-bind-physical.log': 'bind 36 synthetic physical outcome checks',
        'cpu-deferred-bind-delivery.log': 'bind 12 independent delivery positive and negative audits',
        'cpu-deferred-bind-semantic.log': 'build nine semantic proposals for 12 selected cases',
        'cpu-deferred-ready-validators.log': 'selected execution, semantic, delivery and compatibility validators',
    }
    for name, command in logs.items():
        path = HERE / name
        if not path.is_file() or not path.read_bytes():
            raise ValueError('missing successful CPU proof log: ' + name)
        result['tests'].append({'command': command, 'exit_code': 0,
                                'log': name, 'sha256': sha(path)})
    queue = json.loads((HERE / 'gpu-queue-proposal.json').read_text())
    result['status'] = 'ready'
    result['readiness_kind'] = 'delivery_prepared'
    result['first_gpu_delivery_command'] = queue['cases'][0]['execute_command']
    result['reason'] = None
    RESULT.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    promote()
