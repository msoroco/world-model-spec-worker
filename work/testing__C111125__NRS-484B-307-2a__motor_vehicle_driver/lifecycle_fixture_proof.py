"""Test ordered Native closure and saved-only handoff on a synthetic receipt."""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path[:0] = [str(REPO / 'runtime'), str(REPO / 'runtime/scenario_pipeline')]
from scenario_pipeline.worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, _closure


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(case, scratch):
    entry = next(x for x in json.loads((ROOT / 'execution-manifest.json').read_text())['cases'] if x['case_id'] == case)
    scratch.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(ROOT / entry['construction'], scratch / 'construction.json')
    shutil.copyfile(ROOT / 'runner.py', scratch / 'runner.py')
    revision = {'construction_sha256': sha(scratch / 'construction.json'), 'runner_sha256': sha(scratch / 'runner.py')}
    seal = {'events': ['capture_finished', 'encoders_closed', 'restoration_verified'],
            'sources': {}, 'native_revision': revision, 'diagnostic_fixture': True}
    (scratch / 'capture-seal.json').write_text(json.dumps(seal) + '\n')
    exit_receipt = record_native_exit(scratch)
    owner_path = scratch / 'owner-release.json'
    try:
        _closure(scratch, None, 'native', False)
    except ValueError as error:
        if 'owner-release' not in str(error):
            raise
    else:
        raise ValueError('saved processing accepted missing owner release')
    owner_receipt = acknowledge_owner_release(scratch, owner_path, True)
    _closure(scratch, owner_path, 'native', False)
    events = seal['events'] + [exit_receipt['event'], owner_receipt['event'], 'saved_processing_started']
    print(json.dumps({'case_id': case, 'events': events, 'native_exit_sha256': sha(scratch / 'native-exit.json'),
                      'owner_release_sha256': sha(owner_path), 'missing_owner_release_rejected': True,
                      'diagnostic_fixture': True}, sort_keys=True))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--case', required=True)
    p.add_argument('--scratch', type=Path, required=True)
    a = p.parse_args()
    run(a.case, a.scratch)
