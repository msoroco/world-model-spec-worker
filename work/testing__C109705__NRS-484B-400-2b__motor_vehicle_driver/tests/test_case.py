import importlib.util, json, unittest, xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
class ExactCase(unittest.TestCase):
    def test_connected_turn_and_opposing_lanes(self):
        tree=ET.parse(ROOT/'scene.xodr')
        roads={r.attrib['id']:r for r in tree.findall('road')}
        self.assertIn('13',roads)
        self.assertIsNotNone(roads['13'].find('planView/geometry/arc'))
        self.assertEqual({1,2,3,4,11,12,13},{int(k) for k in roads})
        self.assertEqual([],tree.findall('.//signal'))
        self.assertTrue(any(c.attrib['incomingRoad']=='1' and c.attrib['connectingRoad']=='13' for c in tree.findall('junction/connection')))
        for index in ('1','2','3','4'):
            self.assertIsNotNone(roads[index].find("lanes/laneSection/left/lane[@id='1']"))
            self.assertIsNotNone(roads[index].find("lanes/laneSection/right/lane[@id='-1']"))
    def test_all_body_vertices_measured(self):
        road={'exit_direction_xy':[0,-1],'exit_centerline_point_xy_m':[0,0],'intersection_polygon_xy_m':[[-7,-7],[7,-7],[7,7],[-7,7]]}
        rows=[{'frame':i,'time_s':i*.05,'body_vertices_xy_m':[[.7,-10],[.7,-9],[2.3,-10],[2.3,-9]]} for i in (1,2,3)]
        output=module('analyze').exit_centerline_offset(road,rows)
        self.assertEqual(output['exit_frame'],1)
        self.assertEqual(len(output['signed_vertex_distances_m']),4)
        self.assertEqual(output['minimum_m'],.7)
    def test_missing_case_source_rejected(self):
        with self.assertRaisesRegex(ValueError,'Missing required source: road_geometry.json'):
            module('analyze').source(ROOT/'missing-fixture-directory','road_geometry.json')
if __name__=='__main__':unittest.main()
