"""Partition-two semantic planning contribution; no implementation/readiness claim."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ids=json.loads((ROOT/'partitions/demo-test-02.json').read_text())['assignment_ids']
sources=json.loads((ROOT/'inputs/coverage/branch-sources.json').read_text())['laws']
candidates=json.loads((ROOT/'inputs/coverage/candidate-cells.json').read_text())['cells']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
laws={};bindings=[]
def add(law,key,description,axis,values,*,layout=None,maneuver=None,control=None,measurement=None):
 a=next(a for a in ids if json.loads((ROOT/'inputs'/a/'assignment.json').read_text())['law_id']==law)
 original=json.loads((ROOT/'inputs'/a/'assignment.json').read_text()); c=original['cell'];wanted=(layout or c['layout'],maneuver or c['maneuver'],control or c['control'])
 assignment=a
 if wanted!=(c['layout'],c['maneuver'],c['control']):
  matches=[x for x in candidates if (x['layout'],x['maneuver'],x['control'])==wanted and 'motor_vehicle_driver' in x['candidate_ego_parties'] and not any('train' in s or 'held' in s for s in x['allocated_sets'])]
  matches.sort(key=lambda x:(not any('test' in s for s in x['allocated_sets']),x['cell_id']))
  assert matches, wanted
  selected=matches[0];assignment=f"testing__{selected['cell_id']}__{law}__motor_vehicle_driver"
  if not any(b['assignment_id']==assignment for b in bindings):bindings.append({'assignment_id':assignment,'original_assignment_id':a,'original_cell_incompatibility':f"Fixed original {c['layout']}/{c['maneuver']}/{c['control']} cannot realize {wanted[0]}/{wanted[1]}/{wanted[2]}.",'binding_reason':description,'catalog_cell':selected,'implementation_status':'pending'})
 cases=[f'{assignment}__{key}_{i}' for i in range(len(values))]
 row={'branch_id':f'{law}-{key}','topic_ids':list(sources[law]['topics']) if law not in laws else ['text-0'],'status':'implementation_pending','assignment_id':assignment,'case_ids':cases,'comparison_ids':[key], 'description':description,'comparison':{'comparison_id':key,'case_ids':cases,'fixed_conditions':['Same exact cell and actor scope','Same camera profile and duration','All unrelated geometry, controller and acquisition parameters fixed'],'deliberate_differences':{axis:values}},'required_measurement':measurement or axis,'physical_acceptance':False}
 laws.setdefault(law,{'branches':[]})['branches'].append(row)
L='NRS-484B-250-1'
add(L,'earlier_entry_precedence','Vehicle already entered from different highway; measure giving precedence through clearance','ego_precedence_policy',['wait_until_clear','advance_before_clear'],measurement='Footprint intersection-entry brackets, occupancy histories, speed/proximity and precedence motion; no legal right-of-way threshold')
add(L,'entry_order','Earlier entry activation compared with later other entry','other_entry_schedule',['other_first','ego_first'])
add(L,'separate_intersection','Identify same versus separate crossings on divided highway at statutory 30-foot separation','other_crossing',['same_roadway_crossing','other_separate_roadway_crossing'],measurement='Connected roadway polygons, highway identities, boundary distances and both entry locations')
for ctl in ['traffic_light','stop_sign','yield_sign']:
 add(L,'governing_'+ctl,'Official-device exclusion with device governing same versus separate crossing','device_governance',['same_intersection','different_intersection'],control=ctl)
add(L,'inoperative_qualification','Subsection-4 qualification separately retained; installed uncovered inoperative signal','signal_operation',['inoperative_at_entry','operative_at_entry'],control='inoperative_signal')
add(L,'opposite_intended_left','Opposite approaches where other driver intends left turn; ego retains travel','other_intention',['left_turn','straight'])
add(L,'opposite_making_left','Opposite approaches where other driver actually makes left turn','other_maneuver',['left_turn','straight'])
L='NRS-484B-250-2'
add(L,'left_yield','Same identified intersection from different highways, ego left; precedence contrast','ego_precedence_policy',['yield','advance'],measurement='Entry brackets and raw time difference, relative approach bearings, precedence histories; no numeric definition of approximately')
add(L,'entry_timing','Time-of-entry comparison preserves approximate-time judgment unresolved','other_start_delay_s',[0,4])
add(L,'left_right','Left versus right driver activation','ego_approach_side',['left','right'])
add(L,'separate_intersection','Same versus separate statutory roadway crossings','other_crossing',['same_roadway_crossing','other_separate_roadway_crossing'])
for ctl in ['traffic_light','stop_sign','yield_sign']:
 add(L,'governing_'+ctl,'Official-device exclusion measured by actual governance','device_governance',['same_intersection','different_intersection'],control=ctl)
add(L,'inoperative_qualification','Subsection-4 qualification not erased by official-device exclusion','signal_operation',['inoperative_at_entry','operative_at_entry'],control='inoperative_signal')
add(L,'opposite_intended_left','Other opposite vehicle intends left turn','other_intention',['left_turn','straight'])
add(L,'opposite_making_left','Other opposite vehicle makes left turn','other_maneuver',['left_turn','straight'])
L='NRS-484B-227-1'
add(L,'opening_uturn','Selected U-turn traverses opening versus closed dividing section','uturn_crossing_location',['opening','closed_section'],measurement='Every body vertex against divider/opening polygons and complete initial/final travel directions')
add(L,'multimovement_uturn','Opposite-direction outcome in one or multiple movements per U-turn definition','movement_schedule',['continuous','multiple_movements'])
add(L,'right_roadway','Right-hand roadway versus wrong opposing roadway','initial_roadway',['right_hand','opposing'])
for motion in ['over','across','within']:
 add(L,'divider_'+motion,'Separate prohibited movement '+motion+' dividing space, barrier or section','divider_contact',['none',motion])
add(L,'left_turn','Left turn through opening contrasted with closed section','left_turn_location',['opening','closed_section'],layout='divided_road',maneuver='left_turn',control='other_vehicle')
add(L,'semicircular','Semicircular turn geometry separately measured without redefining U-turn','turn_shape',['semicircular','nonsemicircular'])
for place in ['crossover','intersection']:
 add(L,'authority_'+place,'Exception at '+place+' requires public-authority establishment distinct from geometry','establishment_provenance',['established_by_public_authority','no_establishment_evidence'])
for material in ['physical_barrier','dividing_space','dividing_section']:
 add(L,'opening_'+material,'Opening exception for '+material+' with actual extent and traversed footprint','opening_status',['opening_present','no_opening'])
L='NRS-484B-220-1'
add(L,'designated_direction','Travel direction on designated and signposted one-way highway','signed_velocity_direction',['designated','opposed'],measurement='Signed displacement along designated roadway tangent, original sign instruction, authority, governance and occupancy')
add(L,'reverse_motion','Heading held fixed while actual travel direction reverses','longitudinal_velocity',['forward','reverse'])
add(L,'governed_extent','Sign scope over occupied roadway section','route_section',['inside_governed_extent','outside_governed_extent'])
add(L,'designation','Designation and signposting are separate activation facts','designation_provenance',['documented','not_documented'])
L='NRS-484B-600-1a'
add(L,'speed','Measured speed contrast with all road and traffic conditions fixed','requested_speed_mps',[4,9],measurement='Original velocity/speed histories, condition calibration and provenance; no lawful reasonable/proper cutoff')
for axis,values in [('traffic_density',['sparse','queue']),('traffic_kind',['vehicle','pedestrian_and_animal']),('surface',['dry','wet']),('surface_frozen',['clear','authored_ice_or_snow']),('highway_width_m',[12,8]),('weather',['clear','rain']),('visibility',['clear','calibrated_fog']),('curvature',['straight','curved']),('sight_obstruction',['absent','present']),('stopping_observation',['lower_brake_effort','higher_brake_effort'])]:
 add(L,axis,'Due regard context: '+axis+' varies independently; no engineering quantity is a legal standard',axis,values)
L='NRS-484B-413-2'
add(L,'business_right_distance','Business district right turn with continuous signal over final statutory 100 feet versus shorter distance','signal_on_distance_ft',[100,80],measurement='Path distance integrated backward from course-change onset and signal semantic display history; 100ft=30.48m exact unit conversion')
add(L,'signal_interruption','Signal continuity in last 100 feet','signal_history',['continuous','interrupted'])
add(L,'weather','Signal rule applies regardless of weather','weather',['clear','rain'])
add(L,'hand_signal','Signal of intention may use actual hand/arm display; semantic display must be acquired','signal_display',['indicator','hand_arm'])
for district,layout,threshold in [('residence','paved_road',100),('other_area','paved_road',300)]:
 for maneuver in ['right_turn','left_turn','change_lane']:
  add(L,district+'_'+maneuver,'Statutory '+district+' '+maneuver+' last '+str(threshold)+' feet; district facts separately documented','signal_on_distance_ft',[threshold,threshold-20],layout=layout,maneuver=maneuver,control='other_vehicle',measurement=f'Backward path integration from course change with district evidence, continuous intention-signal display and {threshold}ft reference')
for maneuver in ['left_turn','change_lane']:
 add(L,'business_'+maneuver,'Business district '+maneuver+' alternative, frontage context authored on paved-road cell','signal_on_distance_ft',[100,80],layout='paved_road',maneuver=maneuver,control='other_vehicle')
out={'format':'worker-partition-branch-planning-v1','partition':2,'status':'planned_only_implementation_pending','laws':laws,'additional_bindings':bindings,'source_sha256':{'inputs/definitions.jsonl':sha(ROOT/'inputs/definitions.jsonl'),'inputs/coverage/branch-sources.json':sha(ROOT/'inputs/coverage/branch-sources.json')},'review_notes':['Read original texts and supplied definitions; summaries do not create time/epsilon/legal thresholds.','413-2 district definitions are not supplied in definitions.jsonl: require sourced district building-use/frontage context; no unsupported numerical district test invented.','Paved-road cells do not fix district status and can support authored business/residence/other context; fixed business-district cell cannot support residence/other.','No CARLA execution, video acceptance, Core acceptance, or completed comparison claimed.','Catalog has no ordinary right_turn candidate in residence_district nor outside_business_residence_district; generic paved_road with exact maneuver is preferred to changing fixed maneuver.']}
p=ROOT/'work'/ids[0]/'partition-2-branch-inventory.json';p.write_text(json.dumps(out,indent=2)+'\n')
print(p.relative_to(ROOT),len([b for l in laws.values() for b in l['branches']]),len(bindings))
