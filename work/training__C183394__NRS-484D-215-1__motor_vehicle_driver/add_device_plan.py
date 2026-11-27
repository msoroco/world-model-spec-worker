"""Bind the authored device pair to the exact C183394 plan after proof staging."""
from copy import deepcopy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
AID = ROOT.name
PATH = ROOT / 'case-plan.json'
plan = json.loads(PATH.read_text())
ids = [AID + '__device_dim', AID + '__device_high']
for requirement in plan['requirement_dispositions']:
    if requirement['requirement'] in ('text-0', 'text-1'):
        for case_id in ids:
            if case_id not in requirement['case_ids']:
                requirement['case_ids'].append(case_id)
for index, case_id in enumerate(ids):
    if any(row['case_id'] == case_id for row in plan['cases']):
        continue
    case = deepcopy(plan['cases'][0])
    case.update(case_id=case_id, target_type='delivery',
                planning_status='cpu_construction_offline_proven_compatibility_pending',
                source_branch='NRS 484D.100 official-device directive alternative on same adjacent shoulder and opposed oncoming vehicle',
                comparison_variable='beam_request_policy_with_fixed_authored_device',
                condition_index=7+index,
                claim='Authored OpenDRIVE lamp-use signal and Native map readback request only; official authority, applicability, original optical evidence and legal outcome unverified.')
    plan['cases'].append(case)
comparison_id = AID + '__device_directive_beam_comparison'
if not any(row['comparison_id'] == comparison_id for row in plan['comparisons']):
    plan['comparisons'].append({
        'comparison_id': comparison_id, 'case_ids': ids,
        'deliberate_differences': ['beam request policy: dim within measured 500 feet versus retain high'],
        'fixed_conditions': {'cell_id': 'C183394', 'law_id': 'NRS-484D-215-1',
            'actor': 'motor_vehicle_driver',
            'road': 'same adjacent paved shoulder and opposed oncoming OpenDRIVE with one authored lamp-use signal',
            'authored_signal_id': '100', 'authored_signal_name': 'AUTHORED_LAMP_USE_INSTRUCTION',
            'camera_count': 4, 'rate_hz': 20, 'duration_s': 30},
        'measurement': 'Original signal map readback, decoded visibility, directive applicability and independent official authority review required; authored signal alone does not prove statutory activation.'})
PATH.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + '\n')
print('BIND two exact device cases and one fixed-source comparison')
