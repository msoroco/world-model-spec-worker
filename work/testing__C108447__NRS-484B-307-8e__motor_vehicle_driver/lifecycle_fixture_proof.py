"""Exercise saved-processing closure ordering on an explicitly synthetic fixture."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from worker_exchange.saved_processing import _closure, record_native_exit


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixture', type=Path, required=True)
    args = parser.parse_args()
    root = args.fixture
    root.mkdir(parents=True, exist_ok=True)
    write(root / 'construction.json', {'case_id': 'synthetic-lifecycle'})
    (root / 'runner.py').write_text('pass\n')
    (root / 'trace.jsonl').write_text('{"frame":1}\n')
    revision = {'construction_sha256': sha(root / 'construction.json'),
                'runner_sha256': sha(root / 'runner.py')}
    seal = {'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'events': ['capture_finished','encoders_closed','restoration_verified'],
            'sources': {'trace.jsonl': sha(root / 'trace.jsonl')}, 'native_revision': revision}
    write(root / 'capture-seal.json', seal)
    try:
        _closure(root, None, 'native', False)
    except FileNotFoundError:
        pass
    else:
        raise ValueError('Missing Native exit was accepted')
    record_native_exit(root)
    try:
        _closure(root, None, 'native', False)
    except ValueError as error:
        if 'owner-release' not in str(error):
            raise
    else:
        raise ValueError('Missing owner receipt was accepted')
    owner = root / 'owner-release.json'
    write(owner, {'event': 'owner_released', 'operator_attested': True,
                  'native_construction_sha256': revision['construction_sha256'],
                  'native_exit_sha256': sha(root / 'native-exit.json'),
                  'synthetic_fixture': True, 'no_resource_operation_performed': True})
    _closure(root, owner, 'synthetic_fixture', True)
    previous = (root / 'native-exit.json').read_text()
    (root / 'native-exit.json').unlink()
    try:
        _closure(root, owner, 'synthetic_fixture', True)
    except FileNotFoundError:
        pass
    else:
        raise ValueError('Missing Native exit was accepted')
    (root / 'native-exit.json').write_text(previous)
    print(json.dumps({'events': seal['events'] + ['native_exit','owner_released','saved_processing_started'],
                      'positive_closure': True, 'missing_exit_rejected': True,
                      'missing_owner_rejected': True, 'diagnostic_fixture': True,
                      'physical_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
