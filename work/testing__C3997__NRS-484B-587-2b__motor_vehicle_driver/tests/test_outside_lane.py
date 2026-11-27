import importlib.util
from pathlib import Path
import sys
import unittest

path=Path(__file__).resolve().parents[1]/'outside_lane.py'
spec=importlib.util.spec_from_file_location('solid_line_c3997',path)
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)

class Adapter:
 def __init__(self,fail=False):self.calls=[];self.fail=fail
 def spawn_vehicle(self,point,**kw):self.calls.append(('spawn',point));return 'ego'
 def set_route(self,ego,route,**kw):
  self.calls.append(('route',route))
  if self.fail:raise RuntimeError('route failed')
 def set_capture_metadata(self,ego,metadata):self.calls.append(('metadata',metadata))
 def destroy(self,ego):self.calls.append(('destroy',ego))

def site(case):
 direction=1 if case.approach=='north' else -1
 routes={}
 for c in m.CASES:
  if c.approach!=case.approach:continue
  x0=-2 if c.origin=='traffic' else 2
  x1=-2 if c.destination=='traffic' else 2
  points=[[x0,0],[x0,10*direction],[x1,20*direction],[x1,30*direction]]
  adjacent='entrance' if c.origin==c.destination else (c.destination if c.origin=='traffic' else c.origin)
  routes[c.name]={'id':'route-'+c.name,'origin':c.origin,'destination':c.destination,
   'adjacent_lane':adjacent,'source_sha256':'map-source', 'points':points,
   'separator':{'anchor_xy':[0,0],'normal_xy':[1,0],
    'start_xy':[0,-40],'end_xy':[0,40],
    'kind':'solid_white','separates':sorted(['traffic',adjacent]),
    'source_sha256':'marking-source'}}
 return {'cell_id':'C3997','layout':'adjacent_lanes','lane_change_control':'solid_white_line',
  'legal_controlled_access_source_sha256':'authority-source',
  'public_highway_boundary_source_sha256':'boundary-source',
  'map_sha256':'map-source','lane_marking_source_sha256':'marking-source',
  'lane_function_source_sha256':'function-source',
  'direction_source_sha256':'direction-source',
  'vehicle_class_source_sha256':'vehicle-source',
  'paved_shoulder_source_sha256':'paving-source',
  'lawful_shoulder_sign_source_sha256':'sign-source',
  'emergency_record_source_sha256':'emergency-source',
  'subsection3_authorization_source_sha256':'authorization-source',
  'native_spawn_source_sha256':'spawn-source',
  'camera_plan_sha256':'camera-source',
  'approach':case.approach,'approach_vector':[0,direction],
  'routes':routes,'vehicle_class':case.vehicle_class,
  'shoulder_paved':case.subsection3_shoulder_authorized,
  'lawful_sign_permits_shoulder':case.subsection3_shoulder_authorized,
  'emergency_required':case.emergency_required,
  'subsection3_shoulder_authorized':case.subsection3_shoulder_authorized}

def rows(case,n=2):
 base={'case':case.name,'ego_id':'ego','map_sha256':'map-source',
  'lane_marking_source_sha256':'marking-source','lane_function_source_sha256':'function-source',
  'legal_controlled_access_source_sha256':'authority-source',
  'public_highway_boundary_source_sha256':'boundary-source',
  'direction_source_sha256':'direction-source','camera_plan_sha256':'camera-source',
  'vehicle_class_source_sha256':'vehicle-source',
  'paved_shoulder_source_sha256':'paving-source',
  'lawful_shoulder_sign_source_sha256':'sign-source',
  'emergency_record_source_sha256':'emergency-source',
  'subsection3_authorization_source_sha256':'authorization-source',
  'route_id':'route-'+case.name,'approach':case.approach,'origin':case.origin,
  'destination':case.destination,'separator_kind':'solid_white',
  'vehicle_class':case.vehicle_class,
  'separator_source_sha256':'marking-source',
  'emergency_required':case.emergency_required,
  'subsection3_shoulder_authorized':case.subsection3_shoulder_authorized,
  'shoulder_paved':case.subsection3_shoulder_authorized,
  'lawful_sign_permits_shoulder':case.subsection3_shoulder_authorized,
  'source_sha256':'original-source','ego_speed_mps':8.0}
 return [dict(base,original_frame=100+i,
   center_signed_m=-2.0+4.0*i/(n-1) if case.origin!=case.destination else -2.0,
   body_min_signed_m=(-2.0+4.0*i/(n-1) if case.origin!=case.destination else -2.0)-0.6,
   body_max_signed_m=(-2.0+4.0*i/(n-1) if case.origin!=case.destination else -2.0)+0.6,
   center_segment_fraction=0.5,body_min_segment_fraction=0.48,
   body_max_segment_fraction=0.52)
   for i in range(n)]

