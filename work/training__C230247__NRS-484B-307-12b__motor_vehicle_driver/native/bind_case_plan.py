"""Bind the exact red-X pair to measured statutory source requirements."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSIGNMENT = ROOT.name

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')

plan_path = ROOT / 'case-plan.json'
plan = json.loads(plan_path.read_text())
case_ids = [ASSIGNMENT + '__probe_1', ASSIGNMENT + '__probe_2']
for item in plan['requirement_dispositions']:
    item['status'] = 'selected_required'
    item['case_ids'] = case_ids
    item['evidence_or_gap'] = 'Exact source-bound red-X pair prepared for independent physical review; no accepted original evidence exists.'
for index, case in enumerate(plan['cases']):
    case['kind'] = 'delivery'
    case['requested_not_measured'] = True
    case['gap_ids'] = ['red_x_lane_occupancy']
    case['construction'] = 'construction.json' if index == 0 else 'cases/probe_2/construction.json'
plan['evidence_review'] = {
    'reviewer': 'worker', 'method': 'Frozen evidence inventory and exact assignment membership reviewed; both contain no accepted recordings.',
    'facts': [],
    'gaps': [{'id': 'red_x_lane_occupancy',
              'requirement': 'Facing driver approach and movement relative to individual-lane red X',
              'source': 'NRS 484B.307(12)(b)',
              'why_existing_insufficient': 'No accepted recording IDs in frozen membership.'}]
}
plan['source_observation_mapping'] = {
    term['term']: {
        'evidence': 'Original per-frame signal, map, body and trace sources joined in saved finalizer',
        'channels': [term['term']],
        'source_refs': [f'inputs/{ASSIGNMENT}/assignment.json', 'measurement.json']}
    for term in plan['mandatory_observation_terms']
}
for item in plan['mandatory_observation_terms']:
    item['status'] = 'source_bound_measurement'
plan['candidate_plans'] = [{'case_id': cid, 'primary': ('construction.json' if i == 0 else 'cases/probe_2/construction.json'),
                            'risk': 'Native red-X asset and original physical lane crossing require local confirmation'}
                           for i, cid in enumerate(case_ids)]
plan['blockers'] = ['Public compatibility, saved-only processing, semantic proposals and independent audits remain unfinished.']
plan['selected_branch'] = 'individual-lane red-X facing driver, outside versus entering governed lane'
dump(plan_path, plan)
requirements = [
    {'disposition_index': 0, 'requirement': 'NRS-484B-307-12b', 'source': 'NRS 484B.307(12)(b)',
     'output_key': 'overhead_red_x', 'method': 'overhead_red_x', 'value_type': 'object', 'kind': 'measured',
     'inputs': ['native-signal-rows.jsonl', 'native-map-readback.xodr']},
    {'disposition_index': 1, 'requirement': 'NRS-484B-307-12b', 'source': 'NRS 484B.307(12)(b)',
     'output_key': 'lane_occupancy', 'method': 'lane_occupancy', 'value_type': 'object', 'kind': 'measured',
     'inputs': ['native-signal-rows.jsonl', 'trace.jsonl', 'capture/evidence.jsonl']},
    {'disposition_index': 2, 'requirement': 'NRS-484B-307-12b', 'source': 'NRS 484B.307(12)(b)',
     'output_key': 'facing_driver', 'method': 'facing_driver', 'value_type': 'number', 'kind': 'measured',
     'inputs': ['native-signal-rows.jsonl']}
]
contract = {'format': 'worker-measurement-contract', 'requirements': requirements,
            'negative': {'remove': ['native-signal-rows.jsonl'],
                         'error_contains': 'Missing required source: native-signal-rows.jsonl'}}
dump(ROOT / 'measurement.json', contract)
dump(ROOT / 'cases/probe_2/measurement.json', contract)
proposals = {'format': 'worker-stage-cases', 'cell_id': 'C230247', 'actor': 'motor_vehicle_driver',
             'law_id': 'NRS-484B-307-12b', 'status': 'draft_pending_semantic_validation',
             'cases': [{'case_id': cid, 'target_law_id': 'NRS-484B-307-12b',
                        'target_type': 'controlled_pair',
                        'rationale': 'Measure outside or entering the original red-X governed lane',
                        'variable_assignments': {
                            'red_x_lane_occupancy': {'kind': 'subject_behavior', 'unit': 'lane entry event',
                                                     'value': i == 1}},
                        'paired_probe_id': 'red_x_lane_occupancy',
                        'deliberate_differences': ['red_x_lane_occupancy'],
                        'recording_description': json.loads((ROOT / ('config.json' if i == 0 else 'cases/probe_2/config.json')).read_text())['recording_description']}
                       for i, cid in enumerate(case_ids)]}
dump(ROOT / 'proposals/cases.json', proposals)
