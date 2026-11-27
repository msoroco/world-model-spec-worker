"""Write exact bridge-clause semantic proposals with unresolved judgments."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
ROOT = FOLDER.parents[1]
AID = FOLDER.name
ORIGINAL = json.loads((ROOT / 'inputs' / AID / 'assignment.json').read_text())
LAW = ORIGINAL['law_id']
ACTOR = ORIGINAL['actor']
TEXT = ORIGINAL['law']['text']
TEMPLATE = LAW + '@' + ACTOR


def write(name, value):
    path = FOLDER / 'proposals' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    return {'path': str(path.relative_to(FOLDER)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    desc = json.loads((FOLDER / 'cases/false/primary/construction.json').read_text())['recording_description']
    refs = {}
    relevance = {'cell_id': ORIGINAL['cell_id'], 'actor': ACTOR, 'status': 'draft',
        'relevant_laws': [{'law_id': LAW, 'quote': TEXT, 'applies_to': [ACTOR],
            'relevance_type': 'specific_match', 'confidence': 'high',
            'notes': 'Frozen bridge stop cell; physical support, actual activity and exceptions require original review.'}],
        'borderline_excluded': []}
    refs['relevance_batch'] = write('relevance-batch.json', relevance)
    refs['relevance'] = write('relevance.json', relevance)
    judgments = [
        {'phrase': 'stop, stand or park',
         'note': 'Original velocity and footprint are measured; responsible activity and purpose remain source-review questions.'},
        {'phrase': 'Upon any bridge or other elevated structure or within a highway tunnel',
         'note': 'Native elevation and footprint survey must be tied to actual bridge support or tunnel structure.'},
        {'phrase': 'except when necessary to avoid conflict with other traffic',
         'note': 'Traffic necessity and law, police or device direction require original source review.'}]
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
        'status': 'draft', 'quote': TEXT,
        'structure': {
            'activation': {'description': 'Observe exact source-grounded bridge, elevated structure or tunnel occupancy.',
                           'source_clause': 'Upon any bridge or other elevated structure or within a highway tunnel.'},
            'obligation': {'description': 'Observe the vehicle stop, stand or park activity at the selected place without legal label.',
                           'type': 'must_not', 'source_clause': 'A person shall not stop, stand or park a vehicle',
                           'numeric_conditions': []},
            'exceptions': [
                {'description': 'Review traffic-conflict necessity from original traffic sources.',
                 'source_clause': 'except when necessary to avoid conflict with other traffic'},
                {'description': 'Review applicable law separately.', 'source_clause': 'in compliance with law'},
                {'description': 'Review police or official device direction separately.',
                 'source_clause': 'the directions of a police officer or official traffic-control device'}],
            'timing': {'description': 'Review every original frame during the observed stop; no invented duration cutoff.'},
            'judgment_calls_needed': judgments},
        'parameter_refs': [
            {'name': 'stationary_footprint_on_bridge', 'kind': 'subject_behavior',
             'range_or_domain': 'source-measured full, partial or absent bridge footprint overlap at rest'},
            {'name': 'requested_station_bridge', 'kind': 'controller',
             'range_or_domain': 'requested ground control or bridge destination'},
            {'name': 'exception_context', 'kind': 'world_setup',
             'range_or_domain': 'original traffic, other-law, police and device sources'}]}
    refs['template'] = write('template.json', template)
    observed = []
    for i, (judgment, name) in enumerate(zip(judgments,
            ('stationary_candidate', 'bridge_relation', 'traffic_conflict_context')), 1):
        requirement = {'observables': [{'name': name, 'unit': 'structured',
            'description': 'Original source-joined observation of ' + name}],
            'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
            'recording_needs': [{'name': name, 'unit': 'structured',
                'description': 'Retain original sources and review join for ' + name}],
            'limitations': ['Synthetic diagnostics prove software joins only; physical structure and legal result remain open.']}
        observed.append(write('judgment-%d.json' % i,
            {'template_id': TEMPLATE, 'phrase': judgment['phrase'], 'note': judgment['note'],
             'status': 'draft', 'observable_requirements': requirement}))
    refs['judgment_observables'] = observed
    refs['bindings'] = write('bindings.json', {
        'cell_id': ORIGINAL['cell_id'], 'actor': ACTOR, 'status': 'draft',
        'established_contexts': [], 'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [{'name': 'bridge_cell_context',
            'value': 'frozen bridge and other_vehicle cell',
            'rationale': 'Frozen catalog context; physical support and exception sources remain for original review.'}],
        'variable_parameters': [
            {'name': 'stationary_footprint_on_bridge', 'kind': 'subject_behavior',
             'range_or_domain': 'full, partial or absent measured footprint overlap', 'used_by_laws': [LAW]},
            {'name': 'requested_station_bridge', 'kind': 'controller',
             'range_or_domain': 'ground or bridge requested destination', 'used_by_laws': [LAW]}]})
    base = {'case_id': AID + '__baseline', 'target_law_id': None,
        'target_type': 'baseline', 'rationale': 'Observe passing bridge context before selected stop.',
        'variable_assignments': {'stationary_footprint_on_bridge': {'kind': 'subject_behavior', 'value': None},
                                 'requested_station_bridge': {'kind': 'controller', 'value': None}},
        'unresolved_judgment_calls': [j['phrase'] for j in judgments],
        'recording_description': desc}
    cases = [base]
    for suffix, bridge in (('false', False), ('true', True)):
        cases.append({'case_id': AID + '__' + suffix, 'target_law_id': LAW,
            'target_type': 'boundary_probe', 'paired_probe_id': 'bridge-station-control',
            'rationale': 'Measure original stationary body ' + ('on bridge' if bridge else 'on ground') +
                         '; retain physical and legal review.',
            'deliberate_differences': ['requested_station_bridge'],
            'variable_assignments': {
                'stationary_footprint_on_bridge': {'kind': 'subject_behavior', 'value': None},
                'requested_station_bridge': {'kind': 'controller', 'value': bridge}},
            'unresolved_judgment_calls': [j['phrase'] for j in judgments],
            'recording_description': desc,
            'probe': {'primary_variable': 'stationary_footprint_on_bridge',
                      'comparison_or_standard': 'source-surveyed bridge deck and original body footprint',
                      'target_value_or_branch': 'bridge' if bridge else 'ground'}})
    refs['cases'] = write('cases.json', {'cell_id': ORIGINAL['cell_id'], 'actor': ACTOR,
        'status': 'draft', 'sweep_specs': [{
            'sweep_id': 'bridge-stop-judgment-review', 'target_law_id': LAW,
            'judgment_refs': judgments, 'status': 'incomplete',
            'rationale': 'Original source review of stopping, bridge support and traffic exceptions is pending.',
            'missing_inputs': ['Original Native capture and independent structural and exception sources.']}],
        'sweeps_expanded': True, 'cases': cases})
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
                                  'assignment_id': AID, 'stages': refs})
    print(json.dumps({'stage_files': 8, 'selected_cases': 2}))


if __name__ == '__main__':
    build()
