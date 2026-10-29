"""Join final partition proofs and explicit controlled-comparison audit specs."""
import hashlib,importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OWNER=Path(__file__).parent
BINDINGS=json.loads((OWNER/'additional-bindings.json').read_text())
ORIGINAL=json.loads((ROOT/'partitions/demo-test-03.json').read_text())['assignment_ids']
AIDS=ORIGINAL+[b['assignment_id'] for b in BINDINGS]
def write(p,d):p.write_text(json.dumps(d,indent=2)+'\n')
def scopes(plan):
 aid=plan['assignment_id']
 if '__C157964__' in aid or ('__C158196__' in aid and '257-' in aid):
  for d in plan['requirement_dispositions']:
   req=d['requirement'].lower()
   if any(x in req for x in ['exclude actual','traffic is not controlled','traffic is not being controlled']):d['case_ids']=[aid+'__passive_control']
 return plan

def comparison_specs(plan):
 aid=plan['assignment_id'];law=plan['law_id'];result=[]
 for c in plan['comparisons']:
  key=c['comparison_id'];selector='';op='distinct'
  fixed=['duration_s','cameras','rate_hz']
  if law=='NRS-484B-113-2':
   selector='measurements.backing_crosswalk_body_overlap.value.'+('street_corner_progression.bearing_change_deg' if 'corner' in key else 'intersection_entry_transitions' if key=='intersection' else 'backing_overlap_original_frames')
   fixed += ['crosswalk_definition']
  elif law=='NRS-484B-407':
   selector='measurements.u_turn_motion.value.samples' if key=='discontinuous_reversal' else 'measurements.bidirectional_500ft_visibility.value.clear_frames_by_approach.'+('ahead_opposing' if 'ahead' in key else 'behind_same_direction')
   fixed += ['turn_station_m','location_kind']
  elif law=='NRS-484B-127-2':
   if '500ft_space' in key:selector='measurements.truck_body_gap.value.minimum_m';fixed += ['ego_class','lead_class','same_direction_lane_count','conditions_context','entrant_start_tick']
   elif key=='subject_width':selector='measurements.truck_width_and_lanes.value.trucks.0.measured_bbox_width_m';fixed += ['lead_blueprint','requested_body_gap_m','same_direction_lane_count']
   elif key=='lead_width':selector='measurements.truck_width_and_lanes.value.trucks.1.measured_bbox_width_m';fixed += ['ego_blueprint','requested_body_gap_m','same_direction_lane_count']
   elif key=='conditions_permit':selector='measurements.requirement_0.value.entry_and_activity.conditions_context';fixed += ['ego_blueprint','lead_blueprint','requested_body_gap_m','same_direction_lane_count']
   elif key=='enter_and_occupy':selector='measurements.requirement_0.value.entry_and_activity.samples.1.entrant_lateral_span_m';fixed += ['ego_blueprint','lead_blueprint','requested_body_gap_m','same_direction_lane_count','conditions_context']
   elif key=='two_available_lanes':selector='measurements.truck_width_and_lanes.value.same_direction_lane_count';fixed += ['ego_blueprint','lead_blueprint','requested_body_gap_m','conditions_context']
   else:selector='measurements.requirement_0.value.entry_and_activity.overtaking_front_frames';fixed += ['ego_blueprint','lead_blueprint','requested_body_gap_m','same_direction_lane_count','conditions_context']
  else:
   if 'governing_exception' in key:selector='measurements.requirement_0.value.governing_control_sample_count';fixed += ['initial_response','reference_kind','through_start_tick']
   elif 'not_so_obligated' in key:selector='measurements.requirement_0.value.other_entrance_obligation';fixed += ['reference_kind','initial_response','through_start_tick','departure_speed_mps']
   elif 'approaching_traffic' in key or 'across_or_within_history' in key:selector='measurements.intersection_motion.value.through_within_intersection_frames';fixed += ['reference_kind','initial_response','departure_speed_mps']
   elif 'occupied_traffic' in key:selector='measurements.intersection_motion.value.first_ego_body_entry_frame';fixed += ['reference_kind','initial_response','through_start_tick','departure_speed_mps']
   else:selector='measurements.intersection_motion.value.samples';fixed += ['reference_kind','through_start_tick']
  result.append(dict(comparison_id=key,case_ids=c['case_ids'],fixed_config_selectors=fixed,checks=[dict(name='Measured '+key+' intervention',case_ids=c['case_ids'],selector=selector,operator=op)]))
 return result

