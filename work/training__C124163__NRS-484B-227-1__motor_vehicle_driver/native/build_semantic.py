"""Author canonical source-quoted semantic proposals for the selected cell."""
import hashlib
import json
from pathlib import Path
import sys

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG))
from median_scene import CASES, request

A = PKG.name
assignment = json.loads((Path('inputs')/A/'assignment.json').read_text())
LAW, CELL, ACTOR = (assignment[key] for key in ('law_id', 'cell_id', 'actor'))
QUOTE = assignment['law']['text']
TEMPLATE = LAW+'@'+ACTOR
P = PKG/'proposals'
P.mkdir(exist_ok=True)


def write(name, value):
    path = P/(name+'.json')
    path.write_text(json.dumps(value, indent=2)+'\n')
    return {'path': str(path.relative_to(PKG)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    relevance = {'actor': ACTOR, 'cell_id': CELL, 'status': 'draft',
        'relevant_laws': [{'law_id': LAW, 'quote': QUOTE,
            'applies_to': [ACTOR], 'relevance_type': 'direct',
            'confidence': 'high',
            'notes': 'Frozen divided-highway median-opening left-turn cell. Public-authority establishment remains source dependent.'}],
        'borderline_excluded': []}
    refs = {'relevance_batch': write('relevance-batch', relevance),
            'relevance': write('relevance', relevance)}
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
        'quote': QUOTE, 'status': 'draft',
        'structure': {'activation': {'description': 'Vehicle driven on divided highway',
            'source_clause': 'Every vehicle driven upon a divided highway'},
            'obligation': {'description': 'Use the right-hand roadway and do not cross dividing space or turn outside listed exceptions',
                'type': 'must',
                'source_clause': 'must be driven only upon the right-hand roadway and must not be driven over, across or within any dividing space, barrier or section or make any left turn, semicircular turn or U-turn'},
            'exceptions': [{'description': 'Through physical opening in barrier or dividing section or space',
                'source_clause': 'except through an opening in the barrier or dividing section or space'},
                {'description': 'At crossover or intersection established by public authority',
                 'source_clause': 'or at a crossover or intersection established by a public authority'}],
            'timing': {'description': 'Right-hand-roadway duty continuously; turn and crossing at event'},
            'judgment_calls_needed': []},
        'parameter_refs': [{'name': 'target_crossing_x_m', 'kind': 'controller',
            'range_or_domain': [0, 12]},
            {'name': 'physical_median_crossing_location', 'kind': 'world_setup',
             'range_or_domain': ['opening', 'continuous_section']}]}
    refs['template'] = write('template', template)
    refs['judgment_observables'] = []
    bindings = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
        'established_contexts': [{'name': 'divided_highway_left_turn',
            'source': 'frozen C124163 median_opening/left_turn/median_barrier cell with authored selected geometry'}],
        'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [{'name': 'target_crossing_x_m',
            'kind': 'controller', 'range_or_domain': [0, 12], 'used_by_laws': [LAW]},
            {'name': 'physical_median_crossing_location', 'kind': 'world_setup',
             'range_or_domain': ['opening', 'continuous_section'],
             'used_by_laws': [LAW]}]}
    refs['bindings'] = write('bindings', bindings)
    base = json.loads((PKG/'native/bundles/through_opening/construction.json').read_text())
    cases = [{'case_id': A+'__baseline', 'target_law_id': None,
        'target_type': 'baseline', 'rationale': 'Unselected neutral divided-road definition; no legal outcome asserted.',
        'recording_description': base['recording_description'],
        'unresolved_judgment_calls': [],
        'variable_assignments': {'target_crossing_x_m': {
            'kind': 'controller', 'unit': 'm', 'value': 0},
            'physical_median_crossing_location': {'kind': 'world_setup',
                'unit': 'category', 'value': 'opening'}}}]
    for suffix, target in CASES.items():
        cid = A+'__'+suffix
        construction = json.loads((PKG/'native/bundles'/suffix/'construction.json').read_text())
        cases.append({'case_id': cid, 'target_law_id': LAW,
            'target_type': 'compliant_attempt' if suffix == 'through_opening' else 'violating_attempt',
            'probe': {'primary_variable': 'physical_median_crossing_location',
                'comparison_or_standard': 'physical opening versus continuous median section',
                'target_value_or_branch': target['physical_target']},
            'paired_probe_id': 'C124163-median-crossing',
            'deliberate_differences': ['target_crossing_x_m',
                'physical_median_crossing_location'],
            'rationale': 'Original full-body crossing and roadway sources measured; public authority remains separate original-source fact.',
            'recording_description': construction['recording_description'],
            'unresolved_judgment_calls': [],
            'variable_assignments': {'target_crossing_x_m': {'kind': 'controller',
                'unit': 'm', 'value': target['crossing_x_m']},
                'physical_median_crossing_location': {'kind': 'world_setup',
                    'unit': 'category', 'value': target['physical_target']}}})
    proposal = {'actor': ACTOR, 'cell_id': CELL, 'status': 'draft',
        'sweeps_expanded': True, 'cases': cases,
        'semantic_status': 'draft', 'sweep_specs': []}
    refs['cases'] = write('cases', proposal)
    index = {'assignment_id': A, 'format': 'worker-semantic-delivery',
             'stages': refs}
    (P/'semantic-index.json').write_text(json.dumps(index, indent=2)+'\n')
    return {'cases': len(cases),
            'index_sha256': hashlib.sha256((P/'semantic-index.json').read_bytes()).hexdigest()}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
