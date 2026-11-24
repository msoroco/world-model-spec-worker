"""Rehearse saved-only CPU processing for the installed diagnostic manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from parking_pose import REQUESTS


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command):
    result = subprocess.run(command, cwd=REPO, env=os.environ,
                            capture_output=True, text=True, timeout=300)
    if result.returncode:
        raise ValueError('pinned saved rehearsal failed: ' + ' '.join(command)
                         + ' ' + result.stdout[-1200:] + result.stderr[-1200:])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-root', required=True, type=Path)
    parser.add_argument('--validator', required=True, type=Path)
    args = parser.parse_args()
    scratch = (REPO / '.runtime-work').resolve()
    output = args.output_root.resolve()
    runtime_output = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '/')).resolve()
    if (not output.is_relative_to(scratch) or output.exists() or
            not runtime_output.is_relative_to(scratch) or
            not args.validator.is_file()):
        raise ValueError('fresh scratch outputs and pinned validator required')
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if manifest['preparation_status'] != 'partial_reviewed_site_and_delivery_pending':
        raise ValueError('diagnostic only: manifest status differs')
    if manifest['runtime_manifest_sha256'] != sha(REPO / 'runtime/SOURCE-MANIFEST.json'):
        raise ValueError('installed runtime source hash differs')
    output.mkdir(parents=True)
    results = []
    for kind in REQUESTS:
        case = ROOT.name + '__' + kind
        entry = next(e for e in manifest['cases'] if e['case_id'] == case)
        source = output / kind / 'compatibility'
        saved = output / kind / 'saved'
        compat_command = [sys.executable, str(REPO / 'runtime.py'), 'compatibility',
                          '--manifest', str(manifest_path), '--case', case,
                          '--candidate', 'primary', '--output', str(source),
                          '--library', str(REPO / 'runtime/library'),
                          '--validator', str(args.validator.resolve())]
        run(compat_command)
        selection = json.loads((source / 'candidate-selection.json').read_text())
        if (selection['manifest_sha256'] != sha(manifest_path) or
                selection['construction_sha256'] != entry['construction_sha256']):
            raise ValueError('saved source does not select current manifest')
        source_before = sha(source / 'parking-history.jsonl')
        saved_command = [sys.executable, str(REPO / 'runtime.py'), 'process-saved',
                         '--manifest', str(manifest_path), '--case', case,
                         '--attempt', str(source), '--output', str(saved),
                         '--library', str(REPO / 'runtime/library'),
                         '--validator', str(args.validator.resolve())]
        run(saved_command)
        receipt = json.loads((saved / 'v0001/processing.json').read_text())
        if (receipt.get('passed') is not True or
                receipt.get('recorded_only') is not True or
                receipt.get('missing_evidence') is not False or
                sha(source / 'parking-history.jsonl') != source_before):
            raise ValueError('saved-only diagnostic proof differs')
        results.append({'case_id': case, 'passed': True,
                        'manifest_sha256': selection['manifest_sha256'],
                        'construction_sha256': selection['construction_sha256'],
                        'saved_receipt_sha256': sha(saved / 'v0001/processing.json'),
                        'original_capture_reviewed': False})
    print(json.dumps({'format': 'c150041-installed-saved-diagnostic-v1',
                      'source_kind': 'synthetic_fixture', 'passed': True,
                      'cases': results, 'original_capture_reviewed': False,
                      'delivery_ready_claimed': False}, indent=2))


if __name__ == '__main__':
    main()
