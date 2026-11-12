"""Add the planned midpoint to the C101303 semantic case and comparison plans."""
import copy
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OLD='testing__C101303__NRS-484B-127-1__motor_vehicle_driver__source_verified_base'
NEW='testing__C101303__NRS-484B-127-1__motor_vehicle_driver__source_verified_midpoint'


def main():
    path=ROOT/'case-plan.json'
    plan=json.loads(path.read_text())
    if NEW not in {c['case_id'] for c in plan['cases']}:
        base=next(c for c in plan['cases'] if c['case_id']==OLD)
        midpoint=copy.deepcopy(base)
        midpoint['case_id']=NEW
        midpoint['purpose']='8.5 m engineering-gap midpoint for the sourced hill-crest judgment sweep'
        plan['cases'].append(midpoint)
        for row in plan['requirement_dispositions']:
            if row['status']=='selected_required' and OLD in row.get('case_ids',[]):
                row['case_ids'].append(NEW)
        plan['comparisons'].append({
            'comparison_id':'body_gap_midpoint',
            'case_ids':[OLD,NEW],
            'fixed_conditions':['same source-reviewed hill crest, lane-change route, vehicle blueprints, camera plan and capture rate; keep unlisted traffic/weather parameters fixed'],
            'deliberate_differences':['measured longitudinal complete-body gap']})
    if 'body_gap_midpoint_closer' not in {x['comparison_id'] for x in plan['comparisons']}:
        plan['comparisons'].append({
            'comparison_id':'body_gap_midpoint_closer',
            'case_ids':['testing__C101303__NRS-484B-127-1__motor_vehicle_driver__source_verified_closer',NEW],
            'fixed_conditions':['same source-reviewed hill crest, lane-change route, vehicle blueprints, camera plan and capture rate; keep unlisted traffic/weather parameters fixed'],
            'deliberate_differences':['measured longitudinal complete-body gap']})
    path.write_text(json.dumps(plan,indent=2)+'\n')
    path=ROOT/'proposals/cases.json'
    proposal=json.loads(path.read_text())
    if NEW not in {c['case_id'] for c in proposal['cases']}:
        base=next(c for c in proposal['cases'] if c['case_id']==OLD)
        midpoint=copy.deepcopy(base)
        midpoint['case_id']=NEW
        midpoint['rationale']='Measure a source-backed 8.5 m engineering midpoint between the closer and base setpoints while keeping other conditions fixed; leave legal judgment unresolved.'
        midpoint['variable_assignments']['requested_engineering_gap_m']['value']=8.5
        midpoint['deliberate_differences']=['requested_engineering_gap_m']
        proposal['cases'].append(midpoint)
        path.write_text(json.dumps(proposal,indent=2)+'\n')
    print(NEW)


if __name__=='__main__':
    main()
