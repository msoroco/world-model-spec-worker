"""Business-district frontage geometry and provenance controls."""
import sys
import unittest
import json
import tempfile
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from u_turn_403_3_frontage import FRONTAGE_M, WINDOW_M, collect_native_buildings, measure_frontage, select_403_3_candidate
from u_turn_finalizer import measure_built_frontage


def building(name, start, end, side, use=None, citation=None):
    y0,y1 = (5.0,10.0) if side=='left' else (-10.0,-5.0)
    return {'source_id':name,
            'vertices_xy_m':[[start,y0],[end,y0],[end,y1],[start,y1]],
            'use_class':use,'use_source_ref':citation}


class FrontageTests(unittest.TestCase):
    def test_six_hundred_foot_window_and_sourced_frontage(self):
        buildings = [building('a',-60,0,'left','business','source-a'),
                     building('b',-10,40,'left','business','source-b'),
                     building('c',0,30,'right','industrial','source-c')]
        report = measure_frontage(buildings,(0,0),(1,0))
        self.assertEqual(report['window_m'],WINDOW_M)
        self.assertEqual(report['qualifying_frontage_m'],FRONTAGE_M)
        self.assertAlmostEqual(report['frontage_by_side']['left']['sourced_qualifying_use']['frontage_m'],100)
        self.assertAlmostEqual(report['combined_sourced_qualifying_use']['frontage_m'],130)
        self.assertIsNone(report['business_district_legal_judgment'])
        self.assertIsNone(report['intersection_exception_status'])

    def test_unknown_building_use_does_not_become_qualifying(self):
        report = measure_frontage([building('unknown',-75,75,'right')],(0,0),(1,0))
        self.assertEqual(report['combined_built']['frontage_m'],150)
        self.assertEqual(report['combined_sourced_qualifying_use']['frontage_m'],0)

    def test_unsourced_use_and_center_crossing_rejected(self):
        with self.assertRaisesRegex(ValueError,'source'):
            measure_frontage([building('unsourced',-50,50,'left','business')],(0,0),(1,0))
        crossing = building('crossing',-20,20,'left')
        crossing['vertices_xy_m'][2][1] = -1
        with self.assertRaisesRegex(ValueError,'crosses'):
            measure_frontage([crossing],(0,0),(1,0))

    def test_reverse_heading_swaps_sides_but_not_total(self):
        items = [building('a',-40,40,'left','business','source-a')]
        forward = measure_frontage(items,(0,0),(1,0))
        reverse = measure_frontage(items,(0,0),(-1,0))
        self.assertEqual(forward['frontage_by_side']['left']['built']['frontage_m'],80)
        self.assertEqual(reverse['frontage_by_side']['right']['built']['frontage_m'],80)

    def test_native_building_box_collection_keeps_use_unknown(self):
        class Box:
            def __init__(self,x):
                self.location=SimpleNamespace(x=x,y=6)
                self.x=x

            def get_world_vertices(self,transform):
                return [SimpleNamespace(x=self.x+dx,y=y)
                        for dx,y in ((-4,5),(4,5),(4,10),(-4,10))]

        world=SimpleNamespace(get_level_bbs=lambda label:[Box(20),Box(400)])
        carla=SimpleNamespace(CityObjectLabel=SimpleNamespace(Buildings='Buildings'),
                              Transform=lambda:object())
        buildings=collect_native_buildings(world,carla,(0,0))
        self.assertEqual(len(buildings),1)
        self.assertEqual(buildings[0]['source_id'],'building-box-0')
        self.assertIsNone(buildings[0]['use_class'])

    def test_candidate_selector_requires_built_frontage_without_claiming_use(self):
        def waypoint(x):
            transform=SimpleNamespace(location=SimpleNamespace(x=x,y=0),
                                      get_forward_vector=lambda:SimpleNamespace(x=1,y=0))
            return SimpleNamespace(transform=transform,is_junction=False)

        scenes=[{'approach':waypoint(0)},{'approach':waypoint(200)}]
        def get_scene(mapping,**kwargs):
            index=kwargs['candidate_index']
            if index>=len(scenes):
                raise ValueError('No requested Native opposing-lane U-turn pair')
            return scenes[index]
        def get_buildings(world,carla,turn_xy,**kwargs):
            length=50 if turn_xy[0]==0 else 100
            return [building('candidate',turn_xy[0]-length/2,
                             turn_xy[0]+length/2,'left')]
        world=SimpleNamespace(get_map=lambda:object(),get_level_bbs=lambda label:[])
        carla=SimpleNamespace(CityObjectLabel=SimpleNamespace(Buildings='Buildings'))
        with patch('u_turn_construction.select_u_turn_scene',side_effect=get_scene), patch(
                'u_turn_403_3_frontage.collect_native_buildings',side_effect=get_buildings):
            selected,report=select_403_3_candidate(world,carla)
        self.assertIs(selected,scenes[1])
        self.assertEqual(report['candidate_index'],1)
        self.assertEqual(report['combined_built']['frontage_m'],100)
        self.assertEqual(report['combined_sourced_qualifying_use']['frontage_m'],0)
        self.assertIsNone(report['business_district_legal_judgment'])

    def test_saved_frontage_recalculates_original_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            report=measure_frontage([building('a',-50,50,'left')],(0,0),(1,0))
            report.update({'road_id':7,'approach_lane_id':-1,
                           'opposite_lane_id':1,'site_is_junction':False})
            context={'approach_road_id':7,'approach_lane_id':-1,
                     'opposite_lane_id':1}
            source=root/'frontage.json'
            (root/'context.json').write_text(json.dumps(context))
            source.write_text(json.dumps({'built_frontage_candidate':report}))
            self.assertEqual(measure_built_frontage(source,root/'context.json'),report)
            report['combined_built']['frontage_m']=1000
            source.write_text(json.dumps({'built_frontage_candidate':report}))
            with self.assertRaisesRegex(ValueError,'frontage differs'):
                measure_built_frontage(source,root/'context.json')


if __name__=='__main__':
    unittest.main()
