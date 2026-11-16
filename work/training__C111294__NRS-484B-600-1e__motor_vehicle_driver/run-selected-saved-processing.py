"""Run recorded-only CPU processing for exact selected speed candidates."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / 'runtime/pipeline/scenario_pipeline'),
                str(ROOT / 'runtime/pipeline/python'), str(ROOT / 'runtime/pipeline')]
from worker_exchange.fixture_recipe import materialize as make_fixture
from worker_exchange.runtime_cli import materialize as make_package
from worker_exchange.saved_processing import copy_sources


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(tag, source_tag=None, only_case=None, only_candidate=None):
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    bound_sha = sha(manifest_path)
    validator = ROOT / '.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'
    if not validator.is_file():
        raise ValueError('Pinned validator missing')
    rows = []
    matrix_path = HERE / f'{tag}-selected-process-saved-matrix.json'
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(HERE.name + '__')
        if only_case and suffix != only_case:
            continue
        for candidate in ('primary', *(item['id'] for item in entry['candidates'])):
            if only_candidate and candidate != only_candidate:
                continue
            base = ROOT / '.runtime-work' / f'c111294-{tag}-selected' / suffix / candidate
            fixture, attempt, output = (base / name for name in
                                        ('source-fixture', 'selected-attempt', 'processed'))
            if any(path.exists() for path in (fixture, attempt, output)):
                raise ValueError('Retain prior selected attempt; choose a fresh tag')
            fixture.parent.mkdir(parents=True, exist_ok=True)
            if source_tag is None:
                make_fixture(ROOT, ROOT / entry['fixture_recipe'], fixture)
                source_fixture = fixture
            else:
                source_fixture = (ROOT / '.runtime-work' /
                                  f'c111294-{source_tag}-selected' / suffix /
                                  candidate / 'source-fixture')
                if not source_fixture.is_dir():
                    raise ValueError('Reusable source fixture absent: ' + str(source_fixture))
            make_package(manifest_path, entry['case_id'], attempt, candidate)
            copy_sources(source_fixture, attempt)
            selection = json.loads((attempt / 'candidate-selection.json').read_text())
            if selection['manifest_sha256'] != bound_sha or selection['candidate_id'] != candidate:
                raise ValueError('Attempt does not bind current selected manifest')
            command = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
                       'process-saved', '--manifest', str(manifest_path),
                       '--case', entry['case_id'], '--attempt', str(attempt),
                       '--output', str(output), '--library', str(ROOT / 'runtime/pipeline/library'),
                       '--validator', str(validator)]
            run = subprocess.run(command, cwd=ROOT, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
            log = HERE / f'{tag}-selected-{suffix}-{candidate}-process-saved.log'
            log.write_text(run.stdout)
            print(suffix, candidate, run.returncode, flush=True)
            if run.returncode:
                raise ValueError('Selected saved processing failed: ' + run.stdout[-2000:])
            receipt = output / 'v0001/processing.json'
            if not receipt.is_file():
                raise ValueError('Selected processing receipt missing')
            rows.append({'case_id': entry['case_id'], 'candidate_id': candidate,
                         'command': ' '.join(command), 'log': log.name,
                         'log_sha256': sha(log),
                         'processing_receipt_sha256': sha(receipt),
                         'diagnostic_only': True})
            matrix_path.write_text(json.dumps({
                'format': 'c111294-selected-process-saved-matrix-v1',
                'status': 'complete_diagnostic' if len(rows) == 16 else 'partial',
                'manifest_sha256': bound_sha, 'rows': rows,
                'source_fixture_reused_from_tag': source_tag,
                'original_physical_acceptance_claimed': False}, indent=2) + '\n')
    print(json.dumps({'selected_saved_processing_passed': len(rows),
                      'matrix_sha256': sha(matrix_path),
                      'original_physical_acceptance_claimed': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', required=True)
    parser.add_argument('--source-tag')
    parser.add_argument('--only-case')
    parser.add_argument('--only-candidate')
    args = parser.parse_args()
    main(args.tag, args.source_tag, args.only_case, args.only_candidate)
