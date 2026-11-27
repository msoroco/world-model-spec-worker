"""Author exact source-bound semantic proposals and the selected case plan."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name
ASSIGNMENT = json.loads((REPO / 'inputs' / AID / 'assignment.json').read_text())
LAW = ASSIGNMENT['law_id']
ACTOR = ASSIGNMENT['actor']
CELL = ASSIGNMENT['cell_id']
TEXT = ASSIGNMENT['law']['text']
TEMPLATE_ID = LAW + '@' + ACTOR
SOURCE = {'path': 'inputs/' + AID + '/assignment.json',
          'sha256': hashlib.sha256((REPO / 'inputs' / AID / 'assignment.json').read_bytes()).hexdigest(),
          'law': ASSIGNMENT['law']['source']}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf8')


CHANNEL_NAMES = (
    'original_frame', 'native_time_s', 'ego_actor_id', 'other_actor_id',
    'ego_lane_id', 'other_lane_id', 'ego_station_m', 'other_station_m',
    'lateral_arrangement_m', 'longitudinal_relation', 'ego_speed_mps',
    'other_speed_mps', 'same_lane_two_wheeler_count', 'camera_frame_join',
)
RECORDING = {
    'channels': [{
        'name': name, 'unit': 'structured native observation', 'sampling_rate_hz': 20,
        'method': 'source-linked original Native actor and frame readback',
        'time_window': 'full 45-second original episode',
        'reference_frame': 'original CARLA frame and synchronized four-camera frame',
        'uncertainty': 'physical pixels, lane bounds and legal sufficiency require independent review',
    } for name in CHANNEL_NAMES],
    'context_inputs': [{
        'name': name, 'unit': 'source-backed contextual record',
        'method': 'independent original reviewed packet and SHA-256 retained with Native attempt',
    } for name in ('chapter_vehicle_classification', 'driver_identity',
                   'driver_consent_evidence', 'subsection_3_exception_review',
                   'lane_geometry_survey')],
    'limitations': [
        'Driver consent and subsection 3 do not follow from maneuver geometry.',
        'Same-lane occupancy and passing need original actor footprint, time and camera review.',
        'No universal statutory clearance, passing duration or abreast cutoff is defined.',
    ],
}


def main():
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    ids = [c['case_id'] for c in plan['cases']]
    plan['source_observation_mapping'] = {}
    plan['evidence_review'] = {
        'reviewer': 'C229023 CPU construction owner',
        'method': 'Read the exact frozen assignment, witness and empty accepted recording inventory; no accepted recording demonstrates any selected branch.',
        'facts': [],
        'gaps': [{
            'id': 'unverified-law-coverage',
            'requirement': 'Original same-lane pass, alternate-lane control, consent and two-abreast count evidence',
            'source': SOURCE,
            'why_existing_insufficient': 'Frozen accepted recording inventory is empty.',
        }],
    }
    requirements = [
        ('qualifying motorcycle operator and independently classified other vehicle',
         'chapter_vehicle_classification', ids),
        ('same traffic lane and behind-to-ahead overtaking or passing',
         'same_lane_passage', ids[:2]),
        ('driver consent for no more than two motorcycles or mopeds abreast',
         'driver_consent_evidence', ids[2:4]),
        ('no more than two motorcycles or mopeds abreast',
         'same_lane_two_wheeler_count', [ids[2], ids[4]]),
        ('subsection 3 exception reviewed independently and unresolved where text or facts absent',
         'subsection_3_exception_review', ids),
    ]
    plan['requirement_dispositions'] = [{
        'requirement': requirement,
        'source': SOURCE,
        'status': 'selected_required',
        'evidence_or_gap': 'unverified-law-coverage',
        'case_ids': members,
        'output_key': output,
    } for requirement, output, members in requirements]
    plan['observations'] = [
        {'name': name, 'mandatory': True,
         'source': 'original same-lane-history.jsonl and source-linked scene packet'}
        for name in CHANNEL_NAMES
    ]
    plan['camera_plan'] = {
        'profile': 'overview1080-capability',
        'duration_s': 45,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'subject': 'ego and other vehicle full bodies, lane lines and pass',
             'interval': 'full 45-second episode', 'view': 'overview'},
            {'subject': 'approach behind-to-ahead relative motion',
             'interval': 'full 45-second episode', 'view': 'approach'},
            {'subject': 'lateral surface gap and lane occupancy',
             'interval': 'full 45-second episode', 'view': 'reference_corner'},
            {'subject': 'ego operator forward view',
             'interval': 'full 45-second episode', 'view': 'driver_reference'},
        ],
    }
    for case in plan['cases']:
        case['kind'] = 'delivery'
        case['new_capture_selected'] = True
        case['construction_status'] = 'source_gated_native_runner_authored'
        case['recording_description'] = RECORDING
    for comparison in plan['comparisons']:
        comparison['status'] = 'selected_for_independent_audit'
    plan['planning_status'] = 'selected_source_gated_delivery_constructions'
    write(ROOT / 'case-plan.json', plan)

    relevance = {
        'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
        'relevant_laws': [{
            'law_id': LAW, 'quote': TEXT, 'applies_to': [ACTOR],
            'relevance_type': 'specific_match', 'confidence': 'high',
            'notes': 'Fixed road overtaking permits same-lane pass and same-lane abreast variants; consent and subsection 3 remain independently sourced.',
        }],
        'borderline_excluded': [],
    }
    write(ROOT / 'proposals/relevance.json', relevance)
    write(ROOT / 'proposals/relevance_batch.json', relevance)
    template = {
        'template_id': TEMPLATE_ID, 'law_id': LAW, 'actor': ACTOR,
        'quote': TEXT,
        'structure': {
            'law_id': LAW,
            'activation': {'condition': 'A qualifying motorcycle, moped or trimobile is driven abreast of, overtakes or passes another vehicle in the same traffic lane.', 'numeric_conditions': []},
            'obligation': {'description': 'Do not ride abreast of or overtake or pass another vehicle in the same traffic lane except the express two-abreast permission or subsection 3.', 'type': 'must_not', 'numeric_conditions': []},
            'exceptions': [
                {'source_clause': 'Except as provided in subsection 3',
                 'description': 'Subsection 3 operative text and applicability require separate original review.'},
                {'source_clause': 'Motorcycles and mopeds may, with the consent of the drivers, be operated no more than two abreast in a single traffic lane.',
                 'description': 'Independent driver consent and actual vehicle count and classification are required.'},
            ],
            'timing': {'description': 'Measure original frame/time history of lane occupancy, lateral and longitudinal position across the full pass or abreast episode.', 'numeric_conditions': []},
            'judgment_calls_needed': [],
        },
        'parameter_refs': [
            {'name': name, 'kind': kind, 'range_or_domain': domain}
            for name, kind, domain in (
                ('requested_same_lane', 'world_setup', 'same or adjacent lane'),
                ('requested_pass', 'controller', 'pass or sustained abreast'),
                ('requested_driver_consent', 'world_setup', 'independent consent present or absent'),
                ('requested_two_wheeler_count', 'world_setup', 'one, two or three riders'),
            )
        ],
    }
    write(ROOT / 'proposals/template.json', template)
    binding = {
        'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
        'established_contexts': ['Nevada road, reviewed same-lane and adjacent-lane road geometry',
                                 'source-reviewed qualifying motorcycle operator and other vehicle'],
        'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [dict(item, used_by_laws=[LAW])
                                for item in template['parameter_refs']],
    }
    write(ROOT / 'proposals/bindings.json', binding)
    proposal_cases = [{
        'case_id': AID + '__baseline', 'target_law_id': None,
        'target_type': 'baseline',
        'rationale': 'Shared source-reviewed road and camera contract; no additional recording.',
        'variable_assignments': {
            'requested_same_lane': {'kind': 'world_setup', 'value': True},
            'requested_pass': {'kind': 'controller', 'value': True},
            'requested_driver_consent': {'kind': 'world_setup', 'value': False},
            'requested_two_wheeler_count': {'kind': 'world_setup', 'value': 1},
        },
        'unresolved_judgment_calls': [],
        'recording_description': RECORDING,
    }]
    pair = {'same_lane_pass': 'same_lane_scope',
            'different_lane_pass': 'same_lane_scope',
            'consented_two_abreast': 'consent_for_abreast',
            'unconsented_two_abreast': 'consent_for_abreast',
            'three_abreast': 'no_more_than_two'}
    for case in plan['cases']:
        suffix = case['case_id'].removeprefix(AID + '__')
        primary = ('requested_same_lane' if suffix in ('same_lane_pass','different_lane_pass')
                   else 'requested_driver_consent' if suffix in ('consented_two_abreast','unconsented_two_abreast')
                   else 'requested_two_wheeler_count')
        proposal_cases.append({
            'case_id': case['case_id'], 'target_law_id': LAW,
            'target_type': 'compliant_attempt' if suffix in ('different_lane_pass','consented_two_abreast') else 'violating_attempt',
            'rationale': 'Original source-backed comparison of lane, relative motion, independently reviewed consent and count; legal outcome remains unadjudicated.',
            'variable_assignments': {
                name: {'kind': kind, 'value': case[name]}
                for name, kind in (
                    ('requested_same_lane', 'world_setup'),
                    ('requested_pass', 'controller'),
                    ('requested_driver_consent', 'world_setup'),
                    ('requested_two_wheeler_count', 'world_setup'),
                )
            },
            'unresolved_judgment_calls': [],
            'recording_description': RECORDING,
            'paired_probe_id': pair[suffix],
            'deliberate_differences': [primary],
            'probe': {'primary_variable': primary,
                      'comparison_or_standard': pair[suffix],
                      'target_value_or_branch': case[primary]},
        })
    write(ROOT / 'proposals/cases.json', {
        'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
        'cases': proposal_cases, 'sweep_specs': [],
    })
    refs = {}
    for stage in ('relevance_batch', 'relevance', 'template', 'bindings', 'cases'):
        path = ROOT / 'proposals' / (stage + '.json')
        refs[stage] = {'path': 'proposals/' + stage + '.json',
                       'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    refs['judgment_observables'] = []
    write(ROOT / 'proposals/semantic-index.json', {
        'format': 'worker-semantic-delivery', 'assignment_id': AID,
        'stages': refs,
    })


if __name__ == '__main__':
    main()
