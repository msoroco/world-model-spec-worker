"""Both-lane median geometry and mapped barrier source controls."""
import sys
import unittest
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from u_turn_227_divider import collect_native_dividers, measure_divider_candidate, select_227_candidate
from runner import PREFIX, check_config
from u_turn_finalizer import measure_mapped_divider


def waypoint(y,width,lane):
    transform=SimpleNamespace(location=SimpleNamespace(x=0,y=y),
                              get_forward_vector=lambda:SimpleNamespace(x=1,y=0))
    return SimpleNamespace(transform=transform,road_id=7,lane_id=lane,lane_width=width)


def scene(separation=8):
    return {'approach':waypoint(0,3,-1),'opposite':waypoint(separation,3,1)}


def barrier(y=4):
    return {'source_id':'GuardRail-0','label':'GuardRail',
            'vertices_xy_m':[[-3,y-.2],[3,y-.2],[3,y+.2],[-3,y+.2]]}


class DividerTests(unittest.TestCase):
    def test_opposing_lane_gap_and_mapped_barrier_retained_without_legal_claim(self):
        report=measure_divider_candidate(scene(),[barrier()])
        self.assertEqual(report['unoccupied_lane_edge_gap_m'],5)
        self.assertEqual(report['nearby_divider_boxes'][0]['source_id'],'GuardRail-0')
        self.assertIsNone(report['public_authority_opening_status'])
        self.assertFalse(report['actual_barrier_crossing_verified'])

    def test_cross_road_box_and_narrow_gap_do_not_select(self):
        narrow=scene(separation=3.5)
        report=measure_divider_candidate(narrow,[barrier(y=1.75)])
        self.assertLess(report['unoccupied_lane_edge_gap_m'],1)
        outside=measure_divider_candidate(scene(),[barrier(y=20)])
        self.assertEqual(outside['nearby_divider_boxes'],[])

    def test_native_barrier_boxes_and_candidate_search(self):
        class Box:
            def get_world_vertices(self,transform):
                return [SimpleNamespace(x=x,y=y) for x,y in barrier()['vertices_xy_m']]
        world=SimpleNamespace(get_map=lambda:object(),
                              get_level_bbs=lambda label:[Box()] if label=='GuardRail' else [])
        carla=SimpleNamespace(CityObjectLabel=SimpleNamespace(GuardRail='GuardRail',Walls='Walls',Fences='Fences'),
                              Transform=lambda:object())
        boxes=collect_native_dividers(world,carla)
        self.assertEqual(len(boxes),1)
        sites=[scene(separation=3.5),scene(separation=8)]
        def choose(mapping,**kwargs):
            index=kwargs['candidate_index']
            if index>=len(sites):raise ValueError('No requested Native opposing-lane U-turn pair')
            return sites[index]
        with patch('u_turn_construction.select_u_turn_scene',side_effect=choose):
            selected,report=select_227_candidate(world,carla)
        self.assertIs(selected,sites[1])
        self.assertEqual(report['candidate_index'],1)

    def test_227_case_config_is_carla_lazy(self):
        root=Path(__file__).resolve().parents[1]
        config=json.loads((root/'config.json').read_text())
        case_id=PREFIX+'prohibition_227'
        config['selected_case_id']=case_id
        config['case']['case_id']=case_id
        self.assertEqual(check_config(config),case_id)

    def test_saved_divider_geometry_is_recomputed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            report=measure_divider_candidate(scene(),[barrier()])
            (root/'divider.json').write_text(json.dumps({'divider_candidate':report}))
            (root/'context.json').write_text(json.dumps({
                'approach_road_id':7,'approach_lane_id':-1,'opposite_lane_id':1}))
            self.assertEqual(measure_mapped_divider(root/'divider.json',root/'context.json'),report)
            report['unoccupied_lane_edge_gap_m']=100
            (root/'divider.json').write_text(json.dumps({'divider_candidate':report}))
            with self.assertRaisesRegex(ValueError,'geometry differs'):
                measure_mapped_divider(root/'divider.json',root/'context.json')


if __name__=='__main__':
    unittest.main()
