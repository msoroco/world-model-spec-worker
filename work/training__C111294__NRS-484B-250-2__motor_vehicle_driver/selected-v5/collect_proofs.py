"""Bind current selected CPU receipts after the measured timing repair."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent
REPO = ASSIGNMENT.parents[1]
SCRATCH = REPO / '.runtime-work/c111294-2502-selected-v5-portable2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy(source, target):
    if not source.is_file():
        raise ValueError('Missing completed proof: ' + str(source))
    if source.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Oversized returned proof: ' + str(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return sha(target)


def run():
    cases = {}
    for suffix in ('controlled_1', 'controlled_2'):
        choices = {}
        for candidate in ('primary', 'fallback1', 'fallback2'):
            stem = suffix + '-' + candidate
            base = HERE / suffix / candidate
            proof = base / 'proofs'
            sources = {
                'offline.log': SCRATCH / ('offline-' + stem) / 'offline.log',
                'compatibility.json': SCRATCH / ('compat-' + stem) / 'compatibility.json',
                'public-analysis.log': SCRATCH / ('compat-' + stem) / 'compatibility-analysis.log',
                'negative-analysis.log': SCRATCH / ('compat-' + stem) / 'negative-analysis.log',
                'saved-processing.json': SCRATCH / ('saved-' + stem) / 'v0001/processing.json',
                'saved-analysis.log': SCRATCH / ('saved-' + stem) / 'v0001/analysis.log',
            }
            hashes = {name: copy(source, proof / name) for name, source in sources.items()}
            construction_sha = sha(base / 'construction.json')
            compatibility = json.loads((proof / 'compatibility.json').read_text())
            processing = json.loads((proof / 'saved-processing.json').read_text())
            if (not compatibility.get('passed') or
                    compatibility.get('construction_sha256') != construction_sha or
                    compatibility.get('negative_removed') != 'actor-history.json' or
                    processing.get('passed') is not True or
                    processing.get('case_id') != ASSIGNMENT.name + '__' + suffix or
                    processing.get('candidate_id') != candidate or
                    processing.get('missing_evidence') is not False or
                    not processing.get('recorded_only') or
                    not processing.get('originals_preserved')):
                raise ValueError('V5 CPU receipt failed selection binding: ' + stem)
            choices[candidate] = {
                'construction_sha256': construction_sha,
                'fixture_recipe_sha256': sha(ASSIGNMENT / 'selected-v3' / suffix / candidate / 'fixture-recipe.json'),
                'proof_sha256': hashes,
                'recorded_only': True,
                'original_native_observed': False,
            }
        cases[suffix] = choices
    index = {'format': 'c111294-2502-selected-cpu-proof-index-v5',
             'assignment_id': ASSIGNMENT.name,
             'manifest_sha256': sha(ASSIGNMENT / 'selected-v5-manifest.json'),
             'comparison_sha256': sha(ASSIGNMENT / 'selected-v3/comparison-audit.json'),
             'physical_receipt_sha256': {
                 suffix: sha(HERE / 'physical-proofs' / suffix / 'proof.json')
                 for suffix in cases},
             'cases': cases,
             'synthetic_cpu_diagnostic': True,
             'original_native_observed': False,
             'legal_verdict': None}
    path = HERE / 'cpu-proof-index.json'
    path.write_text(json.dumps(index, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'index_sha256': sha(path), 'candidates': 6}))


if __name__ == '__main__':
    run()
