import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / 'native_scene.py'
spec = importlib.util.spec_from_file_location('native_scene_c109171', MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class NativeSceneTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        def ref(name, data):
            p = self.root/name
            p.write_text(data)
            return {'path':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
        self.ref = ref
        self.refs = [
          ref('map.json',json.dumps({'route_id':'crossing-1',
            'pedestrian_route_xy':[[-2,1],[-1,1],[1,1],[3,1]],
            'highway_boundary_xy':[[0,0],[4,0],[4,4],[0,4]]})),
          ref('vehicle_signal.json',json.dumps({'head_id':'head-1','official':True,
            'sole_green_arrow_aspect':'green-left-arrow'})),
          ref('pedestrian_signal.json',json.dumps({'device_id':'ped-1','governs_route_id':'crossing-1'}))]
        self.site = {'cell_id':'C109171','actor':'pedestrian','original_sources':self.refs,
          'map_source_path':'map.json','vehicle_signal_source_path':'vehicle_signal.json',
          'pedestrian_device_source_path':'pedestrian_signal.json','official_vehicle_head_id':'head-1',
          'pedestrian_device_id':'ped-1','pedestrian_route_id':'crossing-1','pedestrian_device_governs_route':True,
          'pedestrian_faces_vehicle_head':True,'sole_green_arrow_aspect':'green-left-arrow',
          'pedestrian_route_xy':[[-2,1],[-1,1],[1,1],[3,1]],
          'highway_boundary_xy':[[0,0],[4,0],[4,4],[0,4]]}
    def tearDown(self):
        self.tmp.cleanup()
    def events(self, indication='DONT_WALK', enter=True):
        rows=[]
        for frame,x in enumerate([-2,-1,1 if enter else -0.5,2 if enter else -0.5]):
            rows.append({'frame':frame,'vehicle_head_id':'head-1','pedestrian_device_id':'ped-1',
             'vehicle_head_lit_aspects':['green-left-arrow'],
             'pedestrian_facing_vehicle_head':True,'pedestrian_device_indication':indication,
             'pedestrian_xy':[x,1]})
        return rows
    def test_boundary_and_route(self):
        self.assertTrue(mod.verify_site(self.site,self.root))
        self.assertTrue(mod.inside_highway([0,1],self.site['highway_boundary_xy']))
        self.assertFalse(mod.inside_highway([-0.01,1],self.site['highway_boundary_xy']))
    def test_entry_without_other_permission(self):
        ref=self.ref('events.json',json.dumps(self.events()))
        entry=mod.measure_attempt(self.site,self.root,ref)['first_highway_entry']
        self.assertFalse(entry['separate_walk_indication'])
        self.assertEqual(entry['sampled_entry_bracket_frames'],[1,2])
    def test_entry_after_other_permission(self):
        ref=self.ref('events.json',json.dumps(self.events('WALK')))
        self.assertTrue(mod.measure_attempt(self.site,self.root,ref)['first_highway_entry']['separate_walk_indication'])
    def test_wait_without_entry(self):
        ref=self.ref('events.json',json.dumps(self.events(enter=False)))
        self.assertIsNone(mod.measure_attempt(self.site,self.root,ref)['first_highway_entry'])
    def test_reject_extra_green_aspect(self):
        rows=self.events();rows[2]['vehicle_head_lit_aspects'].append('green-circle')
        ref=self.ref('events.json',json.dumps(rows))
        with self.assertRaisesRegex(mod.SourceError,'not sole green'):
            mod.measure_attempt(self.site,self.root,ref)
    def test_reject_missing_and_changed_source(self):
        ref=self.ref('events.json',json.dumps(self.events()))
        (self.root/'events.json').write_text('[]')
        with self.assertRaisesRegex(mod.SourceError,'hash mismatch'):
            mod.measure_attempt(self.site,self.root,ref)
    def test_reject_device_identity_conflation(self):
        self.site['pedestrian_device_id']='head-1'
        with self.assertRaisesRegex(mod.SourceError,'separate device'):
            mod.verify_site(self.site,self.root)
    def test_reject_wrong_governed_route(self):
        self.site['pedestrian_device_governs_route']=False
        with self.assertRaisesRegex(mod.SourceError,'route relation'):
            mod.verify_site(self.site,self.root)
    def test_reject_authored_route_not_in_map_packet(self):
        self.site['pedestrian_route_xy'][1][1]=2
        with self.assertRaisesRegex(mod.SourceError,'route differs from original map'):
            mod.verify_site(self.site,self.root)
    def test_reject_authored_arrow_not_in_signal_packet(self):
        self.site['sole_green_arrow_aspect']='green-right-arrow'
        with self.assertRaisesRegex(mod.SourceError,'arrow aspect differs from original source'):
            mod.verify_site(self.site,self.root)
    def test_reject_authored_device_not_governing_route(self):
        self.site['pedestrian_route_id']='other-crossing'
        with self.assertRaisesRegex(mod.SourceError,'route identity differs from original map'):
            mod.verify_site(self.site,self.root)
    def test_reject_preentered_capture(self):
        rows=self.events();rows[0]['pedestrian_xy']=[1,1]
        ref=self.ref('events.json',json.dumps(rows))
        with self.assertRaisesRegex(mod.SourceError,'already in highway'):
            mod.measure_attempt(self.site,self.root,ref)
    def test_reject_dropped_frame(self):
        rows=self.events();rows[2]['frame']=3;rows[3]['frame']=4
        ref=self.ref('events.json',json.dumps(rows))
        with self.assertRaisesRegex(mod.SourceError,'frame sequence invalid'):
            mod.measure_attempt(self.site,self.root,ref)

if __name__=='__main__':
    unittest.main()
