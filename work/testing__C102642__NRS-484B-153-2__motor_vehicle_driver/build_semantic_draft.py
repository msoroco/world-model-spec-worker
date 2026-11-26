"""Author source-grounded draft stages for the five original door alternatives."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
LAW = 'NRS-484B-153-2'
ACTOR = 'motor_vehicle_driver'
CELL = 'C102642'
TEMPLATE = LAW + '@' + ACTOR
TEXT = 'A person shall not open the door of or board or alight from the side of a vehicle which is closest to passing traffic in such a manner as to interfere with moving vehicular traffic.'
PHRASE = 'in such a manner as to interfere with moving vehicular traffic'
NOTE = 'Interference is a legal judgment; retain original act, door/body clearance, movement and response.'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    folder = HERE / 'proposals'
    relevance = {'status': 'draft', 'cell_id': CELL, 'actor': ACTOR,
                 'relevant_laws': [{'law_id': LAW, 'quote': TEXT, 'applies_to': [ACTOR],
                                    'confidence': 'low',
                                    'relevance_type': 'selected driver door/boarding/alighting act',
                                    'notes': 'Original hill-crest site, action and moving traffic need independent capture.'}],
                 'borderline_excluded': []}
    params = [
        {'name': 'selected_act', 'kind': 'controller', 'range_or_domain': 'open, board or alight'},
        {'name': 'side_relation', 'kind': 'world_setup', 'range_or_domain': 'near or far relative to passing path'},
        {'name': 'clearance_variant', 'kind': 'controller', 'range_or_domain': 'overlap or clear physical target; measure original body gap'},
        {'name': 'engineering_clearance_m', 'kind': 'controller', 'range_or_domain': '0.25 to 1.25 m engineering requests; source-gated feasibility and original measurement'},
        {'name': 'door_body_clearance_m', 'kind': 'controller', 'range_or_domain': 'original measured same-frame polygon gap; never a requested legal threshold'},
        {'name': 'hill_crest_loading_site', 'kind': 'world_setup', 'range_or_domain': 'source-reviewed C102642 loading location'},
        {'name': 'capture_profile', 'kind': 'world_setup', 'range_or_domain': 'four original RGB views, 20 Hz, 900 frames'}]
    template = {'status': 'draft', 'law_id': LAW, 'actor': ACTOR, 'template_id': TEMPLATE,
                'quote': TEXT,
                'structure': {'activation': {'condition': 'Observed selected person opens, boards or alights on the side closest to passing traffic while other traffic moves.', 'numeric_conditions': []},
                              'obligation': {'type': 'must_not', 'description': 'Do not perform the specified act in a manner that interferes with moving vehicular traffic.', 'numeric_conditions': []},
                              'exceptions': [],
                              'timing': {'description': 'Join original driver act and moving traffic in the same Native frames.', 'numeric_conditions': []},
                              'judgment_calls_needed': [{'phrase': PHRASE, 'note': NOTE}]},
                'parameter_refs': params}
    need = {'name': 'original_interaction', 'unit': 'structured',
            'description': 'Frame-joined original act, near/far side, door/body envelopes, moving traffic and response.'}
    judgment = {'status': 'draft', 'template_id': TEMPLATE, 'phrase': PHRASE, 'note': NOTE,
                'observable_requirements': {'observables': [need],
                                            'context_inputs': [{'name': 'hill_crest_loading_site', 'unit': 'structured',
                                                                'description': 'Original surveyed grade and loading governance.'}],
                                            'sweep_dimensions': [{'name': 'door_body_clearance_m', 'unit': 'm',
                                                                  'description': 'Physical coverage requests; original Native gap and legal interference remain separate'}], 'landmarks': [],
                                            'recording_needs': [need],
                                            'limitations': ['Measured proximity and vehicle response cannot independently define statutory interference.']}}
    bindings = {'status': 'draft', 'cell_id': CELL, 'actor': ACTOR,
                'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
                'context_refs': [], 'established_contexts': ['Frozen hill-crest loading cell; original site remains source-gated'],
                'fixed_parameters': [{'name': 'assigned_cell', 'value': CELL,
                                      'rationale': 'Frozen catalog identity, not a reviewed Native site'}],
                'variable_parameters': [dict(p, used_by_laws=[LAW]) for p in params]}
    draft = json.loads((HERE / 'execution-manifest.draft.json').read_text())
    vars_for = lambda kind: {
        'selected_act': {'kind': 'controller', 'value': 'board' if kind == 'board_near' else 'alight' if kind == 'alight_near' else 'open'},
        'side_relation': {'kind': 'world_setup', 'value': 'far' if kind == 'open_far_side' else 'near'},
        'clearance_variant': {'kind': 'controller', 'value': 'clear' if kind == 'open_near_clear' else 'overlap'},
        'engineering_clearance_m': {'kind': 'controller', 'value': None},
        'door_body_clearance_m': {'kind': 'controller', 'value': None},
        'hill_crest_loading_site': {'kind': 'world_setup', 'value': 'source-reviewed C102642 loading location'},
        'capture_profile': {'kind': 'world_setup', 'value': 'four original RGB views, 20 Hz, 900 frames'}}
    description = json.loads((HERE / draft['cases'][0]['construction']).read_text())['recording_description']
    rows = [{'case_id': AID + '__semantic_baseline', 'target_law_id': None,
             'target_type': 'baseline', 'rationale': 'Shared surveyed-site reference; no separate recording.',
             'variable_assignments': vars_for('open_near_overlap'),
             'recording_description': description, 'unresolved_judgment_calls': [PHRASE]}]
    for item in draft['cases']:
        case_id = item['case_id']; kind = case_id.removeprefix(AID + '__')
        if kind.startswith('door_interference_physical_range-'):
            continue
        primary = ('side_relation' if kind == 'open_far_side' else
                   'selected_act' if kind in ('board_near', 'alight_near') else 'clearance_variant')
        rows.append({'case_id': case_id, 'target_law_id': LAW, 'target_type': 'boundary_probe',
                     'paired_probe_id': 'door_action_set',
                     'deliberate_differences': ['selected_act', 'side_relation', 'clearance_variant'],
                     'probe': {'primary_variable': primary, 'comparison_or_standard': 'original controlled door action',
                               'target_value_or_branch': kind},
                     'rationale': 'Original source-gated action and passing-traffic probe: ' + kind,
                     'variable_assignments': vars_for(kind), 'recording_description': description,
                     'unresolved_judgment_calls': [PHRASE]})
    sweep_description = json.loads((HERE / draft['cases'][-1]['construction']).read_text())['recording_description']
    sweep_assignments = vars_for('open_near_overlap')
    sweep_assignments['clearance_variant'] = {'kind': 'controller', 'value': 'source-gated measured clearance request'}
    cases = {'status': 'draft', 'cell_id': CELL, 'actor': ACTOR, 'cases': rows,
             'sweep_specs': [{'sweep_id': AID + '__door_interference_physical_range',
                              'target_law_id': LAW,
                              'judgment_refs': [{'phrase': PHRASE, 'note': NOTE}],
                              'status': 'complete', 'mode': 'one_dimensional',
                              'rationale': 'Three source-gated physical engineering requests with original measured door/body gap; no statutory interference cutoff or verdict.',
                              'landmarks': [], 'recording_description': sweep_description,
                              'variable_assignments': sweep_assignments,
                              'axes': [{'variable': 'engineering_clearance_m',
                                        'observable': 'door_body_clearance_m', 'unit': 'm',
                                        'min': 0.25, 'max': 1.25, 'spacing': 0.5,
                                        'range_rationale': 'Engineering physical coverage candidates; reviewed route source must independently establish feasibility before original capture.',
                                        'spacing_rationale': 'Endpoint and midpoint coverage at one surveyed site; no legal boundary.',
                                        'feasibility_evidence': 'site_contract.py requires a byte-hashed original passing route and surveyed feasible clearance interval before CARLA mutation.',
                                        'measurement': {'method': 'same-frame original door and moving-body polygon distance',
                                                        'time_window': 'minimum-gap original act and moving-traffic overlap frame',
                                                        'statistic': 'min'}}]}]}
    from sys import path
    repo = HERE.parents[1]
    path.insert(0, str(repo / 'runtime/scenario_pipeline'))
    from batch_pipeline.sweeps import expand_sweeps
    expand_sweeps(cases, templates=[template], bindings=bindings)
    refs = {'relevance_batch': write(folder / 'relevance_batch.json', relevance),
            'relevance': write(folder / 'relevance.json', relevance),
            'template': write(folder / 'template.json', template),
            'judgment_observables': [write(folder / 'judgment-1.json', judgment)],
            'bindings': write(folder / 'bindings.json', bindings),
            'cases': write(folder / 'cases.json', cases)}
    write(folder / 'semantic-index.json', {'format': 'worker-semantic-delivery',
                                           'assignment_id': AID, 'stages': refs})
    print('wrote six draft semantic stages and source-hashed index')


if __name__ == '__main__':
    build()
