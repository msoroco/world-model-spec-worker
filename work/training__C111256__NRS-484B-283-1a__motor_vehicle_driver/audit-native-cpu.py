"""Independent uncontrolled-crosswalk geometry, timing and exception audit."""
import hashlib,importlib.util,json,tempfile
from pathlib import Path
import xml.etree.ElementTree as ET
HERE=Path(__file__).resolve().parent;NATIVE=HERE/'native'
def module(name):
 spec=importlib.util.spec_from_file_location(name,NATIVE/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def audit():
 a=json.loads((HERE.parent.parent/'inputs'/HERE.name/'assignment.json').read_text())
 geom=module('geometry');eng=module('engineering');meas=module('measure')
 assert a['cell']['layout']=='intersection' and a['cell']['maneuver']=='travel' and a['cell']['control']=='crosswalk'
 assert 'official traffic-control devices are not in place or not in operation' in a['law_record']['text']
 assert 'half of the highway' in a['law_record']['text']
 assert geom.check()['passed'] and (NATIVE/'road.xodr').read_text()==geom.open_drive()
 assert json.loads((NATIVE/'route.json').read_text())==geom.route()
 xml=ET.parse(NATIVE/'road.xodr').getroot()
 assert len(xml.findall('.//signal'))==0 and len(xml.findall(".//object[@type='crosswalk']"))==1
 assert xml.find('junction/connection').attrib['connectingRoad']=='13'
 assert xml.find("road[@id='13']/link/successor").attrib['elementId']=='4'
 plan=json.loads((NATIVE/'engineering-plan.json').read_text())
 assert plan['candidates']==[eng.parameters(c,k) for c in eng.CASES for k in eng.CANDIDATES]
 pair=[]
 for case in eng.CASES:
  choices=[eng.parameters(case,k) for k in eng.CANDIDATES]
  assert len({json.dumps(x['knobs'],sort_keys=True) for x in choices})==4
  for x in choices[1:]:assert sum(x['knobs'][k]!=choices[0]['knobs'][k] for k in choices[0]['knobs'])==1
  path=NATIVE/'fixtures'/(case+'-480.json');m=meas.measure(path,meas.sha256(path))
  assert m['official_devices_absent_in_source'] and m['marked_crosswalk_and_ego_directional_half_in_source']
  assert not m['physical_behavior_observed'] and m['legal_verdict'] is None
  pair.append(m)
 assert [x['yielded_to_crosswalk_pedestrian'] for x in pair]==[True,False,True,True]
 assert [x['first_ego_crosswalk_overlap_frame'] for x in pair]==[177,137,177,177]
 assert [x['blind_white_cane_exception_declared'] for x in pair]==[False,False,False,True]
 assert all(x['full_halt_before_crosswalk'] for x in pair)
 w1=json.loads((NATIVE/'fixtures/witness_1-480.json').read_text())['frames']
 w2=json.loads((NATIVE/'fixtures/witness_2-480.json').read_text())['frames']
 e1=json.loads((NATIVE/'fixtures/exception_1_1-480.json').read_text())['frames']
 e2=json.loads((NATIVE/'fixtures/exception_1_2-480.json').read_text())['frames']
 for x,y in zip(w1,w2):
  for k in ('frame','time_s','official_device_actors_present','crosswalk_marked','pedestrian_on_ego_highway_half','road_one_way','ego_directional_lanes','pedestrian_conflict_occupied','pedestrian_blind_declared','white_cane_declared'):assert x[k]==y[k]
 for x,y in zip(e1,e2):
  for k in ('frame','time_s','ego_x_m','ego_y_m','ego_speed_m_s','official_device_actors_present','crosswalk_marked','pedestrian_on_ego_highway_half','road_one_way','ego_directional_lanes','pedestrian_conflict_occupied'):assert x[k]==y[k]
 with tempfile.TemporaryDirectory() as tmp:
  path=Path(tmp)/'bad.json';record=json.loads((NATIVE/'fixtures/witness_1-480.json').read_text());record['frames'][0]['official_device_actors_present']=True;path.write_text(json.dumps(record))
  try:meas.measure(path,meas.sha256(path))
  except ValueError as exc:assert 'device absence' in str(exc)
  else:raise AssertionError('Unexpected device accepted')
  metrics={'source_kind':'original_native_and_video','max_route_cross_track_error_m':.5,'min_ego_half_pedestrian_clearance_s':.5,'min_crosswalk_or_body_pixel_margin_px':30}
  path=Path(tmp)/'metrics.json';path.write_text(json.dumps(metrics));digest=hashlib.sha256(path.read_bytes()).hexdigest()
  assert all(eng.evaluate_trigger(k,metrics,path,digest) for k in eng.CANDIDATES[1:])
  for k in eng.CANDIDATES[1:]:
   try:eng.evaluate_trigger(k,metrics,path,'0'*64)
   except ValueError:pass
   else:raise AssertionError('Unbound trigger accepted')
 return {'passed':True,'assignment_id':HERE.name,'candidate_count':16,'witness_yield':[True,False],
         'exception_declared':[False,True],'source_scope':'authored geometry and synthetic CPU; no original pixels or accepted recording'}
if __name__=='__main__':print(json.dumps(audit(),indent=2))
