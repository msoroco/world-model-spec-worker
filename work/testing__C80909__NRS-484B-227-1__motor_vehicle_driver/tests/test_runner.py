import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('c80909_runner', ROOT / 'runner.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class RunnerTests(unittest.TestCase):
    def plan(self, root):
        source = root / 'review.txt'
        source.write_text('Reviewed source fixture for CPU contract test.\n')
        context = {'native_map_id': 'TownX',
                   'divided_highway_source': 'review.txt',
                   'roadway_boundaries_source': 'review.txt',
                   'opening_geometry_source': 'review.txt',
                   'barrier_actors_source': 'review.txt',
                   'other_vehicle_source': 'review.txt',
                   'right_hand_roadway_xy_m': [[0,-10],[30,-10],[30,-2],[0,-2]],
                   'destination_roadway_xy_m': [[0,2],[30,2],[30,10],[0,10]],
                   'dividing_space_xy_m': [[0,-2],[30,-2],[30,2],[0,2]],
                   'opening_xy_m': [[10,-2],[20,-2],[20,2],[10,2]]}
        plan = {'assignment_id': runner.ASSIGNMENT, 'selected_case_id': runner.CASE,
                'source_review_status': 'reviewed_original_map_and_cameras',
                'rate_hz': 20, 'frames': 600, 'native_map_name': 'TownX',
                'source_refs': [{'path': 'review.txt',
                                 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}],
                'divider_context': context,
                'camera_poses': {name: [0,0,3,0,0,0] for name in runner.CAMERAS},
                'barrier_sections': [{'blueprint_id': 'barrier', 'pose': [0,0,0,0,0,0]}]*2,
                'ego_spawn_pose': [5,-5,0,0,0,0],
                'other_spawn_pose': [26,-5,0,0,0,0],
                'ego_route_xy_m': [[5,-5],[15,-5],[15,0],[15,5]],
                'ego_body_radius_m': 1.0,
                'other_route_xy_m': [[26,-5],[27,-5]],
                'vehicle_blueprint_id': 'vehicle.test',
                'barrier_axis_xy': [1,0],
                'native_spawn_lanes': {'ego': {'road_id': 1, 'lane_id': 1},
                                       'other': {'road_id': 1, 'lane_id': 1}}}
        packet = root / 'site.json'
        packet.write_text(json.dumps(plan))
        return packet, source, plan

    def test_reviewed_source_bound_opening_plan_and_negative_mutations(self):
        with tempfile.TemporaryDirectory() as directory:
            packet, source, plan = self.plan(Path(directory))
            self.assertEqual(runner.load_plan(packet)['frames'], 600)
            source.write_text('changed')
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                runner.load_plan(packet)
            packet, source, plan = self.plan(Path(directory))
            plan['source_review_status'] = 'unreviewed'
            packet.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'Reviewed original'):
                runner.load_plan(packet)
            plan['source_review_status'] = 'reviewed_original_map_and_cameras'
            plan['ego_route_xy_m'] = [[5,-5],[5,-3],[5,0],[5,5]]
            packet.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'blocked dividing space'):
                runner.load_plan(packet)


if __name__ == '__main__': unittest.main()
