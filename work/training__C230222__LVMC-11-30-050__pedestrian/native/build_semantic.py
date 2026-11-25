"""Author canonical draft stage chain for the exact crossing comparison."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROPOSALS = ROOT / 'proposals'
LAW = 'LVMC-11-30-050'
ACTOR = 'pedestrian'
CELL = 'C230222'
QUOTE = ('No pedestrian shall cross a roadway at any place other than by a route '
         'at right angles to the curb or by the shortest route to the opposite curb '
         'except in a crosswalk.')


def write(name, value):
    path = PROPOSALS / name
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': str(path.relative_to(ROOT)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    relevance = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': QUOTE,
                     'applies_to': [ACTOR], 'relevance_type': 'direct',
                     'confidence': 'high', 'notes': 'The selected pedestrian crosses the authored roadway; actual map and crossing pixels require original review.'}],
                 'borderline_excluded': []}
    rel = write('relevance.json', relevance)
    rel_batch = write('relevance-batch.json', relevance)
    parameter = {'name': 'requested_crossing_path_geometry', 'kind': 'controller',
                 'range_or_domain': ['right_angle', 'longer_diagonal']}
    template = {'template_id': LAW + '@' + ACTOR, 'law_id': LAW, 'actor': ACTOR,
                'quote': QUOTE, 'status': 'draft',
                'structure': {'law_id': LAW,
                    'activation': {'condition': 'pedestrian crosses a roadway', 'numeric_conditions': []},
                    'obligation': {'type': 'must',
                        'description': 'outside a crosswalk, use either a route at right angles to the curb or the shortest route to the opposite curb',
                        'numeric_conditions': []},
                    'exceptions': [{'trigger': 'crossing in a crosswalk',
                        'effect': 'the outside-crosswalk route alternatives are not the applicable branch',
                        'source_clause': 'except in a crosswalk.'}],
                    'timing': {'description': 'observe the pedestrian route from entry at the origin curb to the opposite curb',
                               'numeric_conditions': []},
                    'judgment_calls_needed': []}, 'parameter_refs': [parameter]}
    template_ref = write('template.json', template)
    binding = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
               'established_contexts': ['Authored roadway and curbs with no authored crosswalk; actual Native map and pixels remain to be reviewed'],
               'law_refs': [{'template_id': template['template_id'], 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [{**parameter, 'used_by_laws': [LAW]}]}
    binding_ref = write('bindings.json', binding)
    cases = json.loads((PROPOSALS / 'cases.json').read_text())
    cases['cases'][0]['variable_assignments']['requested_crossing_path_geometry']['kind'] = 'controller'
    cases['cases'][1]['variable_assignments']['requested_crossing_path_geometry']['kind'] = 'controller'
    cases['cases'][2]['variable_assignments']['requested_crossing_path_geometry']['kind'] = 'controller'
    cases['cases'][1]['target_type'] = 'compliant_attempt'
    cases['cases'][2]['target_type'] = 'violating_attempt'
    cases['cases'][1]['rationale'] = 'Request a right-angle outside-crosswalk route; original motion and pixels decide observed geometry, without a legal verdict.'
    cases['cases'][2]['rationale'] = 'Request a longer diagonal outside-crosswalk route for a physical comparison; original motion and pixels decide observed geometry, without a legal verdict.'
    cases_ref = write('cases.json', cases)
    index = {'format': 'worker-semantic-delivery', 'assignment_id': ROOT.name,
             'stages': {'relevance_batch': rel_batch, 'relevance': rel,
                        'template': template_ref, 'judgment_observables': [],
                        'bindings': binding_ref, 'cases': cases_ref}}
    write('semantic-index.json', index)
    print(json.dumps({'stage_count': 5, 'case_count': 2}))


if __name__ == '__main__':
    main()
