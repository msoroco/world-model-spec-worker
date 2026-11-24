"""Validate the C110763 canonical semantic foundation against pinned contracts."""
import hashlib
import json
import sys
from pathlib import Path

repo = Path(__file__).resolve().parents[2]
folder = Path(__file__).resolve().parent
sys.path.insert(0, str(repo / 'runtime/pipeline'))
sys.path.insert(0, str(repo / 'runtime/pipeline/scenario_pipeline'))
from batch_pipeline import stages

assignment = json.loads((repo / 'inputs' / folder.name / 'assignment.json').read_text())
proposals = folder / 'proposals'
load = lambda name: json.loads((proposals / name).read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
request = {'cell': assignment['cell'], 'actor': assignment['actor']}
common = {'request': request, 'law_records': {assignment['law_id']: assignment['law']}, 'dependencies': []}
files = ['relevance-batch.json', 'relevance.json', 'template.json', 'bindings.json']
files += [f'judgment-observables-{i}.json' for i in range(1, 4)]
for stage, name in [('relevance_batch', files[0]), ('relevance', files[1])]:
    stages.validate(stage, load(name), common)
assert load(files[0]) == load(files[1])
template = load('template.json')
rules = json.loads((stages.ROOT / 'data/canonical_parameter_aliases.json').read_text())
stages.validate('template', template, {'request': {'law_id': assignment['law_id'], 'actor': assignment['actor']}, 'law_record': assignment['law'], 'canonical_parameter_rules': rules, 'dependencies': []})
judgments = template['structure']['judgment_calls_needed']
assert len(judgments) == 3
for i, judgment in enumerate(judgments, 1):
    observed = load(f'judgment-observables-{i}.json')
    stages.validate('judgment_observables', observed, {'request': {'template_id': template['template_id'], 'phrase': judgment['phrase'], 'note': judgment['note']}, 'dependencies': []})
    assert (observed['phrase'], observed['note']) == (judgment['phrase'], judgment['note'])
    judgment['observable_requirements'] = observed['observable_requirements']
binding = load('bindings.json')
stages.validate('bindings', binding, {'request': dict(request, template_ids=[template['template_id']]), 'canonical_parameter_rules': rules, 'dependencies': [template]})
assert [entry['template_id'] for entry in binding['law_refs']] == [template['template_id']]
proof = {'format': 'semantic-foundation-check-v1', 'assignment_id': assignment['assignment_id'], 'status': 'foundation_only', 'validated_stages': ['relevance_batch', 'relevance', 'template', 'judgment_observables_1', 'judgment_observables_2', 'judgment_observables_3', 'bindings'], 'sources': {name: sha(proposals / name) for name in files}, 'remaining': 'cases stage and full semantic delivery index; original motion and all delivery audits'}
(proposals / 'semantic-foundation-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
print('semantic_foundation_validated', len(proof['validated_stages']))
