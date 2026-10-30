import json,pathlib
R=pathlib.Path(__file__).resolve().parents[2]
ids=json.loads((R/'partitions/demo-test-04.json').read_text())['assignment_ids']
ids += ['testing__C24811__NRS-484B-250-4__motor_vehicle_driver','testing__C376646__NRS-484B-250-4__motor_vehicle_driver']
checks={
'gap':('original_following_geometry.minimum_body_gap_m','distinct'),'ego_speed':('original_following_geometry.ego_speed_mps','distinct'),'lead_speed':('original_following_geometry.lead_speed_mps','distinct'),'lead_braking':('original_following_geometry.lead_speed_mps','distinct'),'wet_surface':('traffic_condition_history.original_weather','distinct'),'following_relation':('original_following_geometry.before_change_samples','distinct'),'traffic':('traffic_condition_history.participant_counts','distinct'),
'strict_rate_boundary':('original_speed_history.max_sampled_mph','strictly_increasing'),
'governed_portion':('posted_zone_speed_history.zone_sample_count','distinct'),'governed_direction':('posted_zone_speed_history.zone_sample_count','distinct'),'authority':('posted_zone_speed_history.authority_asserted','distinct'),'units':('posted_sign_context.posted_unit','distinct'),'source_visibility':('posted_sign_context.sign_station_m','distinct'),
'red_entry':('red_exhibition_vs_body_entry.red_at_entry_events','distinct'),'yellow_entry':('red_exhibition_vs_body_entry.body_entry_events','distinct'),'already_inside':('red_exhibition_vs_body_entry.body_entry_events','distinct'),'green_termination':('governing_yellow_red_sequence.original_states','distinct'),'steady_yellow_alone':('governing_yellow_red_sequence.yellow_alone_frames','distinct'),'facing_governance':('governing_yellow_red_sequence.facing_subject_history','distinct'),
'line_reference':('marked_line_stop_before_entry.sampled_halt_precedes_entry','distinct'),'marked_crosswalk_reference':('marked_line_stop_before_entry.sampled_halt_precedes_entry','distinct'),'unmarked_crosswalk_reference':('marked_line_stop_before_entry.sampled_halt_precedes_entry','distinct'),'sight_reference':('marked_line_stop_before_entry.sampled_halt_precedes_entry','distinct'),'earlier_stop':('earlier_stop_and_intersection_occupancy.earlier_stop_before_ego_entry','distinct'),'occupied':('earlier_stop_and_intersection_occupancy.other_occupancy_before_ego_entry','distinct'),'cautious':('marked_line_stop_before_entry.first_body_entry.frame','distinct'),'uncovered':('installed_dark_signal_heads.covered_requested','distinct'),'inoperative_entry':('installed_dark_signal_heads.all_heads_dark_at_entry','distinct'),'installed':('marked_line_stop_before_entry.sampled_halt_precedes_entry','distinct')}
for aid in ids:
 f=R/'work'/aid
 if not (f/'case-plan.json').exists():continue
 p=json.loads((f/'case-plan.json').read_text());specs=[]
 for c in p['comparisons']:
  path,op=checks[c['comparison_id']]
  if '600-1c' in aid and c['comparison_id']=='strict_rate_boundary':path='posted_zone_speed_history.max_sampled_mph'
  key,field=path.split('.',1)
  ss=dict(comparison_id=c['comparison_id'],case_ids=c['case_ids'],fixed_config_selectors=['cell_id','actor','law_id','duration_s','rate_hz','cameras'],checks=[dict(name='Measured deliberate contrast '+c['comparison_id'],case_ids=c['case_ids'],selector='measurements.'+key+'.value.'+field,operator=op)])
  if c['comparison_id']=='units':ss['checks'].append(dict(name='Equivalent normalized statutory rate',case_ids=c['case_ids'],selector='measurements.posted_zone_speed_history.value.posted_limit_mps',operator='equal'))
  specs.append(ss)
 (f/'comparison-audit-specs.json').write_text(json.dumps(specs,indent=2)+'\n')
 print(aid,len(specs))
