"""Author exact nearest-rail and traffic-necessity semantic proposals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE / 'proposals'
LAW = 'NRS-484B-450-1i'
ACTOR = 'motor_vehicle_driver'
TEMPLATE = LAW + '@' + ACTOR
NOTE = 'Traffic-conflict necessity and law, officer or device direction require independent original source review; nearby traffic alone proves no exception.'


def write(name: str, value: dict) -> dict:
    path = P / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def build() -> dict:
    plan = json.loads((HERE / 'case-plan.json').read_text())
    quote = plan['law_text']
    common = {'status': 'draft', 'cell_id': 'C229435', 'actor': ACTOR}
    relevance = dict(common, relevant_laws=[{'law_id': LAW, 'quote': quote,
        'applies_to': [ACTOR], 'confidence': 'low', 'relevance_type': 'specific_match',
        'notes': 'Nearest railroad rail, full vehicle footprint and four exceptions need original review.'}],
        borderline_excluded=[])
    relevance_ref = write('relevance.json', relevance)
    batch_ref = write('relevance_batch.json', relevance)
    variables = (('nearest_vehicle_to_rail_m', '14.0, 15.24 or 17.0 m'),
                 ('traffic_conflict_necessity', 'absent or unresolved'))
    template_ref = write('template.json', {'status': 'draft', 'law_id': LAW,
        'actor': ACTOR, 'template_id': TEMPLATE, 'quote': quote,
        'parameter_refs': [{'name': name, 'kind': 'world_setup', 'range_or_domain': domain}
            for name, domain in variables],
        'structure': {'activation': {'condition': 'Ego stops, stands or parks near the nearest railroad rail.',
            'numeric_conditions': [{'variable': 'nearest_vehicle_to_rail_m', 'operator': '<', 'value': 15.24, 'unit': 'm'}]},
            'obligation': {'type': 'must_not', 'description': quote,
                'numeric_conditions': []},
            'exceptions': [{'source_clause': 'except when necessary to avoid conflict with other traffic or in compliance with law or the directions of a police officer or official traffic-control device',
                'description': NOTE, 'numeric_conditions': []}],
            'timing': {'description': 'Observe original approach and parked footprint with other vehicle at 20 Hz.',
                'numeric_conditions': []},
            'judgment_calls_needed': [{'phrase': 'necessary to avoid conflict with other traffic', 'note': NOTE}]}})
    judgment_ref = write('judgment-1.json', {'status': 'draft', 'template_id': TEMPLATE,
        'phrase': 'necessary to avoid conflict with other traffic', 'note': NOTE,
        'observable_requirements': {'observables': [
            {'name': 'vehicle_rail_distance', 'unit': 'm', 'description': 'Original complete ego footprint to every nearby rail.'},
            {'name': 'vehicle_parking_action', 'unit': 'state', 'description': 'Original ego approach and parking state.'},
            {'name': 'traffic_and_exceptions', 'unit': 'state', 'description': 'Other vehicle motion and independent exception context.'}],
            'context_inputs': [{'name': 'reviewed_railroad_site', 'unit': 'source',
                'description': 'Carrier, railroad identity, all rails and exception source hashes.'}],
            'recording_needs': [{'name': name, 'unit': unit, 'description': desc}
                for name, unit, desc in (
                    ('railroad_site', 'classification', 'Original railroad and all nearby rails.'),
                    ('vehicle_rail_distance', 'm', 'Complete original footprint distance.'),
                    ('vehicle_parking_action', 'state', 'Original parking action.'),
                    ('traffic_and_exceptions', 'state', 'Other vehicle and four independent exceptions.'))],
            'sweep_dimensions': [], 'landmarks': [],
            'limitations': ['Traffic necessity and legal direction remain source-dependent.']}})
    bindings_ref = write('bindings.json', dict(common,
        law_refs=[{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        context_refs=[],
        established_contexts=['Frozen C229435 rail-adjacent parking cell; original railroad qualification pending.'],
        fixed_parameters=[{'name': 'assigned_cell', 'value': 'C229435',
            'rationale': 'Frozen catalog identity, not physical proof.'}],
        variable_parameters=[{'name': name, 'kind': 'world_setup',
            'range_or_domain': domain, 'used_by_laws': [LAW]} for name, domain in variables]))
    baseline_description = json.loads((HERE / 'cases/inside_no_exception/construction.json').read_text())['recording_description']
    cases = [{'case_id': HERE.name + '__baseline', 'target_law_id': None,
        'target_type': 'baseline', 'rationale': 'Shared reviewed railroad and parking reference.',
        'variable_assignments': {'nearest_vehicle_to_rail_m': {'kind': 'world_setup', 'value': 14.0},
            'traffic_conflict_necessity': {'kind': 'world_setup', 'value': 'absent'}},
        'recording_description': baseline_description,
        'unresolved_judgment_calls': ['necessary to avoid conflict with other traffic']}]
    for case in plan['cases']:
        short = case['case_id'].split('__')[-1]
        construction = json.loads((HERE / 'cases' / short / 'construction.json').read_text())
        values = {'nearest_vehicle_to_rail_m': case['requested_nearest_vehicle_to_rail_m'],
            'traffic_conflict_necessity': case['requested_traffic_conflict_necessity_status']}
        boundary = short != 'inside_other_vehicle_unresolved'
        cases.append({'case_id': case['case_id'], 'target_law_id': LAW,
            'target_type': 'boundary_probe' if boundary else 'judgment_sweep',
            'rationale': 'Controlled original rail distance and separately reviewed traffic necessity.',
            'variable_assignments': {name: {'kind': 'world_setup', 'value': value}
                                     for name, value in values.items()},
            'paired_probe_id': 'source-gated-nearest-rail',
            **({'epsilon_used': {'value': .01, 'unit': 'm',
                'rationale': 'Engineering probe separation; not a legal tolerance.'}} if boundary else {}),
            'deliberate_differences': list(values),
            'unresolved_judgment_calls': ['necessary to avoid conflict with other traffic'],
            'recording_description': construction['recording_description'],
            'probe': {'primary_variable': 'nearest_vehicle_to_rail_m',
                **({'threshold_ref': 'activation.numeric_conditions[0]',
                    'operator': '<', 'unit': 'm', 'test_value': values['nearest_vehicle_to_rail_m']} if boundary else {}),
                'comparison_or_standard': 'same reviewed railroad, parking action, other vehicle and four-camera policy',
                'target_value_or_branch': values}})
    sweep = {'sweep_id': 'source-gated-nearest-rail-duty', 'target_law_id': LAW,
        'judgment_refs': [{'phrase': 'necessary to avoid conflict with other traffic', 'note': NOTE}],
        'status': 'incomplete',
        'rationale': '15.24 m is statutory distance; traffic necessity and other exceptions require original source judgments.',
        'missing_inputs': ['reviewed original carrier and all nearby railroad rails',
            'complete original ego footprint and parked action',
            'independent traffic/law/officer/device exception source review']}
    write('pending-source-judgment-sweep.json', sweep)
    cases_ref = write('cases.json', dict(common, cases=cases,
        sweep_specs=[sweep], sweeps_expanded=True,
        sweep_expansion_scope='Four controlled original-source physical probes; legal exceptions unresolved.'))
    index = {'format': 'worker-semantic-delivery', 'assignment_id': HERE.name,
        'stages': {'relevance_batch': batch_ref, 'relevance': relevance_ref,
            'template': template_ref, 'judgment_observables': [judgment_ref],
            'bindings': bindings_ref, 'cases': cases_ref}}
    write('semantic-index.json', index)
    return index


if __name__ == '__main__':
    build()
    print('four exact railroad semantic proposals authored')
