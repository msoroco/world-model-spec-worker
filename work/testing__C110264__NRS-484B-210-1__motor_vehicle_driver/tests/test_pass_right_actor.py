"""CPU fakes for source-map projection and original actor readback."""
import copy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as N

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pass_right_actor import make_actor_sampler, project_actor
from test_pass_right_route import map_packet


def packet():
    source = map_packet()
    for row in source['cross_sections']:
        row['world_center_xy_m'] = [row['station_m'], 10.0]
    return source


def pose(x, y, yaw=0):
    return N(location=N(x=x, y=y), rotation=N(yaw=yaw))


class FakeActor:
    def __init__(self, actor_id, light=0):
        self.id = actor_id
        self.light = light

    def get_light_state(self):
        return self.light


class FakeSnapshotActor:
    def __init__(self, x, y, yaw, vx):
        self.transform = pose(x, y, yaw)
        self.velocity = N(x=vx, y=0)

    def get_transform(self):
        return self.transform

    def get_velocity(self):
        return self.velocity


class FakeSnapshot:
    def __init__(self, rows):
        self.rows = rows

    def find(self, actor_id):
        return self.rows.get(actor_id)


class TestOriginalActorSampler(unittest.TestCase):
    def test_source_station_right_positive_and_signal_readback(self):
        source = packet()
        ego, target = FakeActor(7), FakeActor(8, light=0x20)
        snapshot = FakeSnapshot({7: FakeSnapshotActor(59, 7, 0, 8),
                                 8: FakeSnapshotActor(60, 10, 12, 3)})
        measured = make_actor_sampler(source, ego, target, left_signal_mask=0x20)(snapshot)
        self.assertAlmostEqual(measured['ego_s_m'], 59)
        self.assertAlmostEqual(measured['ego_lateral_m'], 3)
        self.assertAlmostEqual(measured['target_lateral_m'], 0)
        self.assertEqual(measured['target_heading_deg'], -12)
        self.assertTrue(measured['target_left_signal'])
        self.assertTrue(measured['ego_paved'])
        self.assertEqual(measured['ego_speed_mps'], 8)
        target.light = 0
        self.assertFalse(make_actor_sampler(source, ego, target, left_signal_mask=0x20)(snapshot)['target_left_signal'])

    def test_unpaved_and_missing_actor_are_observed_not_requested(self):
        source = packet()
        ego, target = FakeActor(7), FakeActor(8)
        sampler = make_actor_sampler(source, ego, target, left_signal_mask=0x20)
        snapshot = FakeSnapshot({7: FakeSnapshotActor(59, 5.9, 0, 8),
                                 8: FakeSnapshotActor(60, 10, 0, 3)})
        self.assertFalse(sampler(snapshot)['ego_paved'])
        del snapshot.rows[8]
        with self.assertRaisesRegex(ValueError, 'missing from original'):
            sampler(snapshot)

    def test_rejects_unsourced_world_frame_and_ambiguous_projection(self):
        source = packet()
        bad = copy.deepcopy(source)
        del bad['cross_sections'][2]['world_center_xy_m']
        with self.assertRaisesRegex(ValueError, 'world XY'):
            project_actor(bad, N(x=50, y=10), 0)
        bad = copy.deepcopy(source)
        bad['cross_sections'][2]['world_center_xy_m'] = [100, 10]
        with self.assertRaisesRegex(ValueError, 'polyline length'):
            project_actor(bad, N(x=50, y=10), 0)
        with self.assertRaisesRegex(ValueError, 'too far'):
            project_actor(source, N(x=50, y=100), 0)

    def test_rejects_wrong_signal_mask_and_actor_identity(self):
        source = packet()
        with self.assertRaisesRegex(ValueError, 'bit mask'):
            make_actor_sampler(source, FakeActor(7), FakeActor(8), left_signal_mask=0)
        with self.assertRaisesRegex(ValueError, 'distinct live actor'):
            make_actor_sampler(source, FakeActor(7), FakeActor(7), left_signal_mask=0x20)


if __name__ == '__main__':
    unittest.main()
