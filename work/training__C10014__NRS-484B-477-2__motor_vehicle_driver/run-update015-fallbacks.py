"""Run current exact fallback compatibility and recorded-only saved processing."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE/'draft-execution-manifest.json'
VALIDATOR = ROOT/'.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, log):
    completed = subprocess.run(command, cwd=ROOT, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               timeout=300)
    log.write_text(completed.stdout)
    if completed.returncode:
        raise RuntimeError(f'Current CPU proof failed: {log}')


def main():
    manifest = json.loads(MANIFEST.read_text())
    results = []
    for suffix in ('reference', 'contrast'):
        entry = next(case for case in manifest['cases']
                     if case['case_id'].endswith('__'+suffix))
        for candidate in ('fallback1', 'fallback2', 'fallback3'):
            selected = next(item for item in entry['candidates']
                            if item['id'] == candidate)
            attempt = ROOT/'.runtime-work'/f'c10014-update015-{suffix}-{candidate}-compat'
            saved = ROOT/'.runtime-work'/f'c10014-update015-{suffix}-{candidate}-saved'
            common = ['--manifest', str(MANIFEST), '--case', entry['case_id'],
                      '--library', str(ROOT/'runtime/pipeline/library'),
                      '--validator', str(VALIDATOR)]
            command = [str(ROOT/'.venv-cpu/bin/python'), str(ROOT/'runtime.py'),
                       'compatibility', *common, '--candidate', candidate,
                       '--output', str(attempt)]
            positive_log = HERE/f'update015-{suffix}-{candidate}-compat.log'
            run(command, positive_log)
            receipt = json.loads((attempt/'compatibility.json').read_text())
            if (receipt.get('passed') is not True or receipt.get('case_id') != entry['case_id'] or
                    receipt.get('candidate_id') != candidate or
                    receipt.get('construction_sha256') != selected['construction_sha256'] or
                    receipt.get('negative_removed') != 'native_samples.jsonl'):
                raise ValueError(f'Incomplete compatibility proof: {suffix}/{candidate}')
            command = [str(ROOT/'.venv-cpu/bin/python'), str(ROOT/'runtime.py'),
                       'process-saved', *common, '--attempt', str(attempt),
                       '--output', str(saved)]
            saved_log = HERE/f'update015-{suffix}-{candidate}-saved.log'
            run(command, saved_log)
            processing = json.loads((saved/'v0001/processing.json').read_text())
            if (processing.get('passed') is not True or
                    processing.get('candidate_id') != candidate or
                    processing.get('case_id') != entry['case_id'] or
                    processing.get('originals_preserved') is not True or
                    processing.get('missing_evidence') is not False):
                raise ValueError(f'Incomplete saved processing proof: {suffix}/{candidate}')
            results.append({'case_id': entry['case_id'], 'candidate_id': candidate,
                            'construction_sha256': selected['construction_sha256'],
                            'compatibility_sha256': sha(attempt/'compatibility.json'),
                            'saved_processing_sha256': sha(saved/'v0001/processing.json'),
                            'compatibility_log_sha256': sha(positive_log),
                            'saved_log_sha256': sha(saved_log)})
            print(json.dumps({'case': suffix, 'candidate': candidate,
                              'compatibility': True, 'saved': True}), flush=True)
    summary = {'format': 'c10014-update015-current-fallback-proofs',
               'draft_manifest_sha256': sha(MANIFEST), 'proofs': results,
               'scope': 'unselected synthetic diagnostics; no Native or legal acceptance'}
    (HERE/'update015-fallback-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps({'passed': True, 'fallbacks': len(results)}))


if __name__ == '__main__':
    main()