class Tests(unittest.TestCase):
 def test_all_routes_cross_or_stay_as_declared(self):
  for case in m.CASES:
   with self.subTest(case=case.name):
    a=Adapter();result=m.build_case(a,site(case),case)
    self.assertEqual(result['route_id'],'route-'+case.name)
    self.assertEqual(a.calls[1][0],'route')
    self.assertEqual(m.crosses_separator(a.calls[1][1],site(case)['routes'][case.name]['separator']),
                     case.origin!=case.destination)
 def test_reject_missing_authority_wrong_line_and_direction(self):
  c=m.CASES[1];s=site(c);s['legal_controlled_access_source_sha256']=''
  with self.assertRaisesRegex(ValueError,'source missing'):m.build_case(Adapter(),s,c)
  s=site(c);s['routes'][c.name]['separator']['kind']='dashed_white'
  with self.assertRaisesRegex(ValueError,'solid-white separator'):m.build_case(Adapter(),s,c)
  s=site(c);s['routes'][c.name]['points']=[[2,0],[2,10],[2,20]]
  with self.assertRaisesRegex(ValueError,'crossing route misses'):m.build_case(Adapter(),s,c)
  s=site(c);s['routes'][c.name]['separator']['start_xy']=[0,40]
  s['routes'][c.name]['separator']['end_xy']=[0,80]
  with self.assertRaisesRegex(ValueError,'crossing route misses'):m.build_case(Adapter(),s,c)
  s=site(c);s['routes'][c.name]['points'].reverse()
  with self.assertRaisesRegex(ValueError,'route opposes'):m.build_case(Adapter(),s,c)
  qualifying=m.CASES[-1];s=site(qualifying)
  s['lawful_sign_permits_shoulder']=False
  with self.assertRaisesRegex(ValueError,'paving or lawful sign'):
   m.build_case(Adapter(),s,qualifying)
 def test_cleanup_on_route_error(self):
  a=Adapter(fail=True)
  with self.assertRaisesRegex(RuntimeError,'route failed'):m.build_case(a,site(m.CASES[0]),m.CASES[0])
  self.assertEqual(a.calls[-1],('destroy','ego'))
 def test_original_body_line_measurement_and_rejection(self):
  c=m.CASES[1];data=m.measure_original(rows(c),c)
  self.assertTrue(data['center_crossing_observed'])
  self.assertTrue(m.measure_original(rows(c,9),c)['center_crossing_observed'])
  self.assertIsNone(data['legal_judgment'])
  b=rows(c);b[1]['original_frame']=120
  with self.assertRaisesRegex(ValueError,'discontinuity'):m.measure_original(b,c)
  b=rows(c);b[1]['body_min_signed_m']=b[1]['center_signed_m']+1
  with self.assertRaisesRegex(ValueError,'body footprint'):m.measure_original(b,c)
  b=rows(c);b[1]['subsection3_shoulder_authorized']=True
  with self.assertRaisesRegex(ValueError,'exception context'):m.measure_original(b,c)
 def test_comparison_source_and_deliberate_change(self):
  a=m.measure_original(rows(m.CASES[0],900),m.CASES[0])
  b=m.measure_original(rows(m.CASES[1],900),m.CASES[1])
  a['original_history_sha256']='a';b['original_history_sha256']='b'
  self.assertEqual(m.audit_comparison(a,b,{'destination'})['changed'],['destination'])
  b['fixed']['map_sha256']='other'
  with self.assertRaisesRegex(ValueError,'fixed source changed'):m.audit_comparison(a,b,{'destination'})

if __name__=='__main__':unittest.main()
