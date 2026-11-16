"""Run exact CPU diagnostics for unselected release-grid constructions."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
STAGE = REPO / '.runtime-work/c109749-hazard-release-stage-v2'
MANIFEST = STAGE / 'work' / ROOT.name / 'hazard-release-draft-manifest.json'
PYTHON = REPO / '.venv-cpu/bin/python'
VALIDATOR = REPO / '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, log):
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('w') as stream:
        subprocess.run([str(arg) for arg in args], cwd=REPO, stdout=stream,
                       stderr=subprocess.STDOUT, check=True)


def prove():
    index = json.loads((ROOT / 'hazard-release-draft-index.json').read_text())
    output = []
    for case in index['cases']:
        case_id = case['case_id']
        suffix = case_id.split('__')[-1]
        for variant in case['variants']:
            label = variant['id']
            candidate = [] if label == 'primary' else ['--candidate', label]
            stem = suffix + '-' + label
            proof = ROOT / 'cases' / suffix / 'draft-proofs' / label
            run([PYTHON, REPO / 'runtime.py', 'offline', '--manifest', MANIFEST,
                 '--case', case_id, '--output', STAGE / '.runtime-work' / (stem + '-offline')]
                + candidate, proof / 'offline.log')
            compat = STAGE / '.runtime-work' / (stem + '-compat')
            run([PYTHON, REPO / 'runtime.py', 'compatibility', '--manifest', MANIFEST,
                 '--case', case_id, '--output', compat, '--library', REPO / 'runtime/library',
                 '--validator', VALIDATOR] + candidate, proof / 'compatibility.log')
            saved = STAGE / '.runtime-work' / (stem + '-saved')
            run([PYTHON, REPO / 'runtime.py', 'process-saved', '--manifest', MANIFEST,
                 '--case', case_id, '--attempt', compat, '--output', saved,
                 '--library', REPO / 'runtime/library', '--validator', VALIDATOR],
                proof / 'saved.log')
            for source, name in ((compat / 'compatibility.json', 'compatibility.json'),
                                 (compat / 'negative-analysis.log', 'negative-analysis.log'),
                                 (saved / 'v0001/processing.json', 'processing.json')):
                shutil.copy2(source, proof / name)
            output.append({'case_id': case_id, 'candidate': label,
                           'construction_sha256': variant['construction_sha256'],
                           'offline_log_sha256': sha(proof / 'offline.log'),
                           'compatibility_receipt_sha256': sha(proof / 'compatibility.json'),
                           'negative_log_sha256': sha(proof / 'negative-analysis.log'),
                           'saved_receipt_sha256': sha(proof / 'processing.json'),
                           'saved_log_sha256': sha(proof / 'saved.log'),
                           'scope': 'isolated synthetic software diagnostic; unselected'})
    path = ROOT / 'hazard-release-draft-proof-index.json'
    path.write_text(json.dumps({'format': 'worker-hazard-release-draft-proofs',
                                'cases': output}, indent=2) + '\n')
    return len(output)


if __name__ == '__main__':
    print(prove())
