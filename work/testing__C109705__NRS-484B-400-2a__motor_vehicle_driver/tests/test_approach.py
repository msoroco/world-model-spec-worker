import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from approach import body_position, compare, measure, validate_context
from construction import build, control


def context(kind='marked'):
    return {'law_id': 'NRS-484B-400-2a', 'cell_id': 'C109705',
            'maneuver': 'left_turn', 'control': 'centerline',
            'public_highway_source': 'original map and public-access review',
            'intersecting_roads': [
                {'road_id': 'approach', 'alley': False, 'lanes': [
                    {'from_xy_m': [-40, -2], 'to_xy_m': [0, -2]},
                    {'from_xy_m': [0, 2], 'to_xy_m': [-40, 2]}]},
                {'road_id': 'departure', 'alley': False, 'lanes': [
                    {'from_xy_m': [2, -40], 'to_xy_m': [2, 0]},
                    {'from_xy_m': [-2, 0], 'to_xy_m': [-2, -40]}]}],
            'approach_road_id': 'approach', 'departure_road_id': 'departure',
            'approach_centerline_xy_m': [[-40, 0], [0, 0]],
            'approach_half_width_m': 4.0, 'centerline_kind': kind,
            'camera_plan': 'four cameras, 20 Hz', 'duration_s': 45,
            'controller_policy': 'fixed left-turn policy'}


def body(y):
    return [[-20, y], [-19, y], [-19, y-1], [-20, y-1]]


class ApproachTests(unittest.TestCase):
    def test_two_directional_both_roads(self):
        validate_context(context())
        c = context(); c['intersecting_roads'][1]['lanes'] = c['intersecting_roads'][1]['lanes'][:1]
        with self.assertRaisesRegex(ValueError, 'two-directional'):
            validate_context(c)

    def test_reject_same_direction_and_wrong_road(self):
        c = context()
        c['intersecting_roads'][0]['lanes'][1]['from_xy_m'] = [-40, 2]
        c['intersecting_roads'][0]['lanes'][1]['to_xy_m'] = [0, 2]
        with self.assertRaisesRegex(ValueError, 'opposing'):
            validate_context(c)
        c = context(); c['departure_road_id'] = 'approach'
        with self.assertRaisesRegex(ValueError, 'left turn'):
            validate_context(c)

    def test_full_body_right_half_and_crossing(self):
        self.assertEqual(body_position(context(), body(-.7))['all_body_in_right_half'], True)
        self.assertEqual(body_position(context(), body(.2))['all_body_in_right_half'], False)
        self.assertEqual(body_position(context(), body(-4.1))['all_body_in_right_half'], False)

    def test_original_source_hash_and_preentry_window(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            (path/'intersection-context.json').write_text(json.dumps(context()))
            rows = [dict(frame=i, time_s=i*.05, road_id='approach', phase='approach',
                         ego_body_vertices_xy_m=body(-.6-i*.1)) for i in range(3)]
            rows.append(dict(frame=3, time_s=.15, road_id='departure', phase='turn',
                             ego_body_vertices_xy_m=body(.3)))
            (path/'approach-history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            acquisition = {name: {'kind':'original_native',
                                  'sha256':hashlib.sha256((path/name).read_bytes()).hexdigest()}
                           for name in ('intersection-context.json','approach-history.jsonl')}
            (path/'acquisition.json').write_text(json.dumps(acquisition))
            result = measure(path)
            self.assertEqual(result['approach_frames'], [0,1,2])
            self.assertTrue(result['all_sampled_body_in_right_half'])
            self.assertEqual(result['legal_nearest_portion_verdict'], 'unresolved')
            (path/'approach-history.jsonl').write_text('')
            with self.assertRaisesRegex(ValueError, 'stale original'):
                measure(path)

    def test_comparison_fixed_conditions(self):
        with tempfile.TemporaryDirectory() as temp:
            a,b = Path(temp)/'a.json',Path(temp)/'b.json'
            c = context()
            a.write_text(json.dumps({'context':c,'measurement':{'source_sha256':{'a':'1'},
                                       'nearest_body_edge_range_m':[.5,.9]}}))
            b.write_text(json.dumps({'context':c,'measurement':{'source_sha256':{'a':'2'},
                                       'nearest_body_edge_range_m':[.8,1.1]}}))
            self.assertAlmostEqual(compare(a,b)['signed_difference_m'], .3)
            bad = context(); bad['controller_policy'] = 'changed'
            b.write_text(json.dumps({'context':bad,'measurement':{'source_sha256':{'a':'2'},
                                       'nearest_body_edge_range_m':[.8,1.1]}}))
            with self.assertRaisesRegex(ValueError, 'fixed condition'):
                compare(a,b)

    def test_four_case_construction_and_controller(self):
        prefix='testing__C109705__NRS-484B-400-2a__motor_vehicle_driver__'
        packet={'context':context(),'source_sha256':'a'*64,'map_name':'surveyed-map',
                'left_turn_route_waypoint_ids':[101,102,201],
                'ego_blueprint_id':'vehicle.test','camera_plan':'four cameras, 20 Hz'}
        near=build(prefix+'near_centerline',packet)
        far=build(prefix+'farther_from_centerline',packet)
        self.assertLess(near['approach_target_lateral_offset_m'],far['approach_target_lateral_offset_m'])
        self.assertEqual(near['left_turn_route_waypoint_ids'],far['left_turn_route_waypoint_ids'])
        packet['context']=context('imaginary_equidistant')
        build(prefix+'imaginary_near_centerline',packet)
        build(prefix+'imaginary_farther_from_centerline',packet)
        with self.assertRaisesRegex(ValueError,'case/centerline'):
            build(prefix+'near_centerline',packet)
        self.assertGreater(control([0,0],0,[8,1],3)['throttle'],0)
        self.assertEqual(control([0,0],0,[.1,0],3)['brake'],1.0)


if __name__ == '__main__':
    unittest.main()
