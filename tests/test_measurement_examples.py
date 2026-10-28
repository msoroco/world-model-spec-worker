import importlib.util
import unittest
from pathlib import Path


path=Path(__file__).resolve().parents[1]/'examples/measurement/geometry.py'
spec=importlib.util.spec_from_file_location('measurement_examples',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class MeasurementExamplesTests(unittest.TestCase):
    def test_centerline_uses_all_vertices(self):
        value=module.centerline_offset((1,0),(0,0),[(0,-2),(2,-2),(2,1),(0,1)])
        self.assertEqual(value['minimum_m'],-2)
        self.assertEqual(value['maximum_m'],1)

    def test_nearest_clear_is_not_first_clear(self):
        samples=[{'point_xy_m':[-12,0],'distance_to_intersection_m':12,'clear_ray':True,'frame':1},
                 {'point_xy_m':[-4,0],'distance_to_intersection_m':4,'clear_ray':True,'frame':2},
                 {'point_xy_m':[-2,0],'distance_to_intersection_m':2,'clear_ray':False,'frame':3}]
        self.assertEqual(module.nearest_visible_point(samples)['frame'],2)


if __name__=='__main__':unittest.main()
