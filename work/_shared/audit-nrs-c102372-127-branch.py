"""Independent pending source/case audit for heavy truck following."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAW = 'NRS-484B-127-2'
AID = 'training__C102372__NRS-484B-127-2__heavy_vehicle_driver'
matrix_path = ROOT / 'work/_shared/branch-coverage.json'
branches = json.loads(matrix_path.read_text())['laws'][LAW]['branches']
source = json.loads((ROOT / 'inputs/coverage/branch-sources.json').read_text())['laws'][LAW]
plan = json.loads((ROOT / 'work' / AID / 'case-plan.json').read_text())
expected = {
    'qualifying_80in_truck_500ft_following': {'text-0', 'reviewed-scope-0'},
    'conditions_permit_qualifier': {'text-0'},
    'overtaking_and_passing_carveout': {'text-0'},
    'two_or_more_same_direction_lanes_exception': {'text-1'},
}
actual = {b['branch_id'].removesuffix('__' + LAW): set(b['topic_ids']) for b in branches}
if actual != expected or set().union(*actual.values()) != set(source['topics']):
    raise ValueError('Exact truck-following branch map differs')
if any(b['status'] != 'pending_review' or b['assignment_id'] != AID for b in branches):
    raise ValueError('Unproven branch promoted or rebound')
cases = {c['case_id'] for c in plan['cases']}
comparisons = {c['comparison_id']: set(c['case_ids']) for c in plan['comparisons']}
suffixes={
    'qualifying_80in_truck_500ft_following':(['probe_1','probe_2'],'comparison'),
    'conditions_permit_qualifier':(['conditions_steady','conditions_lead_brake'],'comparison_conditions'),
    'overtaking_and_passing_carveout':(['passing_hold','passing_overtake'],'comparison_passing'),
    'two_or_more_same_direction_lanes_exception':(['probe_2','two_lane_exception'],'comparison_two_lane_exception'),
}
bound=set()
for branch in branches:
    key=branch['branch_id'].removesuffix('__'+LAW)
    expected_cases={AID+'__'+suffix for suffix in suffixes[key][0]}
    expected_comparison=AID+'__'+suffixes[key][1]
    if set(branch.get('case_ids',[]))!=expected_cases or branch.get('comparison_ids')!=[expected_comparison] or \
            comparisons.get(expected_comparison)!=expected_cases:
        raise ValueError('Truck statutory comparison binding differs: '+key)
    bound|=expected_cases
if cases!=bound or len(comparisons)!=4:
    raise ValueError('Unbound or missing planned statutory case')
if any(case.get('kind')!='planned_only' for case in plan['cases']):
    raise ValueError('Unproven case promoted from planned status')
if '500 feet' not in source['law']['text'] or '80 inches' not in source['law']['text']:
    raise ValueError('Exact statutory thresholds differ')
print(json.dumps({'passed': True, 'law_id': LAW, 'branches_mapped': 4,
                  'planned_cases':len(cases),'controlled_comparisons':len(comparisons),
                  'runnable_branches': 0, 'coverage_sha256': hashlib.sha256(matrix_path.read_bytes()).hexdigest()}, sort_keys=True))
