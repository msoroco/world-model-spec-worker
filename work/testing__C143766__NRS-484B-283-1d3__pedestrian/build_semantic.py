"""Author draft semantic stages for conditional 1d3 crossing continuation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE / 'proposals'
LAW = 'NRS-484B-283-1d3'
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
    common = {'status': 'draft', 'cell_id': 'C143766', 'actor': ACTOR}
    relevance = dict(common, relevant_laws=[{'law_id': LAW, 'quote': quote,
        'applies_to': [ACTOR], 'confidence': 'low', 'relevance_type': 'specific_match',
        'notes': 'Original facing flashing indication without countdown, prior lawful entry, destination timing and exceptions require independent review.'}],
        borderline_excluded=[])
    relevance_ref = write('relevance.json', relevance)
    batch_ref = write('relevance_batch.json', relevance)
    variables = [('entry_phase', 'Walk or flashing'),
        ('destination', 'curb, sidewalk, provided safety zone or reviewed other safety place'),
        ('arrival_phase', 'flashing or steady'), ('countdown', 'present or absent')]
    template_ref = write('template.json', {'status': 'draft', 'law_id': LAW,
        'actor': ACTOR, 'template_id': TEMPLATE, 'quote': quote,
        'parameter_refs': [{'name': name, 'kind': 'world_setup', 'range_or_domain': domain}
            for name, domain in variables],
        'structure': {'activation': {'condition': 'A facing pedestrian indication flashes without countdown; continuation requires separately established lawful entry under subparagraph (1).',
            'numeric_conditions': []},
            'obligation': {'type': 'must', 'description': quote, 'numeric_conditions': []},
            'exceptions': [],
            'timing': {'description': 'Observe original 20 Hz entry, signal flashing-to-steady transition and arrival at sourced place of safety.',
                'numeric_conditions': []},
            'judgment_calls_needed': [{'phrase': 'lawful prior entry and place of safety',
                'note': 'Walk-phase observation alone does not resolve subparagraph (1), destination legality or introductory exceptions.'}]}})
    judgment_ref = write('judgment-1.json', {'status': 'draft', 'template_id': TEMPLATE,
        'phrase': 'lawful prior entry and place of safety',
        'note': 'Walk-phase observation alone does not resolve subparagraph (1), destination legality or introductory exceptions.',
        'observable_requirements': {'observables': [
            {'name': 'signal_phase', 'unit': 'indication',
             'description': 'Official facing Walk, flashing/no-countdown and steady original readback.'},
            {'name': 'pedestrian_route', 'unit': 'state',
             'description': 'First highway entry and arrival at destination on original frames.'},
            {'name': 'safety_destination', 'unit': 'source',
             'description': 'Reviewed curb, accessible sidewalk, provided safety zone or other place source.'}],
            'context_inputs': [{'name': 'reviewed_crossing_site', 'unit': 'source',
                'description': 'Source-hashed trail, highway, signal, route, destination and exceptions.'}],
            'recording_needs': [{'name': name, 'unit': unit, 'description': description}
                for name, unit, description in (
                    ('signal_phase', 'indication', 'Original facing phase/countdown at 20 Hz.'),
                    ('pedestrian_route', 'state', 'Original entry and destination arrival at 20 Hz.'),
                    ('safety_destination', 'source', 'Original destination status and geometry.'),
                    ('exception_context', 'inventory', 'NRS 484B.287, .290 and .350 context.'))],
            'sweep_dimensions': [], 'landmarks': [],
            'limitations': ['Prior entry legality, physical destination status and exceptions remain independent review questions.']}})
    bindings_ref = write('bindings.json', dict(common,
        law_refs=[{'template_id': TEMPLATE, 'binding_kind': 'direct'}], context_refs=[],
        established_contexts=['Frozen C143766 trail/sidewalk cell identity; original Native site qualification pending.'],
        fixed_parameters=[{'name': 'assigned_cell', 'value': 'C143766',
            'rationale': 'Frozen catalog identity, not physical proof.'}],
        variable_parameters=[{'name': name, 'kind': 'world_setup',
            'range_or_domain': domain, 'used_by_laws': [LAW]} for name, domain in variables]))
    cases = []
    first = plan['cases'][0]
    baseline_description = json.loads((HERE / 'cases' / first['case_id'].split('__')[-1] / 'construction.json').read_text())['recording_description']
    cases.append({'case_id': HERE.name + '__baseline', 'target_law_id': None,
        'target_type': 'baseline', 'rationale': 'Neutral original trail, highway crossing and signal reference.',
        'variable_assignments': {name: {'kind': 'world_setup', 'value': value}
            for name, value in [('entry_phase', 'walk'), ('destination', 'sidewalk'),
                ('arrival_phase', 'flashing'), ('countdown', False)]},
        'recording_description': baseline_description,
        'unresolved_judgment_calls': ['lawful prior entry and place of safety']})
    for case in plan['cases']:
        short = case['case_id'].split('__')[-1]
        construction = json.loads((HERE / 'cases' / short / 'construction.json').read_text())
        values = {name: case[name] for name in ('entry_phase', 'destination', 'arrival_phase', 'countdown')}
        cases.append({'case_id': case['case_id'], 'target_law_id': LAW,
            'target_type': 'judgment_sweep',
            'rationale': 'Controlled original signal, entry, arrival and safety-destination physical observations.',
            'variable_assignments': {name: {'kind': 'world_setup', 'value': value}
                for name, value in values.items()},
            'paired_probe_id': 'source-gated-flashing-continuation',
            'deliberate_differences': list(values),
            'unresolved_judgment_calls': ['lawful prior entry and place of safety'],
            'recording_description': construction['recording_description'],
            'probe': {'primary_variable': 'entry_phase',
                'comparison_or_standard': 'same reviewed trail/crossing and four-camera policy',
                'target_value_or_branch': values}})
    sweep = {'sweep_id': 'source-gated-continuation-context', 'target_law_id': LAW,
        'judgment_refs': [{'phrase': 'lawful prior entry and place of safety',
            'note': 'Walk-phase observation alone does not resolve subparagraph (1), destination legality or introductory exceptions.'}],
        'status': 'incomplete',
        'rationale': 'Lawful prior entry and place-of-safety classification require original source review; no numeric legal cutoff is invented.',
        'missing_inputs': ['reviewed original official pedestrian display and route',
            'source-bound destination classification and four-camera pixels',
            'independent subparagraph (1) and NRS 484B.287, .290 and .350 review']}
    write('pending-source-judgment-sweep.json', sweep)
    cases_ref = write('cases.json', dict(common, cases=cases, sweep_specs=[sweep],
        sweeps_expanded=True,
        sweep_expansion_scope='Seven controlled source-deferred physical probes; legal qualification unresolved.'))
    index = {'format': 'worker-semantic-delivery', 'assignment_id': HERE.name,
        'stages': {'relevance_batch': batch_ref, 'relevance': relevance_ref,
            'template': template_ref, 'judgment_observables': [judgment_ref],
            'bindings': bindings_ref, 'cases': cases_ref}}
    write('semantic-index.json', index)
    return index


if __name__ == '__main__':
    build()
    print('seven exact 1d3 semantic proposals authored')
