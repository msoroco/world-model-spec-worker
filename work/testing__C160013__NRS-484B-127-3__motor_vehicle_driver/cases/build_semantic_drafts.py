"""Author and check the first four canonical caravan semantic stages."""
import json
import os
import sys
import hashlib
from copy import deepcopy
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
if not root.is_relative_to((REPO / '.runtime-work').resolve()):
    raise RuntimeError('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first')
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from batch_pipeline import stages

assignment = json.loads((REPO / 'inputs' / PACKAGE.name / 'assignment.json').read_text())
law = assignment['law']
aid, law_id, cell_id, actor = (assignment[k] for k in
                               ('assignment_id', 'law_id', 'cell_id', 'actor'))
template_id = law_id + '@' + actor
phrase = 'sufficient space between each such vehicle or combination of vehicles so as to enable any other vehicle or combination of vehicles to enter and occupy such space without danger'
note = 'Physical entry and body separation are observable; the statutory sufficiency and danger judgment has no supplied numerical cutoff.'
relevance = {
    'cell_id': cell_id, 'actor': actor, 'status': 'draft',
    'relevant_laws': [{'law_id': law_id, 'quote': law['text'], 'applies_to': [actor],
                       'relevance_type': 'caravan following on a highway outside a business district',
                       'confidence': 'medium',
                       'notes': 'Cell layout and maneuver match; caravan membership and district designation require reviewed original sources.'}],
    'borderline_excluded': []}
template = {
    'template_id': template_id, 'law_id': law_id, 'actor': actor, 'status': 'draft',
    'quote': law['text'],
    'structure': {'law_id': law_id,
                  'activation': {'condition': 'motor vehicles being driven upon a highway outside a business district in a caravan or motorcade, whether or not towing other vehicles', 'numeric_conditions': []},
                  'obligation': {'description': 'operate to allow sufficient space between each vehicle or combination for another vehicle or combination to enter and occupy without danger', 'type': 'must', 'numeric_conditions': []},
                  'exceptions': [],
                  'timing': {'description': 'while the caravan or motorcade vehicles are being driven on the qualifying highway', 'numeric_conditions': []},
                  'judgment_calls_needed': [{'phrase': phrase, 'note': note}]},
    'parameter_refs': [
        {'name': 'outside_business_district', 'kind': 'world_setup', 'range_or_domain': 'reviewed highway district classification or unresolved'},
        {'name': 'caravan_membership', 'kind': 'world_setup', 'range_or_domain': 'reviewed caravan or motorcade membership or unresolved'},
        {'name': 'caravan_body_gap', 'kind': 'subject_behavior', 'range_or_domain': 'observed complete-body opening on original frames'},
        {'name': 'entrant_gap_occupancy', 'kind': 'subject_behavior', 'range_or_domain': 'observed complete-body entry and occupancy'},
        {'name': 'member_contact', 'kind': 'subject_behavior', 'range_or_domain': 'observed original body contact'},
        {'name': 'entrant_route_target', 'kind': 'controller', 'range_or_domain': 'authored approach route toward or short of a selected caravan gap'},
        {'name': 'caravan_spacing_target', 'kind': 'controller', 'range_or_domain': 'authored physical member spacing target; no legal threshold'}]}
judgment = {
    'template_id': template_id, 'phrase': phrase, 'note': note, 'status': 'draft',
    'observable_requirements': {
        'observables': [
            {'name': 'caravan_member_bodies', 'unit': 'polygon metres', 'description': 'Original complete body positions for each member through travel.'},
            {'name': 'entering_vehicle_body', 'unit': 'polygon metres', 'description': 'Original complete body positions for another vehicle or combination.'},
            {'name': 'inter_body_opening', 'unit': 'metres', 'description': 'Opening between consecutive complete member bodies.'},
            {'name': 'entrant_gap_occupancy', 'unit': 'boolean', 'description': 'Observed entry and complete occupancy between the member bodies.'},
            {'name': 'member_contact', 'unit': 'boolean', 'description': 'Observed contact among entrant and caravan members.'}],
        'context_inputs': [
            {'name': 'road_context', 'unit': 'structured record', 'description': 'Reviewed map and district designation, caravan membership, route, lane, and vehicle composition.'}],
        'sweep_dimensions': [
            {'name': 'caravan_spacing_target', 'unit': 'metres', 'description': 'Physical controller spacing varied across feasible original captures.'}],
        'landmarks': [],
        'recording_needs': [
            {'name': 'caravan_member_bodies', 'unit': 'polygon metres', 'description': 'Synchronized complete bodies and member identity on original frames.'},
            {'name': 'entering_vehicle_body', 'unit': 'polygon metres', 'description': 'Synchronized complete entrant body on original frames.'},
            {'name': 'inter_body_opening', 'unit': 'metres', 'description': 'Continuous original-frame openings.'},
            {'name': 'entrant_gap_occupancy', 'unit': 'boolean', 'description': 'Original-frame entry and occupancy.'},
            {'name': 'member_contact', 'unit': 'boolean', 'description': 'Original-frame body contact.'}],
        'limitations': ['No supplied statutory numeric sufficiency or danger threshold.',
                        'Contact absence and gap occupancy alone do not decide the legal judgment.',
                        'A simulation cannot establish original district and caravan status without reviewed sources.']}}
