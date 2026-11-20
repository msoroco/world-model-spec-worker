"""Resume the six warning-person fallback chains under the combined manifest."""
import hashlib
import json
import subprocess
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parents[1]
MANIFEST = PACKAGE / 'draft-combined-capture-manifest.json'
PROGRESS = PACKAGE / 'update117-combined-warning-fallback-progress.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    digest = sha(MANIFEST)
    rows = []
    for short in ('reference', 'contrast'):
        for candidate in ('fallback1', 'fallback2', 'fallback3'):
            proof_path = PACKAGE / f'update116-combined-{short}-{candidate}-proof.json'
            if proof_path.exists():
                proof = json.loads(proof_path.read_text())
                if proof.get('manifest_sha256') != digest or proof.get('passed') is not True:
                    raise ValueError('Stale warning fallback proof: ' + str(proof_path))
            else:
                subprocess.run([str(REPO / '.venv-cpu/bin/python'),
                                str(PACKAGE / 'prove_combined_chain.py'),
                                '--case-suffix', short, '--candidate', candidate],
                               cwd=REPO, check=True)
            rows.append({'case_suffix': short, 'candidate_id': candidate,
                         'proof_sha256': sha(proof_path)})
            PROGRESS.write_text(json.dumps({'manifest_sha256': digest,
                                            'passed': len(rows), 'rows': rows},
                                           indent=2, sort_keys=True) + '\n')
            print(short, candidate, 'passed', flush=True)
    print('All six combined warning-person fallbacks passed', flush=True)


if __name__ == '__main__':
    main()
