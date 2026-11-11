"""Bind deterministic finite alley placement points to the exact case plan."""

import json
from pathlib import Path


root = Path(__file__).resolve().parent
plan_path = root / 'case-plan.json'
plan = json.loads(plan_path.read_text())
proposal = json.loads((root / 'proposals/cases.json').read_text())
existing = {case['case_id'] for case in plan['cases']}
generated = [case for case in proposal['cases']
             if case['target_type'] == 'judgment_sweep']
if len(generated) != 3:
    raise ValueError('Three deterministic alley placement points required')
for case in generated:
    if case['case_id'] in existing:
        continue
    offset = case['sweep_point']['pedestrian_offset_m']
    plan['cases'].append({
        'case_id': case['case_id'], 'target_law_id': plan['law_id'],
        'target_type': 'selected',
        'status': 'planned', 'gap_ids': ['person_exposure'],
        'construction': {'alley_direction': 'east',
                         'target_speed_mps': 5.0,
                         'protected_interest': 'person',
                         'pedestrian_offset_m': offset,
                         'placement_method': 'alley_geometry.plan_alley',
                         'stationary_pedestrian': True,
                         'property_owner': 'stationary_pedestrian'},
        'candidate_risk': {'status': 'physical',
            'reason': 'Selected Native alley connectivity, original lane tracking and camera visibility remain physical risks.'}})
comparison_id = 'alley_pedestrian_offset_sweep'
if not any(c['comparison_id'] == comparison_id for c in plan['comparisons']):
    plan['comparisons'].append({
        'comparison_id': comparison_id,
        'case_ids': [case['case_id'] for case in generated],
        'fixed_conditions': 'same authored alley polygon, 10 m pedestrian station, 5 m/s requested speed, property position, cameras and measurement',
        'deliberate_differences': '1.5/1.95/2.4 m authored pedestrian lateral placement; original body gap measured separately',
        'status': 'generated_exact_cases_pending_physical_review',
        'source_refs': plan['sources'][:1]})
for disposition in plan.get('requirement_dispositions', []):
    if disposition['status'] == 'selected_required':
        disposition['case_ids'] = [case['case_id'] for case in plan['cases']]
plan_path.write_text(json.dumps(plan, indent=2) + '\n')
print('Bound nine exact alley cases including three finite placement points')
