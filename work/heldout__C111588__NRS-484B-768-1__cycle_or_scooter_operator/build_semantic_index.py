"""Bind the exact frozen rider law to the canonical draft semantic stages."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
assignment = json.loads((REPO / 'inputs' / ASSIGNMENT / 'assignment.json').read_text())
text = assignment['law']['text']
quote = 'an operator of a bicycle, an electric bicycle or an electric scooter upon a roadway shall not turn from a direct course unless the movement may be made with reasonable safety and the operator gives an appropriate signal.'
assert quote in text
relevance = {'cell_id': assignment['cell_id'], 'actor': assignment['actor'], 'status': 'draft',
    'relevant_laws': [{'law_id': assignment['law_id'], 'quote': quote,
                       'applies_to': [assignment['actor']], 'relevance_type': 'specific_match',
                       'confidence': 'high',
                       'notes': 'The assigned cycle-or-scooter turn cell is actor-compatible. Roadway occupancy, direct-course turn, device class and both exceptions still require original source evidence.'}],
    'borderline_excluded': []}
folder = ROOT / 'proposals'
for name in ('relevance.json', 'relevance_batch.json'):
    (folder / name).write_text(json.dumps(relevance, indent=2) + '\n')

def ref(name):
    path = folder / name
    return {'path': 'proposals/' + name, 'sha256': sha256(path.read_bytes()).hexdigest()}

index = {'format': 'worker-semantic-delivery', 'assignment_id': ASSIGNMENT,
    'stages': {'relevance_batch': ref('relevance_batch.json'), 'relevance': ref('relevance.json'),
               'template': ref('template.json'), 'bindings': ref('bindings.json'),
               'cases': ref('cases-stage-proposal.json'),
               'judgment_observables': [ref(f'judgment-{i}.json') for i in (1,2,3)]}}
(folder / 'semantic-index.json').write_text(json.dumps(index, indent=2) + '\n')
print('Exact frozen rider relevance and six-stage semantic index bound')
