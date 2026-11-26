"""Draft source-gated canonical stages without legal labels or invented bounds."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
PLAN = json.loads((ROOT / 'case-plan.json').read_text())
PROPOSALS = ROOT / 'proposals'
LAW = ASSIGNMENT['law']
IDENT = LAW['id'] + '@' + ASSIGNMENT['actor']


def write(name: str, value: dict) -> dict:
    path = PROPOSALS / name
    raw = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
    path.write_bytes(raw)
    return {'path': str(path.relative_to(ROOT)),
            'sha256': hashlib.sha256(raw).hexdigest()}


def requirement(phrase: str, channel: str, context: bool,
                dimension: str) -> dict:
    recorded = {'name': channel, 'unit': 'source record',
                'description': 'Original source-bound observation for ' + phrase}
    return {'template_id': IDENT, 'phrase': phrase, 'note': '', 'status': 'draft',
            'observable_requirements': {
                'observables': [recorded],
                'context_inputs': [{'name': 'reviewed_fire_lane_packet', 'unit': 'source record',
                                    'description': 'Reviewed designation, posted extent and source identity'}]
                if context else [],
                'sweep_dimensions': [{'name': dimension, 'unit': 'm',
                                      'description': 'Physical coverage target; original geometry measured separately'}],
                'landmarks': [], 'recording_needs': [recorded],
                'limitations': ['Original City source and physical observation are required; '
                                'no legal boundary is supplied.']}}


def build() -> dict:
    quote = LAW['text']
    relevance = {'cell_id': PLAN['cell_id'], 'actor': PLAN['actor'], 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW['id'], 'quote': quote,
                                    'applies_to': [PLAN['actor']],
                                    'relevance_type': 'assigned curb-adjacent posted fire lane',
                                    'confidence': 'medium',
                                    'notes': 'Location-specific City designation and posting source pending.'}],
                 'borderline_excluded': []}
    refs = {'relevance_batch': write('relevance_batch.json', relevance),
            'relevance': write('relevance.json', relevance)}
    phrases = [
        'necessary to avoid conflict with other traffic',
        "designated and posted as a fire lane pursuant to the City's Fire Code",
    ]
    parameters = [
        {'name': name, 'kind': kind, 'range_or_domain': domain}
        for name, kind, domain in (
            ('activity', 'controller', 'requested stop, stand or park activity; original observed separately'),
            ('attended', 'world_setup', 'driver attendance source and original observed state'),
            ('property_kind', 'world_setup', 'public or private reviewed parcel source'),
            ('target_region', 'controller', 'inside or outside reviewed posted extent; original body observed'),
            ('exception', 'world_setup', 'source-gated traffic, police or device direction kind'),
            ('conflict_gap_m', 'controller', 'requested actor separation in metres; not a legal cutoff'),
            ('posted_offset_m', 'controller', 'requested body-centre offset from reviewed posted end in metres'),
        )]
    template = {'template_id': IDENT, 'law_id': LAW['id'], 'actor': PLAN['actor'],
                'quote': quote,
                'structure': {'law_id': LAW['id'],
                    'activation': {'condition': 'Vehicle at a curb-adjacent City-designated and posted fire lane.',
                                   'numeric_conditions': []},
                    'obligation': {'description': 'No stopping, standing or parking in that place.',
                                   'type': 'must_not', 'numeric_conditions': []},
                    'exceptions': [
                        {'trigger': 'necessary to avoid conflict with other traffic in compliance with law',
                         'effect': 'introductory exception to the prohibition',
                         'replacement_obligation': 'Comply with law',
                         'source_clause': 'necessary to avoid conflict with other traffic in compliance with law'},
                        {'trigger': 'directions of a police officer',
                         'effect': 'introductory exception to the prohibition',
                         'replacement_obligation': 'Follow the direction',
                         'source_clause': 'directions of a police officer'},
                        {'trigger': 'directions of a traffic control device',
                         'effect': 'introductory exception to the prohibition',
                         'replacement_obligation': 'Follow the direction',
                         'source_clause': 'or a traffic control device'},
                    ],
                    'timing': {'description': 'While the vehicle stops, stands or parks in the qualifying place.',
                               'numeric_conditions': []},
                    'judgment_calls_needed': [{'phrase': p, 'note': ''} for p in phrases]},
                'parameter_refs': parameters}
    refs['template'] = write('template.json', template)
    refs['judgment_observables'] = [
        write('judgment-conflict.json', requirement(phrases[0], 'necessity_exceptions', False, 'conflict_gap_m')),
        write('judgment-designation.json', requirement(phrases[1], 'designation_and_posting', True, 'posted_offset_m')),
    ]
    binding = {'cell_id': PLAN['cell_id'], 'actor': PLAN['actor'], 'status': 'draft',
               'established_contexts': ['one-way curb approach; original City designation and posted extent pending'],
               'law_refs': [{'template_id': IDENT, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [{**row, 'used_by_laws': [LAW['id']]} for row in parameters]}
    refs['bindings'] = write('bindings.json', binding)
    cases = json.loads((PROPOSALS / 'cases.json').read_text())
    cases['cases'] = [case for case in cases['cases']
                      if case.get('target_type') != 'judgment_sweep']
    cases.pop('sweeps_expanded', None)
    pairs = {
        'public_park_attended': 'attendance_public',
        'public_park_unattended': 'attendance_public',
        'private_park_attended': 'attendance_private',
        'private_park_unattended': 'attendance_private',
        'public_stop': 'traffic_exception',
        'traffic_conflict_exception': 'traffic_exception',
        'police_direction_exception': 'direction_exception',
        'device_direction_exception': 'direction_exception',
    }
    for case in cases['cases']:
        if case['target_type'] == 'baseline':
            continue
        suffix = case['case_id'].removeprefix(ROOT.name + '__')
        case['paired_probe_id'] = pairs.get(suffix, suffix + '_source_standard')
    base = cases['cases'][1]['variable_assignments']
    recording = cases['cases'][1]['recording_description']
    def spec(suffix, phrase, variable, low, high, spacing, method, assignments):
        description = json.loads(json.dumps(recording))
        description['channels'].append({'name': variable, 'unit': 'm',
            'sampling_rate_hz': 20, 'method': method,
            'time_window': 'full original 45-second episode',
            'reference_frame': 'reviewed original site and same-frame actor bodies',
            'uncertainty': 'requested setpoint may differ from measured original motion'})
        return {'sweep_id': ROOT.name + '__' + suffix, 'target_law_id': LAW['id'],
            'judgment_refs': [{'phrase': phrase, 'note': ''}], 'status': 'complete',
            'mode': 'one_dimensional', 'axes': [{'variable': variable,
                'observable': variable, 'unit': 'm', 'min': low, 'max': high,
                'spacing': spacing, 'measurement': {'method': method,
                    'time_window': 'full original 45-second episode', 'statistic': 'min'},
                'range_rationale': 'Three controlled engineering requests around an observed physical context; no legal boundary.',
                'spacing_rationale': 'Endpoint and midpoint physical coverage at one fixed site; no label targeting.',
                'feasibility_evidence': 'Source-gated judgment_sweeps.py preflight checks reviewed route and site before execution; CPU positive, tamper and missing-source tests.'}],
            'landmarks': [],
            'rationale': 'Freeze physical source-gated requests and measure actual originals; legal judgment unresolved.',
            'variable_assignments': assignments,
            'recording_description': description}
    conflict = json.loads(json.dumps(base))
    conflict['exception'] = {'kind': 'world_setup', 'value': 'lawful_traffic_conflict',
                             'note': 'requires independently reviewed conflict source'}
    conflict['activity'] = {'kind': 'controller', 'value': 'stop', 'note': 'requested activity'}
    designation = json.loads(json.dumps(base))
    designation['exception'] = {'kind': 'world_setup', 'value': 'none', 'note': 'no exception requested'}
    designation['target_region'] = {'kind': 'controller', 'value': 'sweep_offset',
                                    'note': 'numeric posted offset controls the target'}
    cases['sweep_specs'] = [
        spec('conflict_necessity_source_review', phrases[0], 'conflict_gap_m',
             4.0, 12.0, 4.0, 'same-frame original actor body gap', conflict),
        spec('designation_posting_source_review', phrases[1], 'posted_offset_m',
             -2.0, 2.0, 2.0, 'same-frame original body centre minus reviewed posted end', designation),
    ]
    sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
    from batch_pipeline.sweeps import expand_sweeps
    expand_sweeps(cases, [template], binding)
    cases['semantic_status'] = 'source_gated_physical_sweeps_frozen_no_legal_label'
    refs['cases'] = write('cases.json', cases)
    index = {'format': 'worker-semantic-delivery', 'assignment_id': ROOT.name,
             'stages': refs, 'status': 'source_gated_physical_sweeps_frozen_no_legal_label'}
    write('semantic-index.json', index)
    return index


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
