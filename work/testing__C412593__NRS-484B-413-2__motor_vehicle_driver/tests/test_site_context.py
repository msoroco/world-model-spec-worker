import hashlib
import importlib.util
import tempfile
import unittest
import sys
from types import SimpleNamespace as NS
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from right_turn_construction import spawn_right_turn_vehicle
spec=importlib.util.spec_from_file_location('site_context',HERE/'site_context.py')
site=importlib.util.module_from_spec(spec)
spec.loader.exec_module(site)


class SiteContextTests(unittest.TestCase):
    def fixture(self,root):
        for name in ('district.txt','zone.txt'):
            (root/name).write_text('synthetic review source for '+name+'\n')
        ref=lambda name:{'path':name,'sha256':hashlib.sha256((root/name).read_bytes()).hexdigest(),
                         'reviewer':'fixture reviewer','review_method':'read original source'}
        packet={'native_map_id':'fixture-map',
                'district':{'type':'business','frontage_facts':'reviewed road frontage',
                            'building_use_facts':'reviewed business use','source':ref('district.txt')},
                'freight_loading_zone':{'designation':'freight_loading_zone','road_id':1,
                       'marking_or_sign_evidence':'reviewed original zone sign',
                       'polygon_xy_m':[[35,3],[45,3],[45,5],[35,5]],
                       'minimum_centerline_clearance_m':2,'maximum_route_distance_m':6,
                       'source':ref('zone.txt')}}
        route={'native_map_id':'fixture-map','approach_road_id':1,
               'approach_points_xy_m':[[0,0],[100,0]],
               'outgoing_points_xy_m':[[100,0],[100,-20]]}
        return packet,route

    def test_source_bound_adjacent_zone_and_district(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);packet,route=self.fixture(root)
            observed=site.validate_site(packet,route,root)
            self.assertEqual(observed['district_type'],'business')
            self.assertEqual(observed['route_zone_distance_m'],3)
            self.assertIs(observed['physical_acceptance_claimed'],False)

    def test_rejects_changed_sources_and_unrelated_or_intruding_zone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);packet,route=self.fixture(root)
            (root/'district.txt').write_text('changed\n')
            with self.assertRaisesRegex(ValueError,'Changed district'):
                site.validate_site(packet,route,root)
            packet,route=self.fixture(root)
            packet['freight_loading_zone']['polygon_xy_m']=[[35,-1],[45,-1],[45,1],[35,1]]
            with self.assertRaisesRegex(ValueError,'intrudes'):
                site.validate_site(packet,route,root)
            packet['freight_loading_zone']['polygon_xy_m']=[[35,30],[45,30],[45,32],[35,32]]
            with self.assertRaisesRegex(ValueError,'unrelated'):
                site.validate_site(packet,route,root)

    def test_native_spawn_checks_site_and_cleans_up_on_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);packet,_=self.fixture(root)
            wp=lambda x,y,road: NS(road_id=road,lane_id=-1,transform=NS(location=NS(x=x,y=y)))
            approach=[wp(x,0,1) for x in range(0,101,2)]
            outgoing=[wp(100,-2,2),wp(100,-4,2)]
            destroyed=[]
            actor=NS(get_location=lambda:approach[0].transform.location,
                     destroy=lambda:destroyed.append(True))
            native_map=NS(name='fixture-map',get_waypoint=lambda location,project_to_road:approach[0])
            world=NS(try_spawn_actor=lambda blueprint,transform:actor,
                     get_map=lambda:native_map)
            with spawn_right_turn_vehicle(world,'fixture blueprint',approach,outgoing,
                                          site_packet=packet,site_source_root=root) as built:
                self.assertEqual(built['site_context']['route_zone_distance_m'],3)
            self.assertEqual(destroyed,[True])
            packet['freight_loading_zone']['polygon_xy_m']=[[35,-1],[45,-1],[45,1],[35,1]]
            with self.assertRaisesRegex(ValueError,'intrudes'):
                with spawn_right_turn_vehicle(world,'fixture blueprint',approach,outgoing,
                                              site_packet=packet,site_source_root=root):
                    pass
            self.assertEqual(destroyed,[True,True])

    def test_disjoint_collinear_edges_do_not_intersect(self):
        self.assertFalse(site._intersects((0,0),(10,0),(20,0),(30,0)))

    def test_rejects_map_or_unsourced_designation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);packet,route=self.fixture(root)
            packet['native_map_id']='other-map'
            with self.assertRaisesRegex(ValueError,'map identities'):
                site.validate_site(packet,route,root)
            packet,route=self.fixture(root)
            packet['freight_loading_zone']['marking_or_sign_evidence']=''
            with self.assertRaisesRegex(ValueError,'designation'):
                site.validate_site(packet,route,root)


if __name__=='__main__':
    unittest.main()
