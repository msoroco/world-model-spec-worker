"""Independent case-plan and knob audit for the two-lane Native constructions."""
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'native'))
from two_lane_engineering import ASSIGNMENT,CANDIDATES,construction

plan=json.loads((HERE/'case-plan.json').read_text())
case_id=ASSIGNMENT+'__two_lane_exception'
case=next(item for item in plan['cases'] if item['case_id']==case_id)
comparison=next(item for item in plan['comparisons'] if item['comparison_id']==ASSIGNMENT+'__comparison_two_lane_exception')
if case['source_branch']!='two or more same-direction lanes' or \
        set(comparison['case_ids'])!={ASSIGNMENT+'__probe_2',case_id} or \
        comparison['deliberate_differences']!=['same_direction_lane_count']:
    raise AssertionError('Two-lane statutory plan binding differs')
variants=[construction(candidate) for candidate in CANDIDATES]
if any(item['case_id']!=case_id or item['target_gap_m']!=140 or
       item['law_id']!='NRS-484B-127-2' or item['cell_id']!='C102372' or
       item['actor']!='heavy_vehicle_driver' for item in variants):
    raise AssertionError('Two-lane candidate identity differs')
if [item['knobs']['ego_target_speed_mps'] for item in variants]!=[8,7.5,8,8] or \
   [item['knobs']['lead_target_speed_mps'] for item in variants]!=[8,8,8.5,8] or \
   [item['knobs']['overview_fov_deg'] for item in variants]!=[90,90,90,110]:
    raise AssertionError('Two-lane fallback knob changes differ')
if [item['fallback_trigger']['metric'] for item in variants[1:]]!=[
        'min_surface_gap_m','max_gap_shortfall_m','min_projected_truck_frame_margin_px']:
    raise AssertionError('Two-lane trigger mechanisms differ')
if any(item['physical_lane_availability_verified'] or item['status']!='planned_native_construction'
       for item in variants):
    raise AssertionError('Unproven two-lane plan promoted')
print(json.dumps({'passed':True,'case_id':case_id,'candidate_count':4,
                  'statutory_comparison_bound':True,'selected_delivery_claimed':False},sort_keys=True))
