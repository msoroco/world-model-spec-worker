"""Copy exact branch CPU receipts from runtime scratch into the return package."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
REPO = BASE.parents[1]
SCRATCH = REPO / '.runtime-work'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy(source, target):
    if not source.is_file() or source.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Missing or oversized branch CPU proof: ' + str(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return sha(target)


def run():
    cases = {}
    for suffix in ('device_controlled', 'opposing_no_turn', 'opposing_left_turn'):
        choices = {}
        for candidate in ('primary', 'fallback2'):
            name = suffix + '-' + candidate
            runtime_name = 'device-primary' if name == 'device_controlled-primary' else name
            compat = SCRATCH / ('c111294-2502-branch-compat-' + runtime_name + ('3' if name == 'device_controlled-primary' else ''))
            saved = SCRATCH / ('c111294-2502-branch-saved-' + runtime_name) / 'v0001'
            offline = SCRATCH / ('c111294-2502-branch-offline-' + name + '-latest')
            proof = HERE / suffix / candidate / 'proofs'
            inputs = {
                'offline.log': offline / 'offline.log',
                'compatibility.json': compat / 'compatibility.json',
                'public-analysis.log': compat / 'compatibility-analysis.log',
                'negative-analysis.log': compat / 'negative-analysis.log',
                'saved-processing.json': saved / 'processing.json',
                'saved-analysis.log': saved / 'analysis.log',
            }
            hashes = {key: copy(path, proof / key) for key, path in inputs.items()}
            construction_sha = sha(HERE / suffix / candidate / 'construction.json')
            public = json.loads((proof / 'compatibility.json').read_text())
            processed = json.loads((proof / 'saved-processing.json').read_text())
            if (public.get('passed') is not True or
                    public.get('construction_sha256') != construction_sha or
                    public.get('negative_removed') != 'actor-history.json' or
                    processed.get('passed') is not True or
                    processed.get('case_id') != BASE.name + '__' + suffix or
                    processed.get('candidate_id') != candidate or
                    processed.get('missing_evidence') is not False or
                    processed.get('recorded_only') is not True or
                    processed.get('originals_preserved') is not True):
                raise ValueError('Branch CPU receipt failed exact selection binding: ' + name)
            choices[candidate] = {'construction_sha256': construction_sha,
                                  'proof_sha256': hashes,
                                  'recorded_only': True,
                                  'original_native_observed': False}
        cases[suffix] = choices
    index = {'format': 'c111294-2502-branch-cpu-proof-index-v1',
             'assignment_id': BASE.name,
             'manifest_sha256': sha(BASE / 'branch-v1-manifest.json'),
             'source_proof_sha256': sha(HERE / 'source-proof.json'),
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
