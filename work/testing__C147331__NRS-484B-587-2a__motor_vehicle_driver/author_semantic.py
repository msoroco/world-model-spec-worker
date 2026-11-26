"""Author canonical draft semantics for eleven exact outside-lane variants."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from outside_lane import CASES

HERE = Path(__file__).resolve().parent
AID = HERE.name
LAW = 'NRS-484B-587-2a'
CELL = 'C147331'
ACTOR = 'motor_vehicle_driver'
SOURCE = 'inputs/' + AID + '/assignment.json'
CAMERAS = tuple((name, 1920 if i == 0 else 1280, 1080 if i == 0 else 720)
                for i, name in enumerate(('overview', 'approach', 'reference_corner', 'driver_reference')))
CHANNELS = (
    ('controlled_access_authority', 'source record', 'separate public-authority controlled-access determination'),
    ('public_highway_boundary', 'world meters', 'sourced highway boundary and vehicle footprint'),
    ('marked_lane_geometry', 'world meters', 'original Native lane boundaries, marking identity and road direction'),
    ('outside_lane_body_occupancy', 'world meters/frame', '20 Hz original vehicle body and marked-lane footprint relation'),
    ('shoulder_geometry_and_paving', 'world meters/source', 'original shoulder extent and independent paving source'),
    ('lawful_shoulder_signage', 'source record/pixels', 'separate lawful sign inventory and original driver-view pixels'),
    ('vehicle_class_and_driver', 'source record', 'original actor blueprint, physical control and class source'),
    ('emergency_necessity', 'source record', 'separate contemporaneous emergency record and vehicle history'),
    ('subsection3_authorization', 'source record', 'separate qualifying class and manner-of-use authorization'),
)
RECORDING = {
    'channels': [dict(name=name, unit=unit, method=method, sampling_rate_hz=20,
                      time_window='Full original 45-second 900-frame episode',
                      reference_frame='Original CARLA world frame and source-sealed lane boundaries',
                      uncertainty='Physical occupancy, sign visibility and legal authorization need original independent review')
                 for name, unit, method in CHANNELS],
    'context_inputs': [{'name': 'reviewed_controlled_access_site', 'unit': 'source record',
                        'method': 'separate source-hashed authority, map, markings, sign, class and exception packets'}],
    'limitations': ['Synthetic fixtures do not establish Native motion or legal status.',
                    'No engineering lateral cutoff is used as a statutory threshold.'],
}
VARIABLES = ('approach', 'route_class', 'vehicle_class', 'sign_permits_shoulder',
             'emergency_required', 'subsection3_authorized')


def put(path: Path, value: dict) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(HERE)), 'sha256': sha256(path.read_bytes()).hexdigest()}


def run() -> None:
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    if len(plan['cases']) != len(CASES) or len(plan['comparisons']) != 9:
        raise ValueError('exact eleven-case nine-comparison plan changed')
    ids = [AID + '__' + case.name for case in CASES]
    if [item['case_id'] for item in plan['cases']] != ids:
        raise ValueError('case ordering or identity changed')
    law_text = plan['law_text']
    clauses = [
        ('Except if required by an emergency', 'Emergency necessity supported by contemporaneous original record'),
        ('as otherwise authorized by subsection 3', 'Separately sourced subsection 3 qualification and manner of shoulder use'),
        ('A person driving a vehicle described in paragraphs (a) to (f), inclusive, of subsection 4 of NRS 484B.210 [list appended below] may drive that vehicle on a paved shoulder of a controlled-access highway where lawfully placed signage allows that vehicle to use the shoulder in that manner.',
         'Sourced qualifying vehicle, paving, lawful signage and manner of use'),
    ]
    for clause, _ in clauses:
        if clause not in law_text:
            raise ValueError('frozen exception clause differs')
    descriptors = {
        'approach': 'north or south original one-way approach',
        'route_class': 'marked traffic, marked entrance, marked exit, paved shoulder or outside nonshoulder',
        'vehicle_class': 'ordinary or independently qualified vehicle class',
        'sign_permits_shoulder': 'lawful shoulder-use sign absent or present',
        'emergency_required': 'contemporaneous emergency necessity absent or claimed',
        'subsection3_authorized': 'separate subsection 3 authorization absent or claimed',
    }
    refs = [dict(name=name, kind='world_setup', range_or_domain=descriptors[name], unit='source request')
            for name in VARIABLES]
    relevance = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW,
                                    'quote': 'Upon any portion of the highway that lies outside of a marked traffic lane or marked entrance or exit lane.',
                                    'applies_to': [ACTOR], 'confidence': 'medium',
                                    'relevance_type': 'specific_match',
                                    'notes': 'Controlled-access legal designation and all exceptions require separate source packets.'}],
                 'borderline_excluded': []}
    template = {'template_id': LAW + '@' + ACTOR, 'law_id': LAW, 'actor': ACTOR,
                'status': 'draft', 'quote': law_text,
                'structure': {'law_id': LAW,
                              'activation': {'condition': 'A person drives a vehicle on a separately established controlled-access highway.', 'numeric_conditions': []},
                              'obligation': {'description': 'Do not drive upon a highway portion outside marked traffic, entrance or exit lanes.',
                                             'type': 'must_not', 'numeric_conditions': []},
                              'exceptions': [dict(trigger=description, effect='possible exception requiring source review',
                                                  replacement_obligation='No automated legal conclusion', source_clause=clause)
                                             for clause, description in clauses],
                              'timing': {'description': 'Original full-frame lane, body, sign and exception history.', 'numeric_conditions': []},
                              'judgment_calls_needed': []},
                'parameter_refs': refs}
    bindings = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
                'established_contexts': [], 'law_refs': [{'template_id': template['template_id'], 'binding_kind': 'direct'}],
                'context_refs': [], 'fixed_parameters': [],
                'variable_parameters': [dict(item, used_by_laws=[LAW]) for item in refs]}
    canonical_cases = []
    for case in CASES:
        assignments = {name: {'kind': 'world_setup', 'value': getattr(case, name), 'unit': 'source request'}
                       for name in VARIABLES}
        is_marked = case.route_class in ('traffic_lane', 'entrance_lane', 'exit_lane')
        authorized = case.emergency_required or case.subsection3_authorized or case.vehicle_class == 'qualifying_484b210_4' and case.sign_permits_shoulder
        primary = 'route_class' if case.name in ('north_marked', 'north_outside', 'south_marked', 'south_outside', 'north_entrance', 'north_exit') else (
                  'vehicle_class' if 'ordinary' in case.name or 'qualified' in case.name else (
                  'emergency_required' if 'emergency' in case.name else 'subsection3_authorized' if 'authorized' in case.name else 'sign_permits_shoulder'))
        canonical_cases.append({'case_id': AID + '__' + case.name, 'target_law_id': LAW,
                                'target_type': 'compliant_attempt' if is_marked or authorized else 'violating_attempt',
                                'status': 'draft',
                                'rationale': 'Requested clause contrast only; actual motion, authority and legal treatment remain unresolved.',
                                'variable_assignments': assignments,
                                'unresolved_judgment_calls': ['Controlled-access designation, vehicle qualification, emergency necessity and authorization need independent review'],
                                'recording_description': RECORDING,
                                'paired_probe_id': 'outside-lane-controlled-comparisons',
                                'deliberate_differences': list(VARIABLES),
                                'probe': {'primary_variable': primary,
                                          'comparison_or_standard': 'Nine exact plan comparisons with fixed source identities and original duration',
                                          'target_value_or_branch': case.name}})
    baseline = dict(canonical_cases[0], case_id=AID+'__baseline', target_law_id=None, target_type='baseline')
    baseline.pop('paired_probe_id'); baseline.pop('deliberate_differences'); baseline.pop('probe')
    cases = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft', 'sweep_specs': [], 'sweeps_expanded': True,
             'cases': [baseline] + canonical_cases}
    proposal_dir = HERE / 'proposals'
    refs_by_stage = {}
    for name, value in [('relevance', relevance), ('relevance-batch', relevance),
                        ('template', template), ('bindings', bindings), ('cases', cases)]:
        refs_by_stage[name] = put(proposal_dir / (name + '.json'), value)
    put(proposal_dir / 'semantic-index.json', {'format': 'worker-semantic-delivery',
         'assignment_id': AID, 'status': 'source_gated_draft',
         'stages': {'relevance_batch': refs_by_stage['relevance-batch'],
                    'relevance': refs_by_stage['relevance'], 'template': refs_by_stage['template'],
                    'judgment_observables': [], 'bindings': refs_by_stage['bindings'],
                    'cases': refs_by_stage['cases']}})
    dispositions = [
        ('Controlled-access public highway designation and boundary', 'controlled_access_authority'),
        ('One-way multilane road and marked traffic, entrance and exit geometry', 'marked_lane_geometry'),
        ('Original vehicle body position throughout travel', 'outside_lane_body_occupancy'),
        ('Separate paved shoulder geometry and lawful shoulder signage', 'shoulder_geometry_and_paving'),
        ('Driver identity and qualifying vehicle class', 'vehicle_class_and_driver'),
        ('Emergency necessity and subsection 3 authorization context', 'emergency_necessity'),
    ]
    plan['requirement_dispositions'] = [dict(disposition_index=i, requirement=requirement, source=SOURCE,
                                            status='selected_required', case_ids=ids,
                                            evidence_or_gap='No accepted recording; original source-hashed Native and authority evidence required',
                                            planned_channel=channel)
                                        for i, (requirement, channel) in enumerate(dispositions)]
    plan['source_observation_mapping'] = {}
    plan['camera_plan'] = {'profile': 'overview1080-capability', 'duration_s': 45,
                           'composition': 'synchronized_four_view_primary',
                           'coverage': [{'view': name, 'subject': 'original ego body, lanes, shoulder and signage',
                                         'interval': 'full 45-second original episode'} for name, _, _ in CAMERAS]}
    for item in plan['cases']:
        item['kind'] = 'delivery'
        item['new_capture_selected'] = True
        item['recording_description'] = RECORDING
    plan['planning_status'] = 'source_gated_draft_semantics_and_exact_cases'
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    run()
