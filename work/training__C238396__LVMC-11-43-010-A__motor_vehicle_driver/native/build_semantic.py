"""Source-based canonical semantic proposals for the exact roundabout direction rule."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
ASSIGNMENT = FOLDER.name
LAW = 'LVMC-11-43-010-A'
TEMPLATE = LAW + '@motor_vehicle_driver'
QUOTE = ('The following regulations pertain to the operation of vehicles within a '
         'roundabout: All vehicular travel shall be in a counterclockwise direction.')


def write(name, value):
    path = FOLDER / 'proposals' / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return path


def ref(path):
    return {'path': str(path.relative_to(FOLDER)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    relevance = {'cell_id': 'C238396', 'actor': 'motor_vehicle_driver',
        'status': 'draft', 'relevant_laws': [{'law_id': LAW, 'quote': QUOTE,
            'applies_to': ['motor_vehicle_driver'], 'relevance_type': 'specific_match',
            'confidence': 'high', 'notes': 'Frozen circulation cell; original jurisdiction and roundabout boundary pending.'}],
        'borderline_excluded': []}
    rel = ref(write('relevance.json', relevance))
    rel_batch = ref(write('relevance_batch.json', relevance))
    template = {'template_id': TEMPLATE, 'law_id': LAW,
        'actor': 'motor_vehicle_driver', 'status': 'draft', 'quote': QUOTE,
        'structure': {'activation': {'condition': 'A vehicle travels within a roundabout.',
                                     'numeric_conditions': []},
            'obligation': {'type': 'must',
                'description': 'All vehicular travel shall be counterclockwise.',
                'numeric_conditions': []},
            'exceptions': [], 'timing': {'description': 'Continuously while within the roundabout.',
                                         'numeric_conditions': []},
            'judgment_calls_needed': []}, 'parameter_refs': []}
    template_ref = ref(write('template.json', template))
    binding = {'cell_id': 'C238396', 'actor': 'motor_vehicle_driver',
        'status': 'draft', 'established_contexts': [{'name': 'roundabout_circulation',
            'source': 'frozen C238396 catalog cell; original boundary and jurisdiction unverified'}],
        'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [{'name': 'direction_sign', 'kind': 'controller',
            'range_or_domain': '+1 counterclockwise or -1 clockwise, engineering request',
            'used_by_laws': [LAW]}]}
    binding_ref = ref(write('bindings.json', binding))
    selected = json.loads((FOLDER / 'proposals/cases.json').read_text())
    baseline = {'case_id': ASSIGNMENT + '__baseline', 'target_law_id': LAW,
        'target_type': 'baseline', 'rationale': 'Neutral nonselected comparison anchor',
        'probe': {'primary_variable': 'direction_sign',
                  'comparison_or_standard': 'counterclockwise source text',
                  'target_value_or_branch': 'baseline'},
        'variable_assignments': {'direction_sign': {'kind': 'controller', 'value': 1}},
        'recording_description': selected['cases'][0]['recording_description'],
        'unresolved_judgment_calls': []}
    selected['cases'].insert(0, baseline)
    cases_ref = ref(write('canonical-cases.json', selected))
    index = {'format': 'worker-semantic-delivery', 'assignment_id': ASSIGNMENT,
        'stages': {'relevance_batch': rel_batch, 'relevance': rel,
                   'template': template_ref, 'judgment_observables': [],
                   'bindings': binding_ref, 'cases': cases_ref}}
    index_path = write('semantic-index.json', index)
    return {'semantic_index_sha256': ref(index_path)['sha256'],
            'judgments': 0}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