if __name__=='__main__':
 counts={'branches':0,'comparisons':0,'recordings':0,'comparison_case_uses':0};ready=[]
 for aid in AIDS:
  folder=ROOT/'work'/aid
  if not (folder/'execution-manifest.json').exists():continue
  manifest=json.loads((folder/'execution-manifest.json').read_text());plan=scopes(json.loads((folder/'case-plan.json').read_text()))
  if not all('post_capture' in e for e in manifest['cases']):continue
  # Required Core atoms are source-bound to the Native packet acquisition, not to source presence alone.
  for e in manifest['cases']:
   construction=json.loads((folder/e['construction']).read_text());cfg=json.loads(next(x['content'] for x in construction['files'] if x['path']=='config.json'))
   for atom in cfg['required_atoms']:
    if atom not in e['acquisition']:e['acquisition'][atom]=dict(entrypoint='runner.py',method='Original Native map plus authored scenario_geometry.json directed one-way roadway packet',evidence='Original scene.xodr and Native map readback; diagnostic converter coverage proves software only')
  law=plan['law_id']
  obligations={
   'NRS-484B-113-2':['Verify eight original body vertices, signed reverse velocity and original gear/control simultaneously at the actual intersection/crosswalk entry; do not choose a legal contact rule.','Verify actual curb/street corner geometry and measured body-centroid/gate progression around it, including reverse-control continuity.','Verify distinctly marked stripes or actual opposite sidewalk lateral connections establishing the near-side unmarked crosswalk in the corresponding exact variant.'],
   'NRS-484B-407':['Verify modeled driver-eye location against actual seat/viewpoint and original body-vertex ray endpoints in both approaching directions within statutory500feet.','Verify Native terrain/container geometry, original blocker hit locations, clear body rays and actual four-view pixels; finite rays do not prove continuous legal visibility.','Verify curve/approach-to-crest/near-crest location geometry and a realizable continuous or multiple-movement opposite-direction swept path.'],
   'NRS-484B-127-2':['Verify actual goods-transport truck and drawn-unit classifications, overall widths against80inches, all-unit body envelopes and physical tow-hitch force/stability readback.','Verify measured surface space against statutory500feet, actual entrant geometry and full entry/occupancy histories without converting engineering clearance to without-danger judgment.','Verify available same-direction lane count over time, actual obstructing bodies and traffic constraints, and actual overtaking/passing history; no post-overtake grace duration.'],
  }
  plan['physical_pixel_audits'] += obligations.get(law,[
   'Verify properly erected authorized stop/yield signs and actual approach governance, all entrance obligations and through/non-through highway context.',
   'Verify stop-line precedence, marked or sidewalk-derived crosswalk geometry, and actual absence of both before the nearest-view fallback; retain original complete-cessation/slowing measurements without legal epsilon.',
   'Verify actual officer identity/authority, original arm-bone gesture readback and subject response, or actual Native signal state and affected approach lanes; mere presence is not governance.',
   'Verify approaching and entered traffic through the entire across-or-within movement, actual driver viewpoint samples/spacing and original four-view pixels; immediate hazard, caution and continuous nearest visibility remain judgments.'
  ])
  plan['physical_pixel_audits']=list(dict.fromkeys(plan['physical_pixel_audits']))
  write(folder/'execution-manifest.json',manifest);write(folder/'case-plan.json',plan);write(folder/'comparison-audit-specs.json',comparison_specs(plan))
  contribution=json.loads((folder/'branch-contribution.json').read_text());counts['branches']+=len(contribution['branches']);counts['comparisons']+=len(plan['comparisons']);counts['recordings']+=len(plan['cases']);counts['comparison_case_uses']+=sum(len(c['case_ids']) for c in plan['comparisons']);ready.append(aid)
 counts['explicit_reuses']=counts['comparison_case_uses']-counts['recordings'];counts['ready_assignments']=ready;counts['all_assignments_ready']=len(ready)==len(AIDS);counts['scope']='Planned recordings and CPU software proofs only; Native executed/video-Core accepted/comparison physically complete all zero.'
 write(OWNER/'partition-summary.json',counts);print(json.dumps(counts,indent=2))