binding = {
    'cell_id': cell_id, 'actor': actor, 'status': 'draft',
    'established_contexts': ['The cell states outside_business_district and follow with another vehicle; exact highway designation and caravan membership require source review.'],
    'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}], 'context_refs': [],
    'fixed_parameters': [],
    'variable_parameters': [{**item, 'used_by_laws': [law_id]} for item in template['parameter_refs']]}
rules = json.loads((stages.ROOT / 'data/canonical_parameter_aliases.json').read_text())
request = {'cell': assignment['cell'], 'actor': actor}
stages.validate('relevance_batch', relevance, {'request': request, 'law_records': {law_id: law}, 'dependencies': []})
stages.validate('relevance', relevance, {'request': request, 'law_records': {law_id: law}, 'dependencies': []})
stages.validate('template', template, {'request': {'law_id': law_id, 'actor': actor}, 'law_record': law,
                                       'canonical_parameter_rules': rules, 'dependencies': []})
stages.validate('judgment_observables', judgment,
                {'request': {'template_id': template_id, 'phrase': phrase, 'note': note}, 'dependencies': []})
stages.validate('bindings', binding,
                {'request': {**request, 'template_ids': [template_id]},
                 'canonical_parameter_rules': rules, 'dependencies': [template]})
for name, artifact in (('relevance', relevance), ('template', template),
                       ('judgment-observables', judgment), ('bindings', binding)):
    (PACKAGE / 'proposals' / (name + '.json')).write_text(json.dumps(artifact, indent=2) + '\n')

def assignments(gap, route):
    values = {'outside_business_district': True, 'caravan_membership': True,
              'caravan_body_gap': None, 'entrant_gap_occupancy': None,
              'member_contact': None, 'entrant_route_target': route,
              'caravan_spacing_target': gap}
    return {item['name']: {'kind': item['kind'], 'value': values[item['name']]}
            for item in binding['variable_parameters']}


cases = []
for suffix, gap, route in (('entrant_can_occupy_gap', 10, 'enter_selected_gap'),
                           ('entrant_cannot_occupy_gap', 3, 'approach_selected_gap')):
    construction = json.loads((PACKAGE / 'cases' / (suffix + '-construction.json')).read_text())
    cases.append({
        'case_id': aid + '__' + suffix, 'target_law_id': law_id,
        'target_type': 'boundary_probe', 'rationale': 'Source-backed physical gap occupancy contrast; legal sufficiency remains unresolved.',
        'variable_assignments': assignments(gap, route),
        'unresolved_judgment_calls': [phrase],
        'recording_description': construction['recording_description'],
        'paired_probe_id': 'caravan_gap_occupancy',
        'deliberate_differences': ['entrant_route_target', 'caravan_spacing_target'],
        'probe': {'primary_variable': 'caravan_spacing_target',
                  'comparison_or_standard': 'physical body-gap and occupancy contrast, not a statutory threshold',
                  'target_value_or_branch': gap}})
baseline = {
    'case_id': aid + '__baseline_non_caravan', 'target_law_id': None,
    'target_type': 'baseline', 'rationale': 'Isolate caravan activation by removing reviewed membership.',
    'variable_assignments': assignments(10, 'pass_without_entry'),
    'unresolved_judgment_calls': [],
    'recording_description': cases[0]['recording_description']}
baseline['variable_assignments']['caravan_membership']['value'] = False
cases_proposal = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
                  'cases': [baseline] + cases,
                  'sweep_specs': [{
                      'sweep_id': 'caravan_spacing_judgment', 'target_law_id': law_id,
                      'judgment_refs': [{'phrase': phrase, 'note': note}],
                      'status': 'incomplete',
                      'rationale': 'Physical spacing and combination occupancy must be sampled without choosing a legal cutoff.',
                      'missing_inputs': ['A supported Native controller for independently varying member spacing while preserving a reviewed caravan route and all original bodies.',
                                         'A physical towing/combination participant and feasible range/spacing evidence for its entry.']}]}
observed_template = deepcopy(template)
observed_template['structure']['judgment_calls_needed'][0]['observable_requirements'] = judgment['observable_requirements']
stages.validate('cases', cases_proposal,
                {'request': request, 'dependencies': [binding], 'templates': [observed_template],
                 'canonical_parameter_rules': rules, 'judgment_completion_policy': {}})
(PACKAGE / 'proposals/cases.json').write_text(json.dumps(cases_proposal, indent=2) + '\n')
def reference(name):
    path = PACKAGE / 'proposals' / (name + '.json')
    return {'path': 'proposals/' + path.name,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

index = {'format': 'worker-semantic-delivery', 'assignment_id': aid,
         'stages': {'relevance_batch': reference('relevance'),
                    'relevance': reference('relevance'),
                    'template': reference('template'),
                    'judgment_observables': [reference('judgment-observables')],
                    'bindings': reference('bindings'), 'cases': reference('cases')}}
(PACKAGE / 'proposals/semantic-index.json').write_text(json.dumps(index, indent=2) + '\n')
print('Validated five canonical stages with one explicitly incomplete judgment sweep')
