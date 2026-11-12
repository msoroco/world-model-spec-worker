"""Bind the current draft semantic stage chain to source hashes."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROPOSALS = ROOT / 'proposals'


def reference(name):
    path = PROPOSALS / name
    return {'path': 'proposals/' + name,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    template = json.loads((PROPOSALS / 'template.json').read_text())
    index = {
        'format': 'worker-semantic-delivery', 'assignment_id': ROOT.name,
        'stages': {
            'relevance_batch': reference('relevance-batch.json'),
            'relevance': reference('relevance.json'),
            'template': reference('template.json'),
            'judgment_observables': [
                reference(f'judgment-observables-{i}.json')
                for i, _ in enumerate(template['structure']['judgment_calls_needed'], 1)],
            'bindings': reference('bindings.json'),
            'cases': reference('cases.json'),
        },
    }
    (PROPOSALS / 'semantic-index.json').write_text(json.dumps(index, indent=2) + '\n')
    print(json.dumps({'stages': list(index['stages']),
                      'judgment_observables': len(index['stages']['judgment_observables'])}))


if __name__ == '__main__':
    main()
