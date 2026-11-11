"""Bind exact both-hands fallback offline and compatibility proofs."""
from hashlib import sha256
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
FOLDER = ROOT / 'cases/both_hands_no_signal'
manifest_path = ROOT / 'both-hands-manifest.json'
manifest = json.loads(manifest_path.read_text())
entry = manifest['cases'][0]


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


for number, candidate in enumerate(entry['candidates'], 1):
    ident = f'fallback{number}'
    offline = REPO / '.runtime-work' / f'c111588-both-hands-fb{number}-offline-a/offline.log'
    compat_dir = REPO / '.runtime-work' / f'c111588-both-hands-fb{number}-compat-a'
    log = FOLDER / f'{ident}-tests.log'
    receipt = FOLDER / f'{ident}-receipt.json'
    analysis = FOLDER / f'{ident}-analysis.log'
    negative = FOLDER / f'{ident}-negative.log'
    for source, target in ((offline, log), (compat_dir / 'compatibility.json', receipt),
                           (compat_dir / 'compatibility-analysis.log', analysis),
                           (compat_dir / 'negative-analysis.log', negative)):
        shutil.copy2(source, target)
    data = json.loads(receipt.read_text())
    if not data['passed'] or data['candidate_id'] != ident or data['construction_sha256'] != candidate['construction_sha256']:
        raise ValueError('Fallback proof selected wrong construction')
    candidate['offline'] = {'command': '.venv-cpu/bin/python runtime.py offline --manifest '
        'work/heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator/both-hands-manifest.json '
        f'--case {entry["case_id"]} --candidate {ident} '
        f'--output .runtime-work/c111588-both-hands-fb{number}-offline-a '
        '--python /scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-held/.venv-cpu/bin/python',
        'exit_code': 0, 'log': str(log.relative_to(ROOT)),
        'log_sha256': sha(log), 'construction_sha256': candidate['construction_sha256']}
    candidate['compatibility'] = {'receipt': str(receipt.relative_to(ROOT)), 'sha256': sha(receipt),
        'log': str(analysis.relative_to(ROOT)), 'negative_log': str(negative.relative_to(ROOT))}
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
print('both-hands three fallback proof bindings complete')
