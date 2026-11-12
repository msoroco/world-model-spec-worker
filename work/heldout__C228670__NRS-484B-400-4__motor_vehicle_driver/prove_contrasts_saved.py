"""Run saved-only processing for all three source-shaped C228670 contrasts."""
from hashlib import sha256
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from worker_exchange.runtime_cli import materialize
from worker_exchange.fixture_recipe import materialize as fixture_materialize
from worker_exchange.saved_processing import copy_sources

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'probe-compatibility-manifest.json'


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', default=str(MANIFEST))
    parser.add_argument('--record-prefix', default='saved')
    args = parser.parse_args()
    manifest = Path(args.manifest).resolve()
    prefix = args.record_prefix
    if prefix not in ('saved', 'delivery-saved'):
        raise ValueError('Unknown saved proof prefix')
    entries = json.loads(manifest.read_text())['cases']
    records = []
    for entry in entries:
      case = entry['case_id']
      slug = case.split('__')[-1]
      for candidate in ['primary'] + [item['id'] for item in entry.get('candidates', [])]:
        revision = 1
        stem = '.runtime-work/c228670-' + prefix + '-' + slug + '-' + candidate
        attempt = REPO / f'{stem}-attempt-v{revision}'
        output = REPO / f'{stem}-v{revision}'
        while attempt.exists() or output.exists():
            revision += 1
            attempt = REPO / f'{stem}-attempt-v{revision}'
            output = REPO / f'{stem}-v{revision}'
        materialize(manifest, case, attempt, candidate)
        with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work', prefix='c228670-source-') as temporary:
            fixture = Path(temporary) / 'source'
            fixture_materialize(REPO, REPO / entry['fixture_recipe'], fixture)
            copy_sources(fixture, attempt)
        before = {path.relative_to(attempt).as_posix(): digest(path)
                  for path in attempt.rglob('*') if path.is_file()}
        command = [sys.executable, str(REPO / 'runtime.py'), 'process-saved',
                   '--manifest', str(manifest), '--case', case,
                   '--attempt', str(attempt), '--output', str(output),
                   '--library', str(REPO / 'runtime/library'),
                   '--validator', str(REPO / '.runtime-work/c125714-validator/.lake/build/bin/adapterCheck')]
        process = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
        log = ROOT / 'cases' / (prefix + '-' + slug + '-' + candidate + '.log')
        log.write_text(process.stdout + process.stderr)
        if process.returncode:
            raise ValueError('C228670 saved processing failed: ' + slug)
        receipt = json.loads(process.stdout)
        if (receipt.get('case_id') != case or not receipt.get('passed')
                or receipt.get('candidate_id') != candidate
                or receipt.get('physical_acceptance_claimed')
                or receipt.get('legal_acceptance_claimed')
                or not receipt.get('originals_preserved')
                or any(digest(attempt / path) != value for path, value in before.items())):
            raise ValueError('C228670 saved receipt/original source differs: ' + slug)
        receipt_path = ROOT / 'cases' / (prefix + '-' + slug + '-' + candidate + '.json')
        receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
        records.append({'case_id': case, 'candidate_id': candidate,
                        'receipt': str(receipt_path.relative_to(ROOT)),
                        'receipt_sha256': digest(receipt_path),
                        'log': str(log.relative_to(ROOT)), 'log_sha256': digest(log)})
        print(slug, candidate, 'passed; originals preserved; no physical or legal acceptance', flush=True)
    (ROOT / (prefix + '-candidate-proofs.json')).write_text(json.dumps(records, indent=2) + '\n')


if __name__ == '__main__':
    main()
