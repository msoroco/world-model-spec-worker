"""Run current-runtime exact selected CPU chains for C110741 staging."""
import concurrent.futures
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PYTHON = ROOT / '.venv-cpu/bin/python'
RUNTIME = ROOT / 'runtime.py'
MANIFEST = HERE / 'current-cutover-staging.json'
LIBRARY = ROOT / 'runtime/pipeline/library'
VALIDATOR = ROOT / '.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'
RUN = ROOT / '.runtime-work/c110741-cutover'
PROOF = HERE / 'current-cutover-proof'
CASES = ('condition_a', 'condition_b')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args, log):
    result = subprocess.run([str(PYTHON), str(RUNTIME), *map(str, args)],
                            cwd=ROOT, capture_output=True, text=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise ValueError(f'CPU chain failed ({result.returncode}): {log}: '
                         + (result.stderr or result.stdout)[-900:])


def prove(case, candidate):
    manifest = json.loads(MANIFEST.read_text())
    entry = next(row for row in manifest['cases'] if row['case_id'].endswith('__' + case))
    case_id = entry['case_id']
    output = RUN / case / candidate
    proof = PROOF / case / candidate
    proof.mkdir(parents=True, exist_ok=True)
    common = ['--manifest', MANIFEST, '--case', case_id, '--candidate', candidate]
    command(['offline', *common, '--output', output / 'offline', '--python', PYTHON],
            proof / 'offline.log')
    command(['compatibility', *common, '--output', output / 'compatibility',
             '--library', LIBRARY, '--validator', VALIDATOR], proof / 'compatibility.log')
    compatibility = json.loads((output / 'compatibility/compatibility.json').read_text())
    selected = entry if candidate == 'primary' else next(
        row for row in entry['candidates'] if row['id'] == candidate)
    if not (compatibility['passed'] is True and compatibility['case_id'] == case_id
            and compatibility['candidate_id'] == candidate
            and compatibility['construction_sha256'] == selected['construction_sha256']
            and compatibility['negative_removed'] == 'native_samples.jsonl'):
        raise ValueError('Selected compatibility binding failed: ' + case + '/' + candidate)
    command(['process-saved', '--manifest', MANIFEST, '--case', case_id,
             '--attempt', output / 'compatibility', '--output', output / 'saved',
             '--library', LIBRARY, '--validator', VALIDATOR], proof / 'saved.log')
    saved = json.loads((output / 'saved/v0001/processing.json').read_text())
    if not (saved['passed'] is True and saved['recorded_only'] is True
            and saved['originals_preserved'] is True
            and saved['physical_acceptance_claimed'] is False
            and saved['legal_acceptance_claimed'] is False):
        raise ValueError('Selected saved processing failed: ' + case + '/' + candidate)
    for name, source in (
            ('compatibility.json', output / 'compatibility/compatibility.json'),
            ('analysis.log', output / 'compatibility/compatibility-analysis.log'),
            ('negative-analysis.log', output / 'compatibility/negative-analysis.log'),
            ('saved-receipt.json', output / 'saved/v0001/processing.json')):
        target = proof / name
        target.write_bytes(source.read_bytes())
        if target.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Oversized returned proof: ' + str(target))
    receipt = {'case_id': case_id, 'candidate_id': candidate,
               'construction_sha256': selected['construction_sha256'],
               'runtime_manifest_sha256': manifest['runtime_manifest_sha256'],
               'staged_manifest_sha256': sha(MANIFEST),
               'offline_log_sha256': sha(proof / 'offline.log'),
               'compatibility_receipt_sha256': sha(proof / 'compatibility.json'),
               'saved_receipt_sha256': sha(proof / 'saved-receipt.json'),
               'passed': True, 'synthetic_cpu_only': True}
    (proof / 'proof.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    return case + '/' + candidate


def main():
    tasks = [(case, candidate) for case in CASES for candidate in CANDIDATES
             if not (case == 'condition_a' and candidate == 'primary')]
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(prove, *task) for task in tasks]
        for future in concurrent.futures.as_completed(futures):
            name = future.result()
            results.append(name)
            print(json.dumps({'passed': name, 'count': len(results)}), flush=True)
    index = {'format': 'c110741-current-cutover-seven-cpu-chains-v1',
             'staged_manifest_sha256': sha(MANIFEST), 'passed': sorted(results),
             'original_native_observed': False}
    (PROOF / 'index.json').write_text(json.dumps(index, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'passed': len(results), 'index_sha256': sha(PROOF / 'index.json')}))


if __name__ == '__main__':
    main()
