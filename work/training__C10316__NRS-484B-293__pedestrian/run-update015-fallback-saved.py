"""Run current recorded-only saved processing on the remaining exact fallbacks."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE/'draft-execution-manifest.json'
VALIDATOR = ROOT/'.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    outputs = []
    for suffix in ('reference', 'contrast'):
        entry = next(item for item in manifest['cases'] if item['case_id'].endswith('__'+suffix))
        for candidate in ('fallback1', 'fallback2', 'fallback3'):
            if suffix == 'reference' and candidate == 'fallback1':
                continue  # The current proof already exists and is retained.
            attempt = ROOT/'.runtime-work'/f'c10316-v15-{suffix}-compat-{candidate}'
            output = ROOT/'.runtime-work'/f'c10316-v15-{suffix}-{candidate}-saved'
            command = [str(ROOT/'.venv-cpu/bin/python'), str(ROOT/'runtime.py'),
                       'process-saved', '--manifest', str(MANIFEST),
                       '--case', entry['case_id'], '--attempt', str(attempt),
                       '--output', str(output), '--library', str(ROOT/'runtime/pipeline/library'),
                       '--validator', str(VALIDATOR)]
            run = subprocess.run(command, cwd=ROOT, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            log = HERE/f'update015-{suffix}-{candidate}-saved.log'
            log.write_text(run.stdout)
            if run.returncode:
                raise RuntimeError(f'Saved processing failed for {suffix}/{candidate}: {log}')
            receipt = output/'v0001/processing.json'
            data = json.loads(receipt.read_text())
            if (data.get('passed') is not True or data.get('case_id') != entry['case_id'] or
                    data.get('candidate_id') != candidate or
                    data.get('native_revision', {}).get('construction_sha256') !=
                    next(x['construction_sha256'] for x in entry['candidates'] if x['id'] == candidate) or
                    data.get('originals_preserved') is not True or
                    data.get('missing_evidence') is not False):
                raise ValueError('Saved processing receipt incomplete: '+suffix+'/'+candidate)
            outputs.append({'case_id': entry['case_id'], 'candidate_id': candidate,
                            'receipt_sha256': sha(receipt), 'log_sha256': sha(log),
                            'originals_preserved': True, 'missing_evidence': False})
            print(json.dumps({'saved': suffix+'/'+candidate, 'passed': True}), flush=True)
    summary = {'format': 'c10316-update015-remaining-fallback-saved',
               'draft_manifest_sha256': sha(MANIFEST), 'proofs': outputs,
               'scope': 'synthetic recorded-only diagnostics; no Native or legal acceptance'}
    (HERE/'update015-fallback-saved-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps({'passed': True, 'remaining_fallbacks': len(outputs)}))


if __name__ == '__main__':
    main()
