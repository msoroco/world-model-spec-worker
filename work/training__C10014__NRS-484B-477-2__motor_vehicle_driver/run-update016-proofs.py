"""Reprove all eight rebuilt C10014 bundles with current pinned CPU runtime."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE/'draft-execution-manifest.json'
VALIDATOR = ROOT/'.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'
PYTHON = ROOT/'.venv-cpu/bin/python'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, log):
    completed = subprocess.run(command, cwd=ROOT, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               timeout=300)
    log.write_text(completed.stdout)
    if completed.returncode:
        raise RuntimeError(f'{log}: exit {completed.returncode}: {completed.stdout[-1000:]}')
    return ' '.join(map(str, command))


def main():
    manifest = json.loads(MANIFEST.read_text())
    if not VALIDATOR.is_file():
        raise FileNotFoundError(VALIDATOR)
    results = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            selected = entry if candidate == 'primary' else next(
                item for item in entry['candidates'] if item['id'] == candidate)
            attempt = ROOT/'.runtime-work'/f'c10014-update016-{suffix}-{candidate}-compat'
            saved = ROOT/'.runtime-work'/f'c10014-update016-{suffix}-{candidate}-saved'
            if attempt.exists() or saved.exists():
                raise FileExistsError(f'Retain prior attempt; update version: {attempt}')
            common = ['--manifest', str(MANIFEST), '--case', entry['case_id'],
                      '--library', str(ROOT/'runtime/pipeline/library'),
                      '--validator', str(VALIDATOR)]
            compatibility_log = HERE/f'update016-{suffix}-{candidate}-compat.log'
            compatibility_command = run([str(PYTHON), str(ROOT/'runtime.py'),
                'compatibility', *common, '--candidate', candidate,
                '--output', str(attempt)], compatibility_log)
            receipt = json.loads((attempt/'compatibility.json').read_text())
            if (receipt.get('passed') is not True or
                    receipt.get('construction_sha256') != selected['construction_sha256'] or
                    receipt.get('case_id') != entry['case_id'] or
                    receipt.get('candidate_id') != candidate or
                    receipt.get('negative_removed') != 'native_samples.jsonl'):
                raise ValueError('Compatibility identity or negative proof incomplete')
            saved_log = HERE/f'update016-{suffix}-{candidate}-saved.log'
            saved_command = run([str(PYTHON), str(ROOT/'runtime.py'),
                'process-saved', *common, '--attempt', str(attempt),
                '--output', str(saved)], saved_log)
            processing = json.loads((saved/'v0001/processing.json').read_text())
            if (processing.get('passed') is not True or
                    processing.get('native_revision', {}).get('construction_sha256') != selected['construction_sha256'] or
                    processing.get('case_id') != entry['case_id'] or
                    processing.get('candidate_id') != candidate or
                    processing.get('recorded_only') is not True or
                    processing.get('originals_preserved') is not True or
                    processing.get('missing_evidence') is not False):
                raise ValueError('Saved processing source or identity incomplete')
            results.append({'case_id': entry['case_id'], 'candidate_id': candidate,
                'construction_sha256': selected['construction_sha256'],
                'compatibility_command': compatibility_command,
                'saved_command': saved_command,
                'compatibility_sha256': sha(attempt/'compatibility.json'),
                'saved_processing_sha256': sha(saved/'v0001/processing.json'),
                'compatibility_log_sha256': sha(compatibility_log),
                'saved_log_sha256': sha(saved_log)})
            print(json.dumps({'case': suffix, 'candidate': candidate,
                              'compatibility': True, 'saved': True}), flush=True)
    report = {'format': 'c10014-update016-current-cpu-proofs',
              'draft_manifest_sha256': sha(MANIFEST), 'proofs': results,
              'scope': 'unselected synthetic diagnostics; no Native or legal acceptance'}
    (HERE/'update016-proof-summary.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'passed': True, 'attempts': len(results)}))


if __name__ == '__main__':
    main()
