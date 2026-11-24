import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('saved_measurement_c109171', ROOT/'saved_measurement.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class SavedMeasurementTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.refs = []
        def ref(name, value):
            path = self.root/name
            path.write_text(json.dumps(value), encoding='utf-8')
            return {'path':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        self.ref = ref
        route = [[-2,1],[-1,1],[1,1],[3,1]]
        boundary = [[0,0],[4,0],[4,4],[0,4]]
        refs = [
            ref('map.json', {'route_id':'crossing-1','pedestrian_route_xy':route,
                             'highway_boundary_xy':boundary}),
            ref('head.json', {'head_id':'head-1','official':True,
                              'sole_green_arrow_aspect':'green-left-arrow'}),
            ref('device.json', {'device_id':'ped-1','governs_route_id':'crossing-1'})]
        site = {'source_kind':'native_original','cell_id':'C109171','actor':'pedestrian',
                'original_sources':refs,'map_source_path':'map.json',
                'vehicle_signal_source_path':'head.json',
                'pedestrian_device_source_path':'device.json',
                'official_vehicle_head_id':'head-1','pedestrian_device_id':'ped-1',
                'pedestrian_route_id':'crossing-1','pedestrian_device_governs_route':True,
                'pedestrian_faces_vehicle_head':True,'sole_green_arrow_aspect':'green-left-arrow',
                'pedestrian_route_xy':route,'highway_boundary_xy':boundary}
        self.site_ref = ref('site.json', site)

    def tearDown(self):
        self.tmp.cleanup()

    def events(self, enter, walk):
        points = [-2,-1,1 if enter else -0.5,2 if enter else -0.5]
        return [{'frame':i,'sim_time_seconds':i*0.05,
                 'vehicle_head_id':'head-1','pedestrian_device_id':'ped-1',
                 'vehicle_head_lit_aspects':['green-left-arrow'],
                 'pedestrian_facing_vehicle_head':True,
                 'pedestrian_device_indication':'WALK' if walk and i>=1 else 'DONT_WALK',
                 'pedestrian_xy':[x,1]} for i,x in enumerate(points)]

    def run_case(self, suffix, enter, walk):
        events_ref = self.ref('events.json', self.events(enter,walk))
        case = mod.ASSIGNMENT + '__' + suffix
        return mod.measure_saved(self.root,self.site_ref,events_ref,case,4)

    def test_four_exact_timeline_cases(self):
        for suffix,enter,walk in [('arrow_wait',False,False),
                                  ('arrow_early_entry',True,False),
                                  ('arrow_walk_entry',True,True),
                                  ('arrow_walk_wait',False,True)]:
            with self.subTest(suffix=suffix):
                result = self.run_case(suffix,enter,walk)
                self.assertEqual(result['frame_count'],4)
                self.assertEqual(result['sole_green_arrow_frames'],4)
                self.assertFalse(result['physical_acceptance'])
                self.assertIsNone(result['legal_verdict'])

    def test_reject_walk_starting_only_at_entry(self):
        rows = self.events(True,False)
        rows[2]['pedestrian_device_indication'] = 'WALK'
        rows[3]['pedestrian_device_indication'] = 'WALK'
        ref = self.ref('events.json',rows)
        with self.assertRaisesRegex(mod.SourceError,'did not precede'):
            mod.measure_saved(self.root,self.site_ref,ref,mod.ASSIGNMENT+'__arrow_walk_entry',4)

    def test_reject_dropped_time_and_wrong_case(self):
        rows = self.events(True,False)
        rows[2]['sim_time_seconds']=0.2
        ref=self.ref('events.json',rows)
        with self.assertRaisesRegex(mod.SourceError,'20 Hz'):
            mod.measure_saved(self.root,self.site_ref,ref,mod.ASSIGNMENT+'__arrow_early_entry',4)
        with self.assertRaisesRegex(mod.SourceError,'entry behavior'):
            self.run_case('arrow_wait',True,False)

    def test_reject_unsealed_or_diagnostic_site(self):
        rows=self.events(False,False)
        ref=self.ref('events.json',rows)
        bad=dict(self.site_ref,sha256='0'*64)
        with self.assertRaisesRegex(mod.SourceError,'hash mismatch'):
            mod.measure_saved(self.root,bad,ref,mod.ASSIGNMENT+'__arrow_wait',4)
        site=json.loads((self.root/'site.json').read_text())
        site['source_kind']='diagnostic'
        site_ref=self.ref('site.json',site)
        with self.assertRaisesRegex(mod.SourceError,'diagnostic'):
            mod.measure_saved(self.root,site_ref,ref,mod.ASSIGNMENT+'__arrow_wait',4)

    def test_reject_source_escape(self):
        ref=self.ref('events.json',self.events(False,False))
        with self.assertRaisesRegex(mod.SourceError,'escapes'):
            mod.measure_saved(self.root,{'path':'../outside.json','sha256':'0'*64},
                              ref,mod.ASSIGNMENT+'__arrow_wait',4)


if __name__ == '__main__':
    unittest.main()
