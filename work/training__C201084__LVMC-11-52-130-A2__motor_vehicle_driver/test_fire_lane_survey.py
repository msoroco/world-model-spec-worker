"""CPU construction checks; the probe is a fake, never Native evidence."""
import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from fire_lane_survey import build
from native_survey import inspect

HERE = Path(__file__).resolve().parent


def fixture():
    return json.loads((HERE / 'draft-fire-lane-survey.json').read_text())


def fake_probe(xy):
    return {'map_name': 'pending_live_public_access_premises_map',
            'road_id': 17, 'lane_id': -1, 'drivable_access': True,
            'source_kind': 'synthetic_construction_probe'}


class SurveyTests(unittest.TestCase):
    def test_inside_outside_same_curb(self):
        result = build(fixture(), fake_probe)
        self.assertEqual(result['cases']['reference']['authored_zone_footprint_relation'], 'inside')
        self.assertEqual(result['cases']['contrast']['authored_zone_footprint_relation'], 'outside')
        self.assertEqual(result['capture_frames'], 600)
        self.assertFalse(result['posting_designation_verified'])
        self.assertFalse(result['physical_or_legal_completion_claimed'])

    def test_overlap_is_rejected(self):
        value = fixture()
        value['stop_footprints_xy_m']['contrast'] = value['stop_footprints_xy_m']['reference']
        with self.assertRaisesRegex(ValueError, 'isolate fire-lane footprint'):
            build(value, fake_probe)

    def test_posting_must_be_curb_adjacent(self):
        value = fixture()
        value['posted_sign_xy_m'] = [80, 80]
        with self.assertRaisesRegex(ValueError, 'not adjacent'):
            build(value, fake_probe)

    def test_live_access_and_same_road_required(self):
        def other_road(xy):
            result = fake_probe(xy)
            if xy[0] > 20:
                result['road_id'] = 18
            return result
        with self.assertRaisesRegex(ValueError, 'changes road identity'):
            build(fixture(), other_road)

    def test_capture_and_code_review_required(self):
        value = fixture()
        value['capture_frames'] = 120
        with self.assertRaisesRegex(ValueError, 'Thirty-second'):
            build(value, fake_probe)
        value = fixture()
        value['fire_code_designation_review'] = 'assumed_valid'
        with self.assertRaisesRegex(ValueError, 'source review'):
            build(value, fake_probe)

    def test_live_map_and_sign_actor_readback(self):
        value = fixture()
        value['map_name'] = 'TownFireLane'
        value['anchor_z_m'] = 0.0
        location = lambda x, y: SimpleNamespace(x=x, y=y, z=0.0)
        actor = SimpleNamespace(id=101, type_id='static.prop.fire_lane_sign',
            get_transform=lambda: SimpleNamespace(location=location(6, -1)))
        actors = SimpleNamespace(find=lambda ident: actor if ident == 101 else None)
        mapping = SimpleNamespace(name='TownFireLane',
            get_waypoint=lambda xy, **kwargs: SimpleNamespace(
                road_id=17, lane_id=-1,
                transform=SimpleNamespace(location=location(xy.x, xy.y))))
        world = SimpleNamespace(get_map=lambda: mapping, get_actors=lambda: actors)
        carla = SimpleNamespace(Location=lambda **kwargs: SimpleNamespace(**kwargs),
                                LaneType=SimpleNamespace(Driving=1))
        result = inspect(world, carla, value)
        self.assertEqual(result['sign_readback']['actor_id'], 101)
        self.assertFalse(result['original_sign_text_verified'])
        mapping.name = 'OtherTown'
        with self.assertRaisesRegex(ValueError, 'Live CARLA map differs'):
            inspect(world, carla, value)

    def test_live_sign_mismatch_rejected(self):
        value = fixture()
        value['map_name'] = 'TownFireLane'
        value['anchor_z_m'] = 0.0
        actor = SimpleNamespace(id=101, type_id='static.prop.fire_lane_sign',
            get_transform=lambda: SimpleNamespace(location=SimpleNamespace(x=12, y=12)))
        world = SimpleNamespace(get_map=lambda: SimpleNamespace(name='TownFireLane'),
                                get_actors=lambda: SimpleNamespace(find=lambda ident: actor))
        with self.assertRaisesRegex(ValueError, 'moved from surveyed location'):
            inspect(world, SimpleNamespace(), value)


if __name__ == '__main__':
    unittest.main()
