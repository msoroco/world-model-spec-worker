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
        for name in ('runtime', 'runtime.py', 'batch.json', 'inputs'):
            (mirror / name).symlink_to(REPO / name,
                                      target_is_directory=name in ('runtime', 'inputs'))
        (mirror / '.runtime-work').mkdir()
        install(staged, packets['park'], packets['stand'], target)
        manifest = target / 'execution-manifest.json'
        env = dict(os.environ,
                   SCENARIO_PIPELINE_OUTPUT_ROOT=str(mirror / '.runtime-work' / 'pipeline'),
                   TMPDIR=str(mirror / '.runtime-work'),
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
        proof_command = [sys.executable, str(target / 'prove_execution_manifest.py'),
                         '--output-root', str(mirror / '.runtime-work' / 'exact-proofs'),
                         '--validator', str(validator)]
        proof = subprocess.run(proof_command, cwd=mirror, env=env,
                               capture_output=True, text=True, timeout=1800)
        if proof.returncode:
            first_log = target / 'diagnostic/park_parallel_lawful/cpu-delivery-primary-offline.log'
            runner_log = (mirror / '.runtime-work/exact-proofs/park_parallel_lawful/'
                          'primary/offline/offline.log')
            raise ValueError('installed exact offline/compatibility proof failed: '
                             + proof.stdout[-1400:] + proof.stderr[-1400:]
                             + (first_log.read_text()[-2200:] if first_log.exists() else '')
                             + (runner_log.read_text()[-2200:] if runner_log.exists() else ''))
        os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'] = env['SCENARIO_PIPELINE_OUTPUT_ROOT']
        os.environ['TMPDIR'] = env['TMPDIR']
        sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
        from worker_exchange.package_compatibility import check_receipts
        check_receipts(mirror, target, json.loads(manifest.read_text()))
        saved = []
        for kind in REQUESTS:
            case = ROOT.name + '__' + kind
            source = mirror / '.runtime-work/saved-source' / kind
            compat_command = [sys.executable, str(mirror / 'runtime.py'), 'compatibility',
                              '--manifest', str(manifest), '--case', case,
                              '--candidate', 'primary', '--output', str(source),
                              '--library', str(REPO / 'runtime/library'),
                              '--validator', str(validator)]
            compat = subprocess.run(compat_command, cwd=mirror, env=env,
                                    capture_output=True, text=True, timeout=300)
            if compat.returncode:
                raise ValueError('current-manifest saved source failed: ' + kind + ' '
                                 + compat.stdout[-1200:] + compat.stderr[-1200:])
            saved_output = mirror / '.runtime-work/saved' / kind
            command = [sys.executable, str(mirror / 'runtime.py'), 'process-saved',
                       '--manifest', str(manifest), '--case', case,
                       '--attempt', str(source), '--output', str(saved_output),
                       '--library', str(REPO / 'runtime/library'),
                       '--validator', str(validator)]
            run = subprocess.run(command, cwd=mirror, env=env,
                                 capture_output=True, text=True, timeout=300)
            if run.returncode:
                raise ValueError('installed saved-only proof failed: ' + kind + ' '
                                 + run.stdout[-1200:] + run.stderr[-1200:])
            receipt = json.loads((saved_output / 'v0001/processing.json').read_text())
            if receipt.get('passed') is not True or receipt.get('missing_evidence') is not False:
                raise ValueError('installed saved-only receipt incomplete: ' + kind)
            (mirror / '.runtime-work' / ('c150041-saved-fixture-v8-' + kind)).symlink_to(source)
            saved.append(case)
        audits = []
        for kind in REQUESTS:
            case = ROOT.name + '__' + kind
            command = [sys.executable, str(target / 'independent/prove_delivery_audit.py'), case]
            run = subprocess.run(command, cwd=mirror, env=env,
                                 capture_output=True, text=True, timeout=120)
            if run.returncode or 'positive and three negatives passed' not in run.stdout:
                raise ValueError('independent delivery protocol failed: ' + case + ' '
                                 + run.stdout[-800:] + run.stderr[-800:])
            audits.append(case)
        comparisons = []
        for pair in ('park_parallelism', 'park_heading',
                     'stand_parallelism', 'stand_heading'):
            command = [sys.executable, str(target / 'independent/prove_comparison_audit.py'), pair]
            run = subprocess.run(command, cwd=mirror, env=env,
                                 capture_output=True, text=True, timeout=120)
            if run.returncode or 'missing-pixel/source negatives passed' not in run.stdout:
                raise ValueError('independent comparison protocol failed: ' + pair + ' '
                                 + run.stdout[-800:] + run.stderr[-800:])
            comparisons.append(pair)
        print(json.dumps({'format': 'c150041-canonical-mirror-diagnostic-v1',
                          'passed': True, 'cases': len(REQUESTS),
                          'bundles': len(passed), 'receipts': passed,
                          'installed_exact_proofs_passed': True,
                          'receipt_validation_passed': True,
                          'installed_saved_only_passed': saved,
                          'independent_delivery_protocols_passed': audits,
                          'independent_comparison_protocols_passed': comparisons,
                          'source_kind': 'synthetic_site_protocol_fixture',
                          'original_review_claimed': False,
                          'delivery_ready_claimed': False}, indent=2))


if __name__ == '__main__':
    main()
