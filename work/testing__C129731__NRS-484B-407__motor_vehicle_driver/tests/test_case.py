import importlib.util, json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'))
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj

class ExactCase(unittest.TestCase):
    def test_offline_scene(self):
        module('runner').check()

    def test_law_specific_measurement(self):
        analysis=module('analyze');cfg=json.loads((ROOT/'config.json').read_text())
        context=cfg['authored_context']
        rows=[]
        for i in range(3):
            for direction in ('forward','reverse'):
                rows.append({'frame':i+1,'time_s':(i+1)*.05,'point_xy_m':[i,0],
                             'distance_to_intersection_m':5-i,'clear_ray':i>0,
                             'ego_speed_mps':2-i*.2,'ego_inside':False,
                             'other_inside':i>0,'other_obligated':False,
                             'other_distance_to_conflict_m':12-i,'other_speed_mps':4,
                             'approach_direction':direction,'approach_distance_m':152.4-i,
                             'heading_deg':i*30,'ego_width_m':2.5,'other_width_m':2.5,
                             'body_gap_m':150+i,'same_lane':True,'overtaking':False,
                             'backing':True,'body_crosswalk_overlap_m2':.5+i*.5})
        for measurement in cfg['measurement_specs']:
            value=getattr(analysis,measurement['method'])(context,rows)
            self.assertIsInstance(value,dict)
            self.assertTrue(value)
        if cfg['mode']=='yield_257_1':
            observed=analysis.nearest_visible_point(context,rows)
            self.assertEqual(observed['distance_to_intersection_m'],3)
        if cfg['mode']=='trucks_127_2':
            observed=analysis.following_gap(context,rows)
            self.assertAlmostEqual(observed['samples'][0]['gap_ft'],150/0.3048)
        if cfg['mode']=='backing_113_2':
            observed=analysis.simultaneous_backing_overlap(context,rows)
            self.assertTrue(all(x['backing'] and x['body_crosswalk_overlap_m2']>0 for x in observed['samples']))

    def test_negative_case_source(self):
        with self.assertRaisesRegex(ValueError,'Missing required source: case_observations.jsonl'):
            module('analyze').read(ROOT/'missing','case_observations.jsonl')

if __name__=='__main__':unittest.main()
