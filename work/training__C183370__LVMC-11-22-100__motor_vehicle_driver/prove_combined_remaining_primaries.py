"""Resume full CPU chains for the five unproved combined-manifest primaries."""
import hashlib
import json
import subprocess
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parents[1]
MANIFEST = PACKAGE / 'draft-combined-capture-manifest.json'
PROGRESS = PACKAGE / 'update117-combined-primary-progress.json'
CASES = ('warning_sign_avoidance', 'highway_closed_sign_crossing',
         'highway_closed_sign_avoidance',
         'employee_exception_employee_crossing',
         'employee_exception_nonemployee_crossing')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    digest = sha(MANIFEST)
    rows = []
    for short in CASES:
        proof_path = PACKAGE / f'update116-combined-{short}-primary-proof.json'
        if proof_path.exists():
            proof = json.loads(proof_path.read_text())
            if proof.get('manifest_sha256') != digest or proof.get('passed') is not True:
                raise ValueError('Stale combined primary proof: ' + str(proof_path))
        else:
            subprocess.run([str(REPO / '.venv-cpu/bin/python'),
                            str(PACKAGE / 'prove_combined_chain.py'),
                            '--case-suffix', short, '--candidate', 'primary'],
                           cwd=REPO, check=True)
        rows.append({'case_suffix': short, 'proof_sha256': sha(proof_path)})
        PROGRESS.write_text(json.dumps({'manifest_sha256': digest,
                                        'passed': len(rows), 'rows': rows},
                                       indent=2, sort_keys=True) + '\n')
        print(short, 'passed', flush=True)
    print('All five remaining combined primaries passed', flush=True)


if __name__ == '__main__':
    main()
