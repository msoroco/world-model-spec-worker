"""Bind exact source-hashed canonical stage proposals to selected delivery IDs."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO/'runtime/scenario_pipeline'))
from worker_exchange.semantic_delivery import validate


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


proposal = ROOT/'proposals'
stages = {}
for name in ('relevance_batch', 'relevance', 'template', 'bindings', 'cases'):
    path = proposal/(name+'.json')
    stages[name] = {'path': str(path.relative_to(ROOT)), 'sha256': sha(path)}
stages['judgment_observables'] = []
for index in range(3):
    path = proposal/f'judgment_observables_{index}.json'
    stages['judgment_observables'].append({'path': str(path.relative_to(ROOT)),
                                          'sha256': sha(path)})
index = {'format': 'worker-semantic-delivery', 'assignment_id': ROOT.name,
         'stages': stages}
destination = proposal/'semantic-index.json'
destination.write_text(json.dumps(index, indent=2, ensure_ascii=False)+'\n')
assignment = json.loads((REPO/'inputs'/ROOT.name/'assignment.json').read_text())
manifest = json.loads((ROOT/'execution-manifest.json').read_text())
print(validate(ROOT, assignment, manifest))
