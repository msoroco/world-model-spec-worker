"""Author source-quoted five-stage priority proposals without legal verdict."""
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
A = PACKAGE.name
original = json.loads((Path('inputs') / A / 'assignment.json').read_text())
LAW, CELL, ACTOR = (original[key] for key in ('law_id', 'cell_id', 'actor'))
QUOTE = original['law']['text']
TEMPLATE = LAW + '@' + ACTOR
OUT = PACKAGE / 'proposals'
OUT.mkdir(exist_ok=True)


def write(name, value):
    path = OUT / (name + '.json')
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': str(path.relative_to(PACKAGE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    relevance = {'actor': ACTOR, 'cell_id': CELL, 'status': 'draft',
        'relevant_laws': [{'law_id': LAW, 'quote': QUOTE,
            'applies_to': [ACTOR], 'relevance_type': 'direct',
            'confidence': 'high',
            'notes': 'Frozen intersection travel cell; original device, operability and opposite-turn context remain source dependent.'}],
        'borderline_excluded': []}
    refs = {'relevance_batch': write('relevance-batch', relevance),
            'relevance': write('relevance', relevance)}
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
        'quote': QUOTE, 'status': 'draft',
        'structure': {'activation': {'description': 'Driver approaches intersection while another vehicle entered first from a different highway',
            'source_clause': 'The driver of a vehicle approaching an intersection'},
            'obligation': {'description': 'Yield right-of-way to first-entering vehicle from different highway',
                'type': 'must', 'source_clause': 'shall yield the right-of-way to a vehicle which has entered the intersection from a different highway'},
            'exceptions': [{'description': 'Official traffic-control device governs intersection, subject to subsection 4',
                'source_clause': 'Except as otherwise provided in subsection 4'},
                {'description': 'Opposite approaches and one driver intends or makes a left turn',
                 'source_clause': 'vehicles approaching each other from opposite directions'}],
            'timing': {'description': 'Other entry precedes ego approach and yielding action at conflict entry'},
            'judgment_calls_needed': []},
        'parameter_refs': [{'name': 'ego_yield_action', 'kind': 'controller',
            'range_or_domain': [False, True]}]}
    refs['template'] = write('template', template)
    refs['judgment_observables'] = []
    bindings = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
        'established_contexts': [{'name': 'two_highway_intersection_travel',
            'source': 'frozen intersection/travel/other_vehicle cell and authored two-highway request'}],
        'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [{'name': 'ego_yield_action', 'kind': 'controller',
            'range_or_domain': [False, True], 'used_by_laws': [LAW]}]}
    refs['bindings'] = write('bindings', bindings)
    base = json.loads((PACKAGE / 'native/selected/priority_yield/primary/construction.json').read_text())
    cases = [{'case_id': A + '__baseline', 'target_law_id': None,
        'target_type': 'baseline', 'rationale': 'Unselected neutral intersection definition.',
        'recording_description': base['recording_description'],
        'unresolved_judgment_calls': [],
        'variable_assignments': {'ego_yield_action': {'kind': 'controller',
            'unit': 'boolean', 'value': True}}}]
    for suffix, action in (('priority_yield', True), ('priority_intrusion', False)):
        construction = json.loads((PACKAGE / 'native/selected' / suffix / 'primary/construction.json').read_text())
        cases.append({'case_id': A + '__' + suffix, 'target_law_id': LAW,
            'target_type': 'compliant_attempt' if action else 'violating_attempt',
            'probe': {'primary_variable': 'ego_yield_action',
                'comparison_or_standard': 'other enters first; ego waits until other clears versus enters while other remains',
                'target_value_or_branch': action},
            'paired_probe_id': 'C111294-first-entry-yield',
            'deliberate_differences': ['ego_yield_action'],
            'rationale': 'Original entry order, occupancy, device and turn context must be reviewed before legal judgment.',
            'recording_description': construction['recording_description'],
            'unresolved_judgment_calls': ['original official-device governance',
                'opposite-turn exclusion and legal yielding'],
            'variable_assignments': {'ego_yield_action': {'kind': 'controller',
                'unit': 'boolean', 'value': action}}})
    refs['cases'] = write('cases', {'actor': ACTOR, 'cell_id': CELL,
        'status': 'draft', 'sweeps_expanded': True,
        'cases': cases, 'semantic_status': 'draft', 'sweep_specs': []})
    index = {'assignment_id': A, 'format': 'worker-semantic-delivery',
             'stages': refs}
    (OUT / 'semantic-index.json').write_text(json.dumps(index, indent=2) + '\n')
    return {'selected_cases': 2,
        'index_sha256': hashlib.sha256((OUT / 'semantic-index.json').read_bytes()).hexdigest()}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
