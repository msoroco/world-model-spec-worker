"""Run all exact unselected 1(b) synthetic Core/video compatibility probes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove():
    manifest = json.loads((FOLDER / 'draft-execution-manifest.json').read_text())
    env = dict(os.environ)
    env['LD_LIBRARY_PATH'] = str(ROOT / '.runtime-work/geos-wheel/shapely.libs') + os.pathsep + env.get('LD_LIBRARY_PATH', '')
    results = []
    for entry in manifest['cases']:
        case = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            folder = FOLDER / 'draft-candidates' / case / candidate
            if (case, candidate) == ('reference', 'primary') and (folder / 'full-package-proof.json').is_file():
                proof = json.loads((folder / 'full-package-proof.json').read_text())
                if proof['construction_sha256'] == entry['construction_sha256']:
                    results.append(proof)
                    print(case, candidate, 'previous exact proof retained', flush=True)
                    continue
            command = [str(ROOT / '.venv-cpu/bin/python'), str(FOLDER / 'probe-full-package.py'),
                       '--case', case, '--candidate', candidate]
            run = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
            (folder / 'full-package-command.log').write_text(run.stdout)
            if run.returncode:
                raise ValueError(f'{case}/{candidate}: full package failed: {run.stdout[-1500:]}')
            proof = json.loads((folder / 'full-package-proof.json').read_text())
            results.append(proof)
            print(case, candidate, 'full positive and negative passed', flush=True)
    summary = {'format': 'c405647-1b-exact-full-package-summary-v1',
               'manifest_sha256': sha(FOLDER / 'draft-execution-manifest.json'),
               'results': results, 'original_native_or_delivery_acceptance_claimed': False}
    (FOLDER / 'full-package-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary


if __name__ == '__main__':
    print(json.dumps({'results': len(prove()['results'])}))
