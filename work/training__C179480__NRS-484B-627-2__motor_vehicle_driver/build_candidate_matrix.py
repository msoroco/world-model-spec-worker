"""Assemble the four current case bundles for selection review and CPU checks.

This is a diagnostic matrix. It deliberately contains no readiness claim or
copied proof bindings; final selection must resolve the governing-control cell
question and rerun exact proofs against the selected manifest.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = ('reference', 'contrast', 'safe_operation_stop', 'law_required_stop')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    entries = []
    for name in CASES:
        draft = json.loads((HERE / f'draft-{name}-fallback-manifest.json').read_text())
        if len(draft['cases']) != 1:
            raise ValueError(f'Expected one exact draft case: {name}')
        entry = draft['cases'][0]
        primary = HERE / entry['construction']
        if sha(primary) != entry['construction_sha256']:
            raise ValueError(f'Primary construction changed: {name}')
        if len(entry['candidates']) != 3:
            raise ValueError(f'Expected three alternatives: {name}')
        for candidate in entry['candidates']:
            if sha(HERE / candidate['construction']) != candidate['construction_sha256']:
                raise ValueError(f'Fallback construction changed: {name}/{candidate["id"]}')
        entries.append(entry)
    result = {
        'format': 'worker-execution-manifest',
        'assignment_id': HERE.name,
        'runtime_manifest_sha256': draft['runtime_manifest_sha256'],
        'status': 'selection_candidate_cpu_diagnostic',
        'selection_review': {
            'law': 'NRS 484B.627(2)',
            'method': 'Four source-visible cases cover the roadway-stop contrast and the two statutory exceptions; compare original Native sources before any physical or legal finding.',
            'unresolved': [
                'The law-required-stop traffic-light control needs an independently verified compatible C179480 cell or an approved additional binding.',
                'Three controlled comparisons and independent physical and delivery audits remain untested.',
            ],
        },
        'cases': entries,
    }
    target = HERE / 'candidate-matrix-manifest.json'
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    return target


if __name__ == '__main__':
    print(build())
