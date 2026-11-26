"""Author exact WALK permission and separate driver-duty semantic proposals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE / 'proposals'
LAW = 'NRS-484B-283-1d1'
ACTOR = 'pedestrian'
TEMPLATE = LAW + '@' + ACTOR


def write(name: str, value: dict) -> dict:
    path = P / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def build() -> dict:
    plan = json.loads((HERE / 'case-plan.json').read_text())
    quote = plan['law_text']
    common = {'status': 'draft', 'cell_id': 'C150911', 'actor': ACTOR}
    relevance = dict(common, relevant_laws=[{'law_id': LAW, 'quote': quote,
        'applies_to': [ACTOR], 'confidence': 'low', 'relevance_type': 'specific_match',
        'notes': 'Original official WALK signal, facing crossing, driver duty and listed exception contexts require review.'}],
        borderline_excluded=[])
    relevance_ref = write('relevance.json', relevance)
    batch_ref = write('relevance_batch.json', relevance)
    template_ref = write('template.json', {'status': 'draft', 'law_id': LAW,
        'actor': ACTOR, 'template_id': TEMPLATE, 'quote': quote,
        'parameter_refs': [{'name': name, 'kind': 'world_setup', 'range_or_domain': domain}
            for name, domain in (('signal_at_entry', 'walk or wait'),
                ('pedestrian_facing_signal', 'true or false'),
                ('driver_yield', 'true or false'))],
        'structure': {'activation': {'condition': 'An official facing pedestrian WALK indication is illuminated at first crosswalk entry.',
            'numeric_conditions': []},
            'obligation': {'type': 'must', 'description': quote,
                'numeric_conditions': []},
            'exceptions': [],
            'timing': {'description': 'Observe original same-frame signal, facing, entry and vehicle trajectory at 20 Hz.',
                'numeric_conditions': []},
            'judgment_calls_needed': [{'phrase': 'right-of-way',
                'note': 'Pedestrian permission and the vehicle-driver duty are separate; no legal verdict is inferred from a command.'}]}})
    judgment_ref = write('judgment-1.json', {'status': 'draft', 'template_id': TEMPLATE,
        'phrase': 'right-of-way',
        'note': 'Pedestrian permission and the vehicle-driver duty are separate; no legal verdict is inferred from a command.',
        'observable_requirements': {'observables': [
            {'name': 'walk_signal_state', 'unit': 'indication',
             'description': 'Official same-frame pedestrian signal readback at first entry.'},
            {'name': 'pedestrian_crosswalk_motion', 'unit': 'state',
             'description': 'Original facing, direction and crosswalk entry.'},
            {'name': 'driver_yield_trajectory', 'unit': 'state',
             'description': 'Identified vehicle approach and yielded trajectory.'}],
            'context_inputs': [{'name': 'reviewed_walk_site', 'unit': 'source',
                'description': 'Source-hashed crosswalk, signal authority, routes and listed exceptions.'}],
            'recording_needs': [{'name': name, 'unit': unit,
                'description': description} for name, unit, description in (
                    ('walk_signal_state', 'indication', 'Original WALK/WAIT indication at 20 Hz.'),
                    ('pedestrian_crosswalk_motion', 'state', 'Original facing, direction and entry at 20 Hz.'),
                    ('driver_yield_trajectory', 'state', 'Distinct original vehicle yielding readback at 20 Hz.'),
                    ('exception_context', 'inventory', 'Original introductory exception context at 20 Hz.'))],
            'sweep_dimensions': [], 'landmarks': [],
            'limitations': ['Original signal pixels, physical interaction and statutory exceptions remain under review.']}})
    bindings_ref = write('bindings.json', dict(common,
        law_refs=[{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        context_refs=[],
        established_contexts=['Frozen C150911 one-way-road crosswalk identity; original Native qualification pending.'],
        fixed_parameters=[{'name': 'assigned_cell', 'value': 'C150911',
            'rationale': 'Frozen catalog identity, not physical proof.'}],
        variable_parameters=[{'name': name, 'kind': 'world_setup',
            'range_or_domain': domain, 'used_by_laws': [LAW]}
            for name, domain in (('signal_at_entry', 'walk or wait'),
                ('pedestrian_facing_signal', 'true or false'),
                ('driver_yield', 'true or false'))]))
    cases = []
    baseline_description = json.loads((HERE / 'cases/walk_facing_yield/construction.json').read_text())['recording_description']
    cases.append({'case_id': HERE.name + '__baseline', 'target_law_id': None,
        'target_type': 'baseline', 'rationale': 'Shared original crosswalk and signal reference.',
        'variable_assignments': {name: {'kind': 'world_setup', 'value': value}
            for name, value in (('signal_at_entry', 'walk'),
                ('pedestrian_facing_signal', True), ('driver_yield', True))},
        'recording_description': baseline_description,
        'unresolved_judgment_calls': ['right-of-way']})
    for case in plan['cases']:
        short = case['case_id'].split('__')[-1]
        construction = json.loads((HERE / 'cases' / short / 'construction.json').read_text())
        values = {'signal_at_entry': case['requested_signal_at_entry'],
            'pedestrian_facing_signal': case['requested_pedestrian_facing_signal'],
            'driver_yield': case['requested_driver_yield']}
        cases.append({'case_id': case['case_id'], 'target_law_id': LAW,
            'target_type': 'judgment_sweep',
            'rationale': 'Controlled original WALK, facing and separate driver-yield observation.',
            'variable_assignments': {name: {'kind': 'world_setup', 'value': value}
                                     for name, value in values.items()},
            'paired_probe_id': 'source-gated-walk-facing-driver-duty',
            'deliberate_differences': list(values),
            'unresolved_judgment_calls': ['right-of-way'],
            'recording_description': construction['recording_description'],
            'probe': {'primary_variable': 'signal_at_entry',
                'comparison_or_standard': 'same reviewed crosswalk, actor identities and four-camera policy',
                'target_value_or_branch': values}})
    sweep = {'sweep_id': 'source-gated-driver-duty-context',
        'target_law_id': LAW, 'judgment_refs': [{'phrase': 'right-of-way',
            'note': 'Pedestrian permission and the vehicle-driver duty are separate; no legal verdict is inferred from a command.'}],
        'status': 'incomplete', 'rationale': 'Physical yielding and exception contexts are original source measurements, not legal thresholds.',
        'missing_inputs': ['reviewed original official WALK signal and crosswalk',
            'source-bound driver trajectory and four-camera pixels',
            'independent NRS 484B.287, 484B.290 and 484B.350 exception review']}
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
    print('four exact WALK semantic proposals authored')
