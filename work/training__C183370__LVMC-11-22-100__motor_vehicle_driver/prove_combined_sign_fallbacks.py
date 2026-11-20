"""Resume the six warning-sign fallback chains under the combined manifest."""
import hashlib
import json
import subprocess
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parents[1]
MANIFEST = PACKAGE / 'draft-combined-capture-manifest.json'
PROGRESS = PACKAGE / 'update118-combined-warning-sign-fallback-progress.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_sha = sha(MANIFEST)
    rows = []
    for suffix in ('warning_sign_crossing', 'warning_sign_avoidance'):
        for candidate in ('fallback1', 'fallback2', 'fallback3'):
            proof_path = PACKAGE / f'update116-combined-{suffix}-{candidate}-proof.json'
            if proof_path.exists():
                proof = json.loads(proof_path.read_text())
                if proof.get('manifest_sha256') != manifest_sha or proof.get('passed') is not True:
                    raise ValueError('Stale fallback proof: ' + str(proof_path))
            else:
                command = [str(REPO / '.venv-cpu/bin/python'),
                           str(PACKAGE / 'prove_combined_chain.py'),
                           '--case-suffix', suffix, '--candidate', candidate]
                subprocess.run(command, cwd=REPO, check=True)
            rows.append({'case_suffix': suffix, 'candidate_id': candidate,
                         'proof_sha256': sha(proof_path)})
            PROGRESS.write_text(json.dumps({'manifest_sha256': manifest_sha,
                                            'passed': len(rows), 'rows': rows},
                                           indent=2, sort_keys=True) + '\n')
            print(suffix, candidate, 'passed', flush=True)
    print('All six combined warning-sign fallbacks passed', flush=True)


if __name__ == '__main__':
    main()
