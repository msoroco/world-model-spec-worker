import copy,json,tempfile,unittest
from pathlib import Path
from traffic_spec_adapter.control_portions import apply
from traffic_spec_adapter.geometry import static_map
from shapely.geometry import Point

MAP='''<OpenDRIVE><road id="1" length="30" junction="-1"><planView><geometry s="0" x="0" y="0" hdg="0" length="30"><line/></geometry></planView><lanes><laneSection s="0"><center><lane id="0" type="none"/></center><right><lane id="-1" type="driving"><width sOffset="0" a="4" b="0" c="0" d="0"/></lane></right></laneSection></lanes></road></OpenDRIVE>'''

class ControlPortionTests(unittest.TestCase):
 def setup_source(self,root):
  (root/'road.xodr').write_text(MAP)
  config={'posting':{'authority_status':'authored_synthetic_fact'},'sign':{'type':'traffic.speed_limit.60','position_m':[2,4.5,0]},'zone':{'road_id':1,'section_id':0,'lane_id':-1,'station_interval_m':[2,20],'end_sign':{'type':'traffic.speed_limit.30','position_m':[20,4.5,0]}},'measurements':{'sign_position_tolerance_m':.05}}
  (root/'config.json').write_text(json.dumps(config))
  regions,polygons,lanes=static_map(root/'road.xodr')
  devices={('actor','60'):{'kind':'speed_limit_sign','position':[2,-4.5],'speed_value':60/3.6,'governs':[lanes[(1,0,-1)]]},('actor','30'):{'kind':'speed_limit_sign','position':[20,-4.5],'speed_value':30/3.6,'governs':[lanes[(1,0,-1)]]}}
  return config,regions,polygons,lanes,devices

 def test_downstream_sign_does_not_govern_upstream_vehicle(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);_,regions,polygons,lanes,devices=self.setup_source(root)
   mapping=apply(root,regions,polygons,lanes,devices)
   sixty=devices[('actor','60')]['governs'][0];thirty=devices[('actor','30')]['governs'][0]
   self.assertTrue(polygons[sixty].contains(Point(10,-2)))
   self.assertFalse(polygons[thirty].intersects(Point(10,-2)))
   self.assertTrue(polygons[thirty].contains(Point(25,-2)))
   self.assertFalse(polygons[sixty].intersects(Point(25,-2)))
   self.assertEqual(mapping[0]['native_trigger_lane_region'],[lanes[(1,0,-1)]])
   self.assertEqual([r['kind'] for r in regions[-2:]],['roadway','roadway'])

 def test_native_association_without_explicit_authored_zone_stays_unchanged(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);config,regions,polygons,lanes,devices=self.setup_source(root);before=copy.deepcopy(devices)
   config['posting']['authority_status']='unconfirmed';(root/'config.json').write_text(json.dumps(config))
   self.assertEqual(apply(root,regions,polygons,lanes,devices),[]);self.assertEqual(devices,before)

 def test_unobserved_or_inconsistent_native_sign_rejects_mapping(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);_,regions,polygons,lanes,devices=self.setup_source(root)
   devices[('actor','30')]['speed_value']=30*.44704
   with self.assertRaises(ValueError):apply(root,regions,polygons,lanes,devices)
