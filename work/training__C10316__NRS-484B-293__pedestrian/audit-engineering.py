"""Independent fixed-context and distinct-knob audit of eight unselected plans."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def main():
    all_plans=[]
    for suffix,offset in (('reference',-.65),('contrast',.65)):
        plans=[]
        for ident in ('primary','fallback1','fallback2','fallback3'):
            path=HERE/'draft-candidates'/suffix/ident/'construction.json'
            plan=json.loads(path.read_text())
            assert plan['case_id']==f'training__C10316__NRS-484B-293__pedestrian__{suffix}'
            assert plan['candidate_id']==ident
            assert plan['law_id']=='NRS-484B-293' and plan['cell_id']=='C10316'
            assert plan['actor']=='pedestrian' and plan['duration_s']==12 and plan['rate_hz']==20
            assert plan['comparison_variable']=='pedestrian_lateral_crosswalk_half'
            assert plan['engineering']['target_lateral_m']==offset
            assert plan['road_source']=='native/road.xodr'
            assert (HERE/plan['road_source']).is_file()
            plans.append(plan)
        primary=plans[0]['engineering']
        assert primary['spawn_start_x_m']==primary['capture_start_x_m']==-4
        f1=plans[1]['engineering']; assert f1['spawn_start_x_m']==-6 and f1['capture_start_x_m']==-4
        assert f1['pre_roll_s']==3 and f1['trigger']['threshold']==1
        f2=plans[2]['engineering']; assert f2['controller_lookahead_s']==.25
        assert f2['trigger']['threshold']==.2 and f2['trigger']['minimum_frames']==10
        f3=plans[3]['engineering']; assert f3['camera_overhead_z_m']==9
        assert f3['trigger']['threshold']==.95
        assert all(p['engineering']['trigger']['source']!='none' for p in plans[1:])
        assert len({json.dumps(p['engineering'],sort_keys=True) for p in plans})==4
        all_plans.append(plans)
    for a,b in zip(*all_plans):
        assert {k:v for k,v in a.items() if k not in ('case_id','engineering')} == {
            k:v for k,v in b.items() if k not in ('case_id','engineering')}
        assert {k:v for k,v in a['engineering'].items() if k!='target_lateral_m'} == {
            k:v for k,v in b['engineering'].items() if k!='target_lateral_m'}
        assert b['engineering']['target_lateral_m']-a['engineering']['target_lateral_m']==1.3
    print(json.dumps({'audit':'pass','unselected_candidate_drafts':8,
                      'distinct_plans_per_case':4,'source_bound_trigger_rules':6,
                      'physical_triggers_measured':0,'selected_cases':0},sort_keys=True))


if __name__=='__main__':
    main()
