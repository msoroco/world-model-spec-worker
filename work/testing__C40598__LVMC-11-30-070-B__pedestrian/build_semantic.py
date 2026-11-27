"""Author canonical draft semantic stages for the exact C40598 law."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE / 'proposals'
LAW = 'LVMC-11-30-070-B'
ACTOR = 'pedestrian'
TEMPLATE = LAW + '@' + ACTOR
NOTE = ('Business-district frontage and marked/unmarked crosswalk status require '
        'independently reviewed original sources; no worker legal cutoff or verdict.')


def write(name: str, value: dict) -> dict:
    path = P / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def build() -> dict:
    plan = json.loads((HERE / 'case-plan.json').read_text())
    quote = plan['law_text']
    common = {'status': 'draft', 'cell_id': 'C40598', 'actor': ACTOR}
    relevance = dict(common, relevant_laws=[{'law_id': LAW, 'quote': quote,
        'applies_to': [ACTOR], 'confidence': 'low', 'relevance_type': 'specific_match',
        'notes': 'Complete afoot crossing, original business district and both crosswalk categories require review.'}],
        borderline_excluded=[])
    relevance_ref = write('relevance.json', relevance)
    batch_ref = write('relevance_batch.json', relevance)
    variables = (('crosswalk_category', 'marked, unmarked, outside both'),
                 ('district_frontage_review', 'two independently sourced frontage alternatives'))
    template_ref = write('template.json', {'status': 'draft', 'law_id': LAW,
        'actor': ACTOR, 'template_id': TEMPLATE, 'quote': quote,
        'parameter_refs': [{'name': name, 'kind': 'world_setup', 'range_or_domain': domain}
            for name, domain in variables],
        'structure': {'activation': {'condition': 'Afoot pedestrian completes a roadway crossing in a source-reviewed business district.',
            'numeric_conditions': []},
            'obligation': {'type': 'must', 'description': quote,
                'numeric_conditions': []},
            'exceptions': [{'source_clause': 'other than in a marked crosswalk or within an unmarked crosswalk',
                'description': 'Marked crosswalk or unmarked crosswalk is the stated permitted location alternative.',
                'numeric_conditions': []}],
            'timing': {'description': 'Observe original road entry, full-body route and opposite-curb exit at 20 Hz.',
                'numeric_conditions': []},
            'judgment_calls_needed': [{'phrase': 'business district', 'note': NOTE}]}})
    judgment_ref = write('judgment-1.json', {'status': 'draft', 'template_id': TEMPLATE,
        'phrase': 'business district', 'note': NOTE,
        'observable_requirements': {'observables': [
            {'name': 'district_frontage', 'unit': 'ft',
             'description': 'Original relevant 600-foot highway span, building uses and occupied frontage on both statutory alternatives.'},
            {'name': 'crosswalk_geometry', 'unit': 'state',
             'description': 'Original marked and all potentially applicable unmarked intersection crosswalk polygons and full-body overlap.'},
            {'name': 'pedestrian_crossing', 'unit': 'state',
             'description': 'Original start, roadway, complete crossing and opposite-curb exit history.'}],
            'context_inputs': [{'name': 'reviewed_business_district_site', 'unit': 'source',
                'description': 'Source-hashed roadway, public access, jurisdiction, controls, frontage and crosswalk review.'}],
            'recording_needs': [{'name': name, 'unit': unit, 'description': desc}
                for name, unit, desc in (
                    ('district_frontage', 'ft', 'Original 600-foot business/industrial building frontage.'),
                    ('crosswalk_geometry', 'state', 'Both original crosswalk categories and pedestrian body.'),
                    ('roadway_jurisdiction', 'state', 'Original roadway, shoulder, public access and municipal limits.'),
                    ('pedestrian_crossing', 'state', 'Original complete afoot roadway crossing.'),
                    ('governing_controls', 'state', 'Original governing signs and signals.'))],
            'sweep_dimensions': [], 'landmarks': [],
            'limitations': ['Actual district qualification and Native pedestrian/crosswalk realization remain under review.']}})
    bindings_ref = write('bindings.json', dict(common,
        law_refs=[{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        context_refs=[],
        established_contexts=['Frozen C40598 business-district crossing cell; original source qualification pending.'],
        fixed_parameters=[{'name': 'assigned_cell', 'value': 'C40598',
            'rationale': 'Frozen catalog identity, not physical proof.'}],
        variable_parameters=[{'name': name, 'kind': 'world_setup',
            'range_or_domain': domain, 'used_by_laws': [LAW]} for name, domain in variables]))
    baseline_description = json.loads((HERE / 'cases/marked_crosswalk/construction.json').read_text())['recording_description']
    cases = [{'case_id': HERE.name + '__baseline', 'target_law_id': None,
        'target_type': 'baseline', 'rationale': 'Shared reviewed district and marked crossing reference.',
        'variable_assignments': {name: {'kind': 'world_setup', 'value': value}
            for name, value in (('crosswalk_category', 'marked'),
                ('district_frontage_review', 'frontage_alternative_1'))},
        'recording_description': baseline_description,
        'unresolved_judgment_calls': ['business district']}]
    for case in plan['cases']:
        short = case['case_id'].split('__')[-1]
        construction = json.loads((HERE / 'cases' / short / 'construction.json').read_text())
        values = {name: case[name] for name in ('crosswalk_category', 'district_frontage_review')}
        cases.append({'case_id': case['case_id'], 'target_law_id': LAW,
            'target_type': 'judgment_sweep',
            'rationale': 'Controlled marked/unmarked/outside crossing and reviewed frontage alternative.',
            'variable_assignments': {name: {'kind': 'world_setup', 'value': value}
                                     for name, value in values.items()},
            'paired_probe_id': 'source-gated-business-district-crossing',
            'deliberate_differences': list(values),
            'unresolved_judgment_calls': ['business district'],
            'recording_description': construction['recording_description'],
            'probe': {'primary_variable': 'crosswalk_category',
                'comparison_or_standard': 'same reviewed roadway, 20 Hz duration and four-camera policy',
                'target_value_or_branch': values}})
    sweep = {'sweep_id': 'source-gated-business-district-crossing',
        'target_law_id': LAW, 'judgment_refs': [{'phrase': 'business district', 'note': NOTE}],
        'status': 'incomplete',
        'rationale': 'Original frontage and crosswalk classification are source judgments, not worker numeric legal cutoffs.',
        'missing_inputs': ['independently reviewed 600-foot highway span and both frontage alternatives',
            'original marked and all applicable unmarked crosswalk geometry',
            'complete full-body pedestrian crossing and governing controls']}
    write('pending-source-judgment-sweep.json', sweep)
    cases_ref = write('cases.json', dict(common, cases=cases,
        sweep_specs=[sweep], sweeps_expanded=True,
        sweep_expansion_scope='Four controlled original-source crossing probes; legal judgment unresolved.'))
    index = {'format': 'worker-semantic-delivery', 'assignment_id': HERE.name,
        'stages': {'relevance_batch': batch_ref, 'relevance': relevance_ref,
            'template': template_ref, 'judgment_observables': [judgment_ref],
            'bindings': bindings_ref, 'cases': cases_ref}}
    write('semantic-index.json', index)
    return index


if __name__ == '__main__':
    build()
    print('four exact business-district semantic proposals authored')
