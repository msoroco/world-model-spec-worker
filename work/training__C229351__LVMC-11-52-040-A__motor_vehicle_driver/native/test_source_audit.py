import copy
import hashlib
import json
import tempfile
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from parking_measure import measure
from selected_plan import CASES, CELL
from source_audit import comparison_audit, extract, road_edge_context


class SourceAuditTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.survey = {
            'source_kind': 'original_native_road_edge_survey', 'fixed_cell': CELL,
            'map_name': 'source_test_map', 'roadway_boundary_source_id': 'road-edge-1',
            'edge_tangent_source_id': 'edge-1', 'lawful_traffic_source_id': 'lane-1',
            'parking_permission_source_id': 'authority-1',
            'roadway_class_source_id': 'native-map-1',
            'vehicle_identity_source_id': 'vehicle-1',
            'driver_identity_source_id': 'operator-1',
            'rest_activity_source_id': 'activity-review-1',
            'reviewed_source_sha256': 'a' * 64, 'reviewer': 'fixture-reviewer',
            'chapter_exception_status': 'unknown', 'chapter_exception_source_refs': [],
            'edge_tangent_xy': [1, 0], 'lawful_direction_xy': [1, 0],
            'spawn_xyz_yaw_deg': [0, 0, 0, 0], 'rest_xyz_m': [1, 0, 0],
            'vehicle_blueprint': 'vehicle.fixture',
        }
        self.survey_path = self.write('survey.json', self.survey)
        self.geometry = {
            'source_kind': 'original_native_road_geometry',
            'survey_sha256': self.sha(self.survey_path),
            'roadway_boundary_source_id': 'road-edge-1',
            'lawful_traffic_source_id': 'lane-1',
            'roadway_class': 'roadway', 'road_edge_identified': True,
            'edge_tangent_xy': [1, 0], 'lawful_traffic_direction_xy': [1, 0],
        }
        self.geometry_path = self.write('geometry.json', self.geometry)

    def sha(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def write(self, name, data):
        path = self.root / name
        path.write_text(json.dumps(data) + '\n')
        return path

    def sources(self, case):
        rows = [{'source_kind': 'original_native', 'case_id': case,
                 'native_frame': i, 'time_s': i * .05,
                 'ego_center_xy_m': [1.0, 0.0], 'ego_front_yaw_deg': 0,
                 'ego_speed_mps': 0, 'roadway_boundary_source_id': 'road-edge-1',
                 'lawful_traffic_source_id': 'lane-1'} for i in (1, 2)]
        images = [{'native_frame': i, 'time_s': i * .05,
                   'all_four_cameras_joined': True} for i in (1, 2)]
        native = self.root / (case + '.jsonl')
        video = self.root / (case + '-frames.jsonl')
        native.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        video.write_text(''.join(json.dumps(row) + '\n' for row in images))
        return native, video

    def test_exact_six_source_join_and_fixed_comparison(self):
        extracts, surveys, observed = {}, {}, {}
        for case in CASES:
            native, video = self.sources(case)
            item = extract(case, native, video, self.geometry_path, self.survey_path)
            extracts[case] = item
            surveys[case] = self.survey
            observed[case] = measure(item, road_edge_context(self.geometry_path))
        self.assertEqual(len(comparison_audit(extracts, surveys, observed)['comparisons']), 7)
        changed = copy.deepcopy(extracts)
        changed[next(iter(CASES))]['geometry_sha256'] = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'geometry not bound'):
            comparison_audit(changed, surveys, observed)
        missing = copy.deepcopy(observed)
        missing[next(iter(CASES))]['observations'][-1].pop('speed_mps')
        with self.assertRaisesRegex(ValueError, 'measured source value changed'):
            comparison_audit(extracts, surveys, missing)
        changed_observation = copy.deepcopy(observed)
        changed_observation[next(iter(CASES))]['observations'][-1]['edge_parallel_angle_deg'] = 20
        with self.assertRaisesRegex(ValueError, 'measured source value changed'):
            comparison_audit(extracts, surveys, changed_observation)

    def test_missing_camera_or_changed_geometry_rejected(self):
        case = next(iter(CASES))
        native, video = self.sources(case)
        rows = [json.loads(line) for line in video.read_text().splitlines()]
        rows[0]['all_four_cameras_joined'] = False
        video.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        with self.assertRaisesRegex(ValueError, 'four-camera'):
            extract(case, native, video, self.geometry_path, self.survey_path)
        changed = dict(self.geometry, edge_tangent_xy=[0, 1])
        self.write('geometry.json', changed)
        with self.assertRaisesRegex(ValueError, 'direction mismatch'):
            extract(case, native, video, self.geometry_path, self.survey_path)

    def test_joined_pose_runs_angle_measurement(self):
        case = next(iter(CASES))
        native, video = self.sources(case)
        item = extract(case, native, video, self.geometry_path, self.survey_path)
        observed = measure(item, road_edge_context(self.geometry_path))
        self.assertEqual(len(observed['observations']), 2)
        self.assertEqual(observed['observations'][0]['edge_parallel_angle_deg'], 0)
        self.assertIsNone(observed.get('legal_result'))


if __name__ == '__main__':
    unittest.main()
