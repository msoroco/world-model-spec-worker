"""Build exact-law canonical stage proposals without legal outcome labels."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parents[1]
AID = FOLDER.name
LAW = 'LVMC-11-40-130'
ACTOR = 'cycle_or_scooter_operator'
CELL = 'C111325'
TEMPLATE = LAW + '@' + ACTOR
PHRASES = [
    ('reasonable and prudent', 'No numeric bicycle-speed cutoff is supplied; original context needs independent review.'),
    ('under the conditions then existing', 'Observe original road, weather, approach and pedestrian context without deciding prudence.'),
]


def write(name, value):
    path = FOLDER / 'proposals' / name
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': str(path.relative_to(FOLDER)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    assignment = json.loads((REPO / 'inputs' / AID / 'assignment.json').read_text())
    quote = assignment['law']['text']
    original = json.loads((FOLDER / 'proposals' / 'cases.json').read_text())
    selected = original['cases']
    desc = selected[0]['recording_description']
    relevance = {
        'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
        'relevant_laws': [{'law_id': LAW, 'quote': quote, 'applies_to': [ACTOR],
                           'relevance_type': 'specific_match', 'confidence': 'medium',
                           'notes': 'Bicycle operator and context fit the selected cell; municipal applicability and prudence await local review.'}],
        'borderline_excluded': [],
    }
    template = {
        'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR, 'status': 'draft', 'quote': quote,
        'structure': {
            'activation': {'source_clause': 'operate a bicycle', 'description': 'Original bicycle operator rides in the selected stop-sign approach.'},
            'obligation': {'source_clause': 'speed greater than is reasonable and prudent', 'description': 'Preserve the qualitative speed judgment; no legal numeric limit is supplied.'},
            'exceptions': [],
            'timing': {'source_clause': 'under the conditions then existing', 'description': 'Review conditions throughout the original approach interval.'},
            'judgment_calls_needed': [{'phrase': phrase, 'note': note} for phrase, note in PHRASES],
        },
        'parameter_refs': [],
    }
    bindings = {
        'cell_id': CELL, 'actor': ACTOR, 'status': 'draft', 'established_contexts': [],
        'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}], 'context_refs': [],
        'fixed_parameters': [],
        'variable_parameters': [
            {'name': 'bicycle_approach_speed', 'kind': 'controller', 'range_or_domain': '3 or 5 m/s engineering contrast; actual Native speed measured', 'used_by_laws': [LAW]},
            {'name': 'route_and_conditions', 'kind': 'world_setup', 'range_or_domain': 'same surveyed dry clear stop-sign approach', 'used_by_laws': [LAW]},
        ],
    }
    baseline = {
        'case_id': AID + '__baseline', 'target_law_id': None, 'target_type': 'baseline',
        'rationale': 'Neutral unselected stop-sign bicycle approach context.',
        'variable_assignments': deepcopy(selected[0]['variable_assignments']),
        'recording_description': desc,
        'unresolved_judgment_calls': [phrase for phrase, _ in PHRASES],
    }
    baseline['variable_assignments']['bicycle_approach_speed']['value'] = None
    for case in selected:
        case['target_type'] = 'judgment_sweep'
        case['paired_probe_id'] = AID + '__speed_pair'
        case['deliberate_differences'] = ['bicycle_approach_speed']
        case['probe'] = {'primary_variable': 'bicycle_approach_speed',
                         'comparison_or_standard': 'paired measured speed contrast, never a legal threshold',
                         'target_value_or_branch': case['variable_assignments']['bicycle_approach_speed']['value']}
        case['unresolved_judgment_calls'] = [phrase for phrase, _ in PHRASES]
    cases = {
        'format': 'worker-case-proposals', 'cell_id': CELL, 'actor': ACTOR, 'law_id': LAW,
        'status': 'draft', 'cases': [baseline, *selected],
        'sweep_specs': [{
            'sweep_id': AID + '__prudence_review', 'target_law_id': LAW, 'status': 'incomplete',
            'judgment_refs': [{'phrase': phrase, 'note': note} for phrase, note in PHRASES],
            'rationale': 'Selected speed pair provides observations; qualitative legal judgment awaits original physical and independent review.',
            'missing_inputs': ['Original physical bicycle and rider pixels', 'Independent municipal applicability and reasonable-prudence review'],
        }],
        'sweeps_expanded': True,
    }
    refs = {'relevance_batch': write('relevance_batch.json', relevance),
            'relevance': write('relevance.json', relevance),
            'template': write('template.json', template)}
    judgment_refs = []
    for index, (phrase, note) in enumerate(PHRASES):
        observable = {
            'template_id': TEMPLATE, 'phrase': phrase, 'note': note, 'status': 'draft',
            'observable_requirements': {
                'observables': [{'name': 'kin.speed', 'unit': 'structured', 'description': 'Original time-joined bicycle speed trace.'}],
                'context_inputs': [{'name': 'bicycle_stop_approach_context', 'unit': 'structured', 'description': 'Surveyed sign, road, visibility and participant context.'}],
                'sweep_dimensions': [], 'landmarks': [],
                'recording_needs': [{'name': 'kin.speed', 'unit': 'structured', 'description': 'Original time-joined bicycle speed trace.'}],
                'limitations': ['Engineering speed contrast does not resolve legal reasonableness.', 'Original physical rider and pixel checks remain pending.'],
            },
        }
        judgment_refs.append(write(f'judgment_observables_{index}.json', observable))
    refs['judgment_observables'] = judgment_refs
    refs['bindings'] = write('bindings.json', bindings)
    refs['cases'] = write('cases.json', cases)
    write('semantic-index.json', {'format': 'worker-semantic-delivery', 'assignment_id': AID, 'stages': refs})


if __name__ == '__main__':
    main()
