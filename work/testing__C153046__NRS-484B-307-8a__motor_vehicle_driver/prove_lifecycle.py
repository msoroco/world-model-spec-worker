"""Exercise the pinned Native closure and saved-only ownership gate on fixtures."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, sort_keys=True) + '\n')


def rejects(call, expected: str) -> None:
    try:
        call()
    except (ValueError, FileNotFoundError) as error:
        if expected not in str(error):
            raise AssertionError(f'wrong rejection: {error}') from error
    else:
        raise AssertionError('expected rejection: ' + expected)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--construction', type=Path, required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    args = parser.parse_args()
    if 'SCENARIO_PIPELINE_OUTPUT_ROOT' not in os.environ:
        raise ValueError('export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first')
    if '.runtime-work' not in str(args.scratch.resolve()):
        raise ValueError('fixture scratch must be under .runtime-work')
    from scenario_pipeline.worker_exchange.saved_processing import (
        record_native_exit, acknowledge_owner_release, _closure)

    if args.scratch.exists():
        shutil.rmtree(args.scratch)
    args.scratch.mkdir(parents=True)
    attempt = args.scratch / 'attempt'
    attempt.mkdir()
    shutil.copy2(args.construction, attempt / 'construction.json')
    (attempt / 'runner.py').write_text('pass\n')
    write(attempt / 'original.json', {'case_id': args.case, 'diagnostic_fixture': True})
    revision = {'construction_sha256': sha(attempt / 'construction.json'),
                'runner_sha256': sha(attempt / 'runner.py')}
    seal = {'events': ['capture_finished', 'encoders_closed', 'restoration_verified'],
            'sources': {'original.json': sha(attempt / 'original.json')},
            'native_revision': revision}
    write(attempt / 'capture-seal.json', seal)
    receipt = args.scratch / 'owner-release.json'
    rejects(lambda: acknowledge_owner_release(attempt, receipt, True),
            'Native process has not exited')
    rejects(lambda: _closure(attempt, None, 'native', False),
            'native-exit.json')
    bad = dict(seal, events=['capture_finished', 'restoration_verified', 'encoders_closed'])
    write(attempt / 'capture-seal.json', bad)
    rejects(lambda: record_native_exit(attempt), 'Invalid Native closure ordering')
    write(attempt / 'capture-seal.json', seal)
    exit_record = record_native_exit(attempt)
    if exit_record['event'] != 'native_exit':
        raise AssertionError('native exit not recorded')
    rejects(lambda: _closure(attempt, None, 'native', False),
            'Supply an operator owner-release receipt')
    rejects(lambda: acknowledge_owner_release(attempt, receipt, False),
            'Operator must attest actual owner release')
    owner = acknowledge_owner_release(attempt, receipt, True)
    if owner['event'] != 'owner_released' or owner['no_resource_operation_performed'] is not True:
        raise AssertionError('owner receipt differs')
    _closure(attempt, receipt, 'native', False)
    rejects(lambda: acknowledge_owner_release(attempt, receipt, True),
            'Retain previous owner-release receipt')
    print(json.dumps({'case_id': args.case, 'diagnostic_fixture': True,
                      'events': seal['events'] + ['native_exit', 'owner_released',
                                                 'saved_processing_started'],
                      'saved_only_rejected_before_owner_release': True,
                      'native_exit_rejected_before_encoder_closure': True,
                      'owner_release_rejected_before_native_exit': True,
                      'pinned_closure_accepted_after_release': True}, sort_keys=True))


if __name__ == '__main__':
    main()
