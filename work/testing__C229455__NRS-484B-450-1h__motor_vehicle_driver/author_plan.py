"""Bind exact 450(1)(h) alternatives, exceptions and source-bound measurements."""
from __future__ import annotations
import json
from pathlib import Path
from safety_zone import CASES, THIRTY_FT_M

ROOT=Path(__file__).resolve().parent
AID=ROOT.name
LAW='NRS-484B-450-1h'
SOURCE='inputs/'+AID+'/assignment.json'
CHANNELS=('site_source','official_zone_designation','zone_boundaries','adjacent_curb',
          'opposite_end_references','vehicle_body_history','vehicle_motion_history',
          'signed_end_station_history','between_zone_curb_history','halt_activity_history',
          'exception_context','traffic_motion_history','camera_frame_map')


def write(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


def main():
    path=ROOT/'case-plan.json';plan=json.loads(path.read_text(encoding='utf-8'))
    gap={'id':'no-original-safety-zone-evidence',
         'requirement':'Original highway, officially designated safety zone, adjacent curb, both ends, vehicle body, activity and exceptions',
         'source':SOURCE,
         'why_existing_insufficient':'evidence.json lists zero accepted recordings; witness is conditional and unverified'}
    plan['evidence_review']={'reviewer':'CPU worker','method':'Read zero-entry frozen evidence.json and exact assignment; no physical equivalence claimed.',
                             'facts':[],'gaps':[gap]}
    plan['cases']=[]
    for c in CASES:
        plan['cases'].append({'case_id':AID+'__'+c.case_id,'target_law_id':LAW,
          'branch':'between official safety zone and adjacent curb or within 30 feet of opposite end points',
          'placement':c.placement,'end':c.end,'offset_m':c.offset_m,
          'halt_activity':c.activity,'exception_context':c.exception,
          'gap_ids':[gap['id']],
          'construction':'safety_zone.construct: reviewed original highway/zone/curb source gate, physical markers, ego route and traffic',
          'measurement':'safety_zone.measure_original: 900 joined original frames, body footprint, signed curb-end station, halt and exception context',
          'physical_risk':'Actual official designation, marking visibility, narrow curb-side route, body position and full camera coverage require original review.',
          'legal_judgment':'unresolved'})
    pairs=(
      ('between_vs_outside','between_park','outside_corridor_park','terminal body corridor placement'),
      ('west_below_vs_at','west_end_below_30ft','west_end_at_30ft','signed west-end station 0.1 m below versus at statutory 30 feet'),
      ('west_at_vs_above','west_end_at_30ft','west_end_above_30ft','signed west-end station at versus 0.1 m above statutory 30 feet'),
      ('west_vs_east_below','west_end_below_30ft','east_end_below_30ft','selected opposite curb end and longitudinal body placement'),
      ('park_vs_stop','between_park','between_stop','halt activity'),
      ('park_vs_stand','between_park','between_stand','halt activity'),
      ('ordinary_vs_conflict','between_stop','between_stop_conflict','conflict-avoidance circumstance'),
      ('ordinary_vs_law','between_park','between_park_law','independently sourced law-compliance circumstance'),
      ('ordinary_vs_officer','between_stand','between_stand_officer','police officer direction circumstance'),
      ('ordinary_vs_device','between_park','between_park_device','official traffic-control-device direction circumstance'))
    plan['comparisons']=[{'comparison_id':name,'case_ids':[AID+'__'+a,AID+'__'+b],
      'fixed_conditions':'same source-reviewed highway, official zone, curb geometry, driver, motor vehicle, 20 Hz, 45 s, four-camera plan and unrelated context',
      'deliberate_differences':[difference]} for name,a,b,difference in pairs]
    ids=[x['case_id'] for x in plan['cases']]
    plan['requirement_dispositions']=[{'requirement':LAW+' both placement alternatives, stop/stand/park and four stated exceptions',
      'source':SOURCE,'status':'selected_required','evidence_or_gap':gap['why_existing_insufficient'],
      'case_ids':ids}]
    plan['observations']=[{'name':name,'mandatory':True,
      'description':'Original source-bound '+name.replace('_',' ')} for name in CHANNELS]
    plan['source_observation_mapping']={}
    plan['camera_plan']={'profile':'overview1080-capability','duration_s':45,
      'composition':'synchronized_four_view_primary','coverage':[
       {'view':'overview','subject':'official zone boundaries, curb and full vehicle route','interval':'approach through halt'},
       {'view':'approach','subject':'ego approach, zone end and curb station','interval':'approach through halt'},
       {'view':'reference_corner','subject':'zone end reference, curb mark and vehicle body','interval':'approach through halt'},
       {'view':'driver_reference','subject':'driver view of visible safety-zone marking/sign','interval':'approach through halt'}]}
    plan['runtime_uncertainties']=['Actual designation, markings and visibility require original independent review.',
      'Statutory distance is 30 feet = 9.144 m; signed original body and curb-end geometry is retained without presuming a legal vehicle-distance convention.',
      'Applicability of each exception remains independent legal review.']
    plan['planning_status']='selected_cpu_package_in_progress'
    write(path,plan)
    contract={'format':'worker-measurement-contract','requirements':[{'disposition_index':0,
      'requirement':plan['requirement_dispositions'][0]['requirement'],'source':SOURCE,
      'output_key':'safety_zone_body_station_and_exception_context','method':'analyze',
      'value_type':'object','kind':'measured',
      'inputs':['safety-zone-history.jsonl','safety-zone-site.json','trace.jsonl','video_frames.jsonl']}],
      'negative':{'remove':['safety-zone-site.json'],
                  'error_contains':'Missing required source: safety-zone-site.json'}}
    write(ROOT/'measurement-contract.json',contract)

if __name__=='__main__':main()
