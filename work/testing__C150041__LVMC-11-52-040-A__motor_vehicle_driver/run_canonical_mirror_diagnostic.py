"""Prove all exact canonical compatibility routes using fake site packets.

This is a software fixture only. It does not publish reviewed sources or
establish original Native motion, pixels, or legal judgment.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from parking_pose import REQUESTS
from rebind_reviewed_execution import rebind
from stage_rebound_delivery import install, stage


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--validator', required=True)
    args = parser.parse_args()
    validator = Path(args.validator).resolve()
    if not validator.is_file():
        raise ValueError('pinned decoder required')
    sys.path.insert(0, str(ROOT / 'tests'))
    from test_bind_reviewed_site import pair
    with TemporaryDirectory(dir=REPO / '.runtime-work') as name:
        scratch = Path(name).resolve()
        packets = pair(scratch)
        rebound = scratch / 'rebound'
        rebind(packets['park'], packets['stand'], rebound)
        staged = scratch / 'staged'
        stage(rebound, staged)
        mirror = scratch / 'mirror'
        (mirror / 'work').mkdir(parents=True)
        target = mirror / 'work' / ROOT.name
        shutil.copytree(ROOT, target, ignore=shutil.ignore_patterns('__pycache__'))
        for name in ('runtime', 'batch.json', 'inputs'):
            (mirror / name).symlink_to(REPO / name,
                                      target_is_directory=name != 'batch.json')
        (mirror / '.runtime-work').mkdir()
        install(staged, packets['park'], packets['stand'], target)
        manifest = target / 'execution-manifest.json'
        env = dict(os.environ,
                   SCENARIO_PIPELINE_OUTPUT_ROOT=str(mirror / '.runtime-work' / 'pipeline'),
                   PYTHONDONTWRITEBYTECODE='1')
        passed = []
        for kind in REQUESTS:
            case = ROOT.name + '__' + kind
            for candidate in ('primary', 'fallback1'):
                output = mirror / '.runtime-work' / kind / candidate
                command = [sys.executable, str(REPO / 'runtime.py'), 'compatibility',
                           '--manifest', str(manifest), '--case', case,
                           '--candidate', candidate, '--output', str(output),
                           '--library', str(REPO / 'runtime/library'),
                           '--validator', str(validator)]
                run = subprocess.run(command, cwd=mirror, env=env,
                                     capture_output=True, text=True, timeout=300)
                if run.returncode:
                    raise ValueError(kind + ' ' + candidate + ' compatibility failed: '
                                     + run.stderr[-1400:])
                receipt = json.loads((output / 'compatibility.json').read_text())
                if (receipt.get('passed') is not True or receipt.get('case_id') != case or
                        receipt.get('candidate_id') != candidate or
                        receipt.get('negative_error_contains') !=
                        'Missing required source: parking-history.jsonl'):
                    raise ValueError('exact compatibility receipt differs: ' + case + ' ' + candidate)
                passed.append({'case_id': case, 'candidate_id': candidate,
                               'construction_sha256': receipt['construction_sha256']})
        print(json.dumps({'format': 'c150041-canonical-mirror-diagnostic-v1',
                          'passed': True, 'cases': len(REQUESTS),
                          'bundles': len(passed), 'receipts': passed,
                          'source_kind': 'synthetic_site_protocol_fixture',
                          'original_review_claimed': False,
                          'delivery_ready_claimed': False}, indent=2))


if __name__ == '__main__':
    main()
