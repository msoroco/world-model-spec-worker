"""Small source-shaped tests; these rows are never an original Native run."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from delivery_audit import (VIEW_SUBJECTS, check_access_review,
                            check_native_boundary, check_original_rows,
                            check_pixel_review, check_physical_result)


class DeliveryAuditBoundaryTest(unittest.TestCase):
    def test_original_physical_result_waits_for_access_review(self):
        source={'native_samples.jsonl':'source','road_geometry.json':'map'}
        result={'case_id':'case','provenance_kind':'native','accepted':False,
                'legal_verdict_claimed':False,'maneuver_completed':True,
                'setup_confirmed':False,
                'physical_checks':{name:{'status':status,'sources':source}
                    for name,status in [('setup','unverified'),('target','met'),
                                        ('maneuver','met'),('attempt','met')]}}
        check_physical_result(result,'case')
        result['provenance_kind']='synthetic_fixture'
        with self.assertRaisesRegex(ValueError,'Physical completion'):
            check_physical_result(result,'case')
        result['provenance_kind']='native'
        result['physical_checks']['maneuver']['status']='not_met'
        with self.assertRaisesRegex(ValueError,'Physical completion'):
            check_physical_result(result,'case')

    def make_rows(self, folder, synthetic=False):
        sample = [
            {"time_s": i / 20, "native_frame": i + 100,
             "native_body_xy_m": [[-2, -3], [-2, -1], [2, -1], [2, -3]],
             "native_center_xy_m": [0, -2], "native_forward_xy": [1, 0],
             "native_road_id": 1, "native_lane_id": -1,
             "speed_mps": 0.0,
             "speed_provenance": "synthetic_native_sample" if synthetic else "native_velocity_readback"}
            for i in range(2)]
        vertices = [[-2, -3, 0], [-2, -1, 0], [2, -1, 0], [2, -3, 0]]
        values = {
            "trace.jsonl": [{"frame": s["native_frame"], "time_s": s["time_s"],
                             "position": {"x": 0, "y": -2}, "speed_mps": 0.0,
                             "speed_provenance": s["speed_provenance"]} for s in sample],
            "capture/evidence.jsonl": [
                {"original_frame": s["native_frame"], "recording_time_s": s["time_s"],
                 "ego": {"speed_provenance": s["speed_provenance"],
                         "position_m": [0, -2, 0], "speed_mps": 0.0,
                         "body_vertices_m": vertices}}
                for s in sample],
            "video_frames.jsonl": [
                {"native_frame": s["native_frame"], "carla_frame": s["native_frame"],
                 "video_frame": i, "time_s": s["time_s"]}
                for i, s in enumerate(sample)],
            "native_samples.jsonl": sample,
            "body_history.jsonl": [
                {"frame": s["native_frame"], "time_s": s["time_s"],
                 "body_vertices_m": vertices}
                for s in sample],
        }
        for name, rows in values.items():
            target = folder / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("".join(json.dumps(row) + "\n" for row in rows))

    def test_source_join_and_synthetic_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            self.make_rows(folder)
            self.assertEqual(check_original_rows(folder, 2)["frames"], 2)
            self.make_rows(folder, synthetic=True)
            with self.assertRaisesRegex(ValueError, "Synthetic diagnostic"):
                check_original_rows(folder, 2)

    def test_missing_and_mismatched_native_rows_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            self.make_rows(folder)
            (folder / "native_samples.jsonl").unlink()
            with self.assertRaisesRegex(ValueError, "Missing original source"):
                check_original_rows(folder, 2)
            self.make_rows(folder)
            source = folder / "native_samples.jsonl"
            rows = [json.loads(line) for line in source.read_text().splitlines()]
            rows[1]["native_frame"] = 999
            source.write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "frame join"):
                check_original_rows(folder, 2)

    def test_cross_source_pose_velocity_and_lane_disagreement_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            self.make_rows(folder)
            for filename, mutate, error in (
                ("trace.jsonl", lambda row: row.update(speed_mps=4), "velocity differs"),
                ("capture/evidence.jsonl", lambda row: row["ego"].update(position_m=[8, -2, 0]), "pose or velocity differs"),
                ("native_samples.jsonl", lambda row: row.pop("native_lane_id"), "lane missing"),
            ):
                self.make_rows(folder)
                path = folder / filename
                records = [json.loads(line) for line in path.read_text().splitlines()]
                mutate(records[0])
                path.write_text("".join(json.dumps(row) + "\n" for row in records))
                with self.subTest(filename=filename), self.assertRaisesRegex(ValueError, error):
                    check_original_rows(folder, 2)

    def test_unsealed_attempt_rejected_before_saved_result(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            with self.assertRaisesRegex(ValueError, "Missing sealed Native capture"):
                check_native_boundary(folder, folder, folder / "owner.json",
                                      "case", "0" * 64)

    def test_actual_pixel_review_requires_all_byte_bound_views(self):
        import hashlib
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            names = ('overview', 'approach', 'reference_corner', 'driver_reference')
            for name in names:
                (folder / (name + '.mkv')).write_bytes(name.encode())
            primary = folder / 'primary.mkv'
            primary.write_bytes(b'primary')
            digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
            review = {'format':'c10014-original-source-pixel-review',
                      'case_id':'case', 'frames':480, 'reviewer':'test reviewer',
                      'method':'source-shaped unit test only',
                      'source_kind':'source_shaped_unit_test',
                      'primary_sha256':digest(primary),
                      'views':{name:{'video_sha256':digest(folder/(name+'.mkv')),
                                     'subjects_visible':sorted(VIEW_SUBJECTS[name]),
                                     'reviewed_stationary_frames':40,
                                     'limitations':[]}
                               for name in names}}
            path = folder / 'pixel-review.json'
            path.write_text(json.dumps(review))
            self.assertEqual(check_pixel_review(path,'case',folder,primary,
                                                test_shape=True)['reviewer'],
                             'test reviewer')
            review['views']['overview']['video_sha256'] = '0'*64
            path.write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError, 'Actual source pixels'):
                check_pixel_review(path,'case',folder,primary,test_shape=True)

    def test_property_access_review_requires_independent_source_hash(self):
        import hashlib
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            geometry = folder / 'road_geometry.json'
            geometry.write_text(json.dumps({'native_map_sha256':'native-map'}))
            property_source = folder / 'property-source.txt'
            property_source.write_text('source-shaped unit test only')
            digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
            review = {'format':'c10014-original-access-review',
                      'case_id':'case','source_kind':'source_shaped_unit_test',
                      'reviewer':'test reviewer','method':'schema test only',
                      'property_access_id':'unit-access',
                      'road_geometry_sha256':digest(geometry),
                      'native_map_sha256':'native-map',
                      'alley_design_confirmed':True,
                      'abutting_property_access_confirmed':True,
                      'entrance_boundary_confirmed':True,
                      'property_source':{'path':str(property_source),
                                         'sha256':digest(property_source)}}
            path = folder / 'access-review.json'
            path.write_text(json.dumps(review))
            self.assertEqual(check_access_review(path,'case',folder,test_shape=True)
                             ['property_access_id'],'unit-access')
            property_source.write_text('changed')
            with self.assertRaisesRegex(ValueError, 'source missing or changed'):
                check_access_review(path,'case',folder,test_shape=True)


if __name__ == "__main__":
    unittest.main()
