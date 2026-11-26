"""Author exact outside-crosswalk and prohibited-place semantic proposals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE / 'proposals'
LAW = 'LVMC-11-30-060-A'
ACTOR = 'pedestrian'
TEMPLATE = LAW + '@' + ACTOR
NOTE = 'Yield throughout a crossing to all vehicles upon the roadway and the 11.30.070 exception require original source review; no legal verdict follows from a command.'


def write(name: str, value: dict) -> dict:
    path = P / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def build() -> dict:
    plan = json.loads((HERE / 'case-plan.json').read_text())
    quote = plan['law_text']
    common = {'status': 'draft', 'cell_id': 'C228096', 'actor': ACTOR}
    relevance = dict(common, relevant_laws=[{'law_id': LAW, 'quote': quote,
        'applies_to': [ACTOR], 'confidence': 'low', 'relevance_type': 'specific_match',
        'notes': 'Outside both crosswalk categories, all roadway vehicles and 11.30.070 place status require original review.'}],
        borderline_excluded=[])
    relevance_ref = write('relevance.json', relevance)
    batch_ref = write('relevance_batch.json', relevance)
    variables = (('vehicle_on_roadway', 'true or false'),
                 ('pedestrian_yield', 'true or false'),
                 ('prohibited_place_under_11_30_070', 'true or false'))
    template_ref = write('template.json', {'status': 'draft', 'law_id': LAW,
        'actor': ACTOR, 'template_id': TEMPLATE, 'quote': quote,
        'parameter_refs': [{'name': name, 'kind': 'world_setup', 'range_or_domain': domain}
            for name, domain in variables],
        'structure': {'activation': {'condition': 'Pedestrian enters and crosses a roadway outside marked and unmarked intersection crosswalks.',
            'numeric_conditions': []},
            'obligation': {'type': 'must', 'description': quote,
                'numeric_conditions': []},
            'exceptions': [],
            'timing': {'description': 'Observe original roadway entry and full crossing with all roadway vehicles at 20 Hz.',
                'numeric_conditions': []},
            'judgment_calls_needed': [{'phrase': 'right-of-way', 'note': NOTE}]}})
    judgment_ref = write('judgment-1.json', {'status': 'draft', 'template_id': TEMPLATE,
        'phrase': 'right-of-way', 'note': NOTE,
        'observable_requirements': {'observables': [
            {'name': 'pedestrian_roadway_motion', 'unit': 'state',
             'description': 'Original roadway entry and complete pedestrian crossing history.'},
            {'name': 'vehicle_roadway_motion', 'unit': 'state',
             'description': 'All original roadway vehicle identities, positions and movements.'},
            {'name': 'yield_trajectory', 'unit': 'state',
             'description': 'Original pedestrian/vehicle interaction throughout crossing.'}],
            'context_inputs': [{'name': 'reviewed_outside_crosswalk_site', 'unit': 'source',
                'description': 'Source-hashed roadway, both crosswalk categories and 11.30.070 place review.'}],
            'recording_needs': [{'name': name, 'unit': unit, 'description': desc}
                for name, unit, desc in (
                    ('outside_crosswalk_site', 'classification', 'Original crosswalk and prohibited-place classification.'),
                    ('pedestrian_roadway_motion', 'state', 'Original complete pedestrian crossing.'),
                    ('vehicle_roadway_motion', 'state', 'All original roadway vehicles.'),
                    ('yield_trajectory', 'state', 'Original yield interaction throughout crossing.'))],
            'sweep_dimensions': [], 'landmarks': [],
            'limitations': ['Actual crossing, all vehicles and statutory exception remain under review.']}})
    bindings_ref = write('bindings.json', dict(common,
        law_refs=[{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        context_refs=[],
        established_contexts=['Frozen C228096 roadway entry cell; original outside-crosswalk qualification pending.'],
        fixed_parameters=[{'name': 'assigned_cell', 'value': 'C228096',
            'rationale': 'Frozen catalog identity, not physical proof.'}],
        variable_parameters=[{'name': name, 'kind': 'world_setup',
            'range_or_domain': domain, 'used_by_laws': [LAW]} for name, domain in variables]))
    baseline_description = json.loads((HERE / 'cases/yield_with_vehicle/construction.json').read_text())['recording_description']
    cases = [{'case_id': HERE.name + '__baseline', 'target_law_id': None,
        'target_type': 'baseline', 'rationale': 'Shared original roadway and crossing reference.',
        'variable_assignments': {name: {'kind': 'world_setup', 'value': value}
            for name, value in (('vehicle_on_roadway', True),
                ('pedestrian_yield', True), ('prohibited_place_under_11_30_070', False))},
        'recording_description': baseline_description,
        'unresolved_judgment_calls': ['right-of-way']}]
    for case in plan['cases']:
        short = case['case_id'].split('__')[-1]
        construction = json.loads((HERE / 'cases' / short / 'construction.json').read_text())
        values = {'vehicle_on_roadway': case['requested_vehicle_on_roadway'],
            'pedestrian_yield': case['requested_pedestrian_yield'],
            'prohibited_place_under_11_30_070': case['requested_prohibited_place_under_11_30_070']}
        cases.append({'case_id': case['case_id'], 'target_law_id': LAW,
            'target_type': 'judgment_sweep',
            'rationale': 'Controlled original vehicle presence, pedestrian yield and prohibited-place condition.',
            'variable_assignments': {name: {'kind': 'world_setup', 'value': value}
                                     for name, value in values.items()},
            'paired_probe_id': 'source-gated-outside-crosswalk-yield',
            'deliberate_differences': list(values),
            'unresolved_judgment_calls': ['right-of-way'],
            'recording_description': construction['recording_description'],
            'probe': {'primary_variable': 'pedestrian_yield',
                'comparison_or_standard': 'same reviewed roadway, crossing route and four-camera policy',
                'target_value_or_branch': values}})
    sweep = {'sweep_id': 'source-gated-outside-crosswalk-duty',
        'target_law_id': LAW, 'judgment_refs': [{'phrase': 'right-of-way', 'note': NOTE}],
        'status': 'incomplete',
        'rationale': 'Physical yield and prohibited-place applicability are original source judgments, not numeric legal thresholds.',
        'missing_inputs': ['reviewed original marked/unmarked crosswalk and intersection geometry',
            'complete pedestrian and all roadway vehicle trajectories',
            'independent LVMC 11.30.070 prohibited-place source review']}
    write('pending-source-judgment-sweep.json', sweep)
    cases_ref = write('cases.json', dict(common, cases=cases,
        sweep_specs=[sweep], sweeps_expanded=True,
        sweep_expansion_scope='Four controlled original-source physical probes; legal judgment unresolved.'))
    index = {'format': 'worker-semantic-delivery', 'assignment_id': HERE.name,
        'stages': {'relevance_batch': batch_ref, 'relevance': relevance_ref,
            'template': template_ref, 'judgment_observables': [judgment_ref],
            'bindings': bindings_ref, 'cases': cases_ref}}
    write('semantic-index.json', index)
    return index


if __name__ == '__main__':
    build()
    print('four exact outside-crosswalk semantic proposals authored')
