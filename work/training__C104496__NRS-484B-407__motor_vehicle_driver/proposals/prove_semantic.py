"""Validate draft semantic stages and ordinary cases against pinned CPU runtime."""
import hashlib
import json
import sys
import copy
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ASSIGNMENT = 'training__C104496__NRS-484B-407__motor_vehicle_driver'
sys.path.insert(0, str(ROOT / 'runtime' / 'pipeline'))
from scenario_pipeline.batch_pipeline.stages import validate  # noqa: E402


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove():
    assignment_path = ROOT / 'inputs' / ASSIGNMENT / 'assignment.json'
    assignment = read(assignment_path)
    law, cell, actor = assignment['law'], assignment['cell'], assignment['actor']
    rules_path = ROOT / 'runtime' / 'pipeline' / 'scenario_pipeline' / 'data' / 'canonical_parameter_aliases.json'
    rules = read(rules_path)
    checked = {}
    for stage, name in (('relevance', 'relevance.json'), ('relevance_batch', 'relevance-batch.json')):
        path = HERE / name
        validate(stage, read(path), {'request': {'cell': cell, 'actor': actor}, 'law_records': {law['id']: law}})
        checked[name] = sha(path)
    path = HERE / 'template.json'
    template = read(path)
    validate('template', template, {'request': {'law_id': law['id'], 'actor': actor},
                                    'law_record': law, 'canonical_parameter_rules': rules})
    checked[path.name] = sha(path)
    for i, call in enumerate(template['structure']['judgment_calls_needed'], 1):
        path = HERE / f'judgment-observables-{i}.json'
        validate('judgment_observables', read(path),
                 {'request': {'template_id': template['template_id'], **call}})
        checked[path.name] = sha(path)
    path = HERE / 'bindings.json'
    binding = read(path)
    validate('bindings', binding,
             {'request': {'cell': cell, 'actor': actor, 'template_ids': [template['template_id']]},
              'canonical_parameter_rules': rules})
    checked[path.name] = sha(path)
    decorated = read(HERE / 'template.json')
    for i, judgment in enumerate(decorated['structure']['judgment_calls_needed'], 1):
        judgment['observable_requirements'] = read(HERE / f'judgment-observables-{i}.json')['observable_requirements']
    path = HERE / 'cases.json'
    cases = read(path)
    case_inputs = {
        'request': {'cell': cell, 'actor': actor},
        'dependencies': [binding], 'templates': [decorated],
        'canonical_parameter_rules': rules}
    validate('cases', cases, case_inputs)
    checked[path.name] = sha(path)
    rejections = {}
    for name in ('missing_geometry_variable', 'guaranteed_reversal', 'missing_visibility_source', 'asserted_verdict'):
        changed = copy.deepcopy(cases)
        target = changed['cases'][1]
        if name == 'missing_geometry_variable':
            target['variable_assignments'].pop('grade_height_m')
        elif name == 'guaranteed_reversal':
            target['variable_assignments']['turn_to_opposite_direction']['value'] = True
        elif name == 'missing_visibility_source':
            target['recording_description']['channels'] = [c for c in target['recording_description']['channels']
                                                          if c['name'] != 'two_direction_visibility']
        else:
            target['legal_verdict'] = 'compliant'
        try:
            validate('cases', changed, case_inputs)
        except ValueError as exc:
            rejections[name] = str(exc)
        else:
            raise AssertionError('Semantic negative was accepted: ' + name)
    proof = {'format': 'c104496-canonical-semantic-foundation-proof',
             'assignment_id': ASSIGNMENT, 'passed': True,
             'pinned_runtime_source_manifest_sha256': sha(ROOT / 'runtime' / 'pipeline' / 'SOURCE-MANIFEST.json'),
             'input_sha256': sha(assignment_path), 'canonical_rules_sha256': sha(rules_path),
             'stage_artifacts_sha256': checked, 'validated_stage_count': len(checked),
             'negative_rejections': rejections,
             'original_native_observed': False, 'delivery_ready': False,
             'remaining_semantic_stage': 'complete sweep expansion and selected construction remain open'}
    (HERE / 'semantic-foundation-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps(proof, indent=2))


if __name__ == '__main__':
    prove()
