"""Finish the exact candidate matrix after the repaired first primary passed."""
import concurrent.futures
import hashlib
import json
import runpy
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODULE = runpy.run_path(str(HERE / 'run-selected-candidate-update804.py'))
MANIFEST = HERE / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    entries = json.loads(MANIFEST.read_text())['cases']
    primary = entries[0]
    proof = HERE / 'update804-selected-proofs/reference/primary/proof.json'
    data = json.loads(proof.read_text())
    if data['manifest_sha256'] != sha(MANIFEST) or data['case_id'] != primary['case_id']:
        raise ValueError('First primary proof differs')
    first = {'case_id': primary['case_id'], 'candidate_id': 'primary',
             'proof': proof.relative_to(HERE).as_posix(), 'sha256': sha(proof)}
    tasks = [(entries[1], 'primary', entries[1])]
    tasks.extend((entry, candidate['id'], candidate)
                 for entry in entries for candidate in entry['candidates'])
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(MODULE['task'], *args) for args in tasks]
        results = [first, *(future.result() for future in futures)]
    if len(results) != 8 or len({(r['case_id'], r['candidate_id']) for r in results}) != 8:
        raise ValueError('Candidate matrix incomplete')
    index = {'format': 'c146314-two-case-cpu-probe-matrix-v1',
             'manifest_sha256': sha(MANIFEST), 'cases': 2, 'candidates': 8,
             'results': results, 'canonical_selected': False,
             'original_native_accepted': False}
    path = HERE / 'update804-two-case-matrix-index.json'
    path.write_text(json.dumps(index, indent=2) + '\n')
    print(json.dumps({'cases': 2, 'candidates': 8, 'index_sha256': sha(path)}))


if __name__ == '__main__':
    main()
