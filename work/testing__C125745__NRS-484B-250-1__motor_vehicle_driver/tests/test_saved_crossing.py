"""Original-shaped synthetic tests only; no CARLA or legal acceptance."""
import copy
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("c125745_saved_crossing", ROOT/"saved_crossing.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
sys.path.insert(0, str(ROOT))
from saved_finalizer import finalize
from compare_saved import audit as compare_saved
from encode_views import encode
from delivery_audit import audit as delivery_audit


def body(x, y):
    return [[x-.4,y-.4],[x+.4,y-.4],[x+.4,y+.4],[x-.4,y+.4]]


class CrossingTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.site = {"assignment_id": module.ASSIGNMENT, "cell_id": "C125745",
                     "case_id": module.ASSIGNMENT+"__precedence", "reviewer": "fixture only",
                     "review_status": "diagnostic_fixture",
                     "map_source_citation": "fixture map", "highway_source_citation": "fixture roads",
                     "device_source_citation": "fixture stop sign", "crossing_id": "crossing A",
                     "roadway_id": "roadway A", "ego_highway": "west highway",
                     "other_highway": "north highway", "approach_relation": "crossing",
                     "ego_side": "left", "other_side": "right",
                     "official_stop_sign_present": True, "stop_sign_controls_intersection": True,
                     "subsection_4_reviewed": False, "ego_actor_id": 11, "other_actor_id": 22,
                     "intersection_polygon_xy_m": [[-1,-1],[1,-1],[1,1],[-1,1]]}
        self.ego = self.rows(11, 6, 8, "x")
        self.other = self.rows(22, 2, 4, "y")
        self.write()

    @staticmethod
    def rows(actor, entry, exit_index, direction):
        result = []
        for i in range(10):
            coordinate = -4 if i < entry else (0 if i < exit_index else 4)
            x, y = (coordinate, 0) if direction == "x" else (0, coordinate)
            result.append({"frame": 100+i, "time_s": i*.05, "actor_id": actor,
                           "body_vertices_xy_m": body(x,y)})
        return result

    def write(self):
        (self.root/"road.xodr").write_text("<OpenDRIVE fixture='true'/>")
        for key, name in (("device_source", "original-device-source.txt"),
                          ("highway_source", "original-highway-source.txt")):
            path = self.root / name
            if not path.exists():
                path.write_text("diagnostic fixture only\n", encoding="utf-8")
            self.site[key] = {"path": name, "sha256": module.sha(path),
                              "citation": "diagnostic fixture only"}
        self.site["map_sha256"] = module.sha(self.root/"road.xodr")
        (self.root/"site-context.json").write_text(json.dumps(self.site))
        for key, rows in (("ego",self.ego),("other",self.other)):
            (self.root/f"{key}-body-history.jsonl").write_text(
                "".join(json.dumps(row)+"\n" for row in rows))
        (self.root/"source-manifest.json").write_text(json.dumps({name:{
            "kind":"original_native","sha256":module.sha(self.root/name)}
            for name in module.SOURCES}))

    def test_original_entry_clearance_and_exception_uncertainty(self):
        result = module.measure(self.root)
        self.assertEqual(result["other_entry"]["upper_frame"], 102)
        self.assertEqual(result["ego_entry"]["upper_frame"], 106)
        self.assertTrue(result["other_entered_before_ego"])
        self.assertTrue(result["other_cleared_before_ego_entry"])
        self.assertEqual(result["simultaneous_body_overlap_frames"], [])
        self.assertIn("unresolved", result["legal_applicability"])
        self.assertFalse(result["legal_verdict_claimed"])

    def test_pair_isolates_ego_response(self):
        waiting = module.measure(self.root)
        self.site["case_id"] = module.ASSIGNMENT+"__advance"
        self.ego = self.rows(11, 3, 8, "x")
        self.write()
        advancing = module.measure(self.root)
        self.assertEqual(advancing["simultaneous_body_overlap_frames"], [103])
        self.assertEqual(module.compare(waiting, advancing)["declared_difference"],
                         "ego_response_clearance_order")
        changed = copy.deepcopy(advancing)
        changed["stop_sign_controls_intersection"] = False
        with self.assertRaisesRegex(ValueError, "fixed comparison condition"):
            module.compare(waiting, changed)
        with self.assertRaisesRegex(ValueError, "did not change"):
            module.compare(waiting, waiting | {"case_id":"other"})

    def test_missing_tampered_and_wrong_scope_rejected(self):
        (self.root/"other-body-history.jsonl").unlink()
        with self.assertRaisesRegex(ValueError, "missing or stale original"):
            module.measure(self.root)
        self.write()
        (self.root/"road.xodr").write_text("tampered")
        with self.assertRaisesRegex(ValueError, "missing or stale original"):
            module.measure(self.root)
        self.write()
        self.site["official_stop_sign_present"] = False
        self.write()
        with self.assertRaisesRegex(ValueError, "stop-sign identity"):
            module.measure(self.root)

    def test_frame_join_gap_identity_and_late_missing_body_rejected(self):
        self.other[3]["frame"] += 1
        self.write()
        with self.assertRaisesRegex(ValueError, "frame/time join"):
            module.measure(self.root)
        self.other[3]["frame"] -= 1
        self.other[5]["actor_id"] = 99
        self.write()
        with self.assertRaisesRegex(ValueError, "actor identity"):
            module.measure(self.root)
        self.other[5]["actor_id"] = 22
        self.other[-1]["body_vertices_xy_m"] = None
        self.write()
        with self.assertRaisesRegex(ValueError, "missing original polygon"):
            module.measure(self.root)

    def test_missing_exit_and_highway_relation_rejected(self):
        self.other = self.rows(22, 2, 11, "y")
        self.write()
        with self.assertRaisesRegex(ValueError, "exit not captured"):
            module.measure(self.root)
        self.other = self.rows(22, 2, 4, "y")
        self.site["other_highway"] = self.site["ego_highway"]
        self.write()
        with self.assertRaisesRegex(ValueError, "different highways"):
            module.measure(self.root)

    def seal_cameras(self):
        self.site['camera_dimensions'] = {name: [2, 2] for name in
            ('overview', 'approach', 'reference_corner', 'driver_reference')}
        self.site['review_status'] = 'diagnostic_fixture'
        self.write()
        frames = self.root / 'original-frames'
        frames.mkdir()
        rows = []
        mapping = []
        for index, body_row in enumerate(self.ego):
            views = {}
            for name in self.site['camera_dimensions']:
                path = frames / f'{name}-{index:06d}.png'
                Image.new('RGB', (2, 2), (index, 20, 40)).save(path)
                views[name] = {'path': str(path.relative_to(self.root)),
                               'sha256': module.sha(path)}
            rows.append({'frame': body_row['frame'], 'time_s': body_row['time_s'],
                         'views': views})
            mapping.append({'video_frame': index, 'carla_frame': body_row['frame'],
                            'native_frame': body_row['frame'],
                            'time_s': body_row['time_s']})
        for name, content in (
            ('camera-frame-map.jsonl', rows), ('video_frames.jsonl', mapping)
        ):
            (self.root / name).write_text(''.join(json.dumps(row) + '\n'
                                                 for row in content), encoding='utf-8')
        trace = [{'frame': row['frame'], 'time_s': row['time_s'],
                  'position': {'x': sum(point[0] for point in row['body_vertices_xy_m']) / 4,
                               'y': sum(point[1] for point in row['body_vertices_xy_m']) / 4,
                               'z': 0.0}, 'heading_deg': 0.0, 'speed_mps': 0.0}
                 for row in self.ego]
        (self.root / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n'
                                                      for row in trace), encoding='utf-8')
        manifest_path = self.root / 'source-manifest.json'
        manifest = json.loads(manifest_path.read_text())
        for name in ('camera-frame-map.jsonl', 'video_frames.jsonl', 'trace.jsonl'):
            manifest[name] = {'kind': 'original_native',
                              'sha256': module.sha(self.root / name)}
        manifest_path.write_text(json.dumps(manifest))
        return manifest_path, frames

    def test_saved_finalizer_reopens_all_four_original_cameras(self):
        manifest_path, frames = self.seal_cameras()
        case_id = module.ASSIGNMENT + '__precedence'
        output = self.root / 'saved-result.json'
        result = finalize(self.root, output,
                          expected_manifest_sha256=module.sha(manifest_path),
                          case_id=case_id)
        self.assertEqual(result['camera_audit']['decoded_camera_frames'], 40)
        self.assertTrue(result['diagnostic_fixture'])
        self.assertFalse(result['physical_acceptance'])
        with self.assertRaisesRegex(FileExistsError, 'saved-result'):
            finalize(self.root, output,
                     expected_manifest_sha256=module.sha(manifest_path),
                     case_id=case_id)
        (frames / 'approach-000005.png').write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError, 'original camera frame bytes changed'):
            finalize(self.root, self.root / 'rejected.json',
                     expected_manifest_sha256=module.sha(manifest_path),
                     case_id=case_id)

    def test_saved_comparison_reopens_both_original_attempts(self):
        manifest_path, _ = self.seal_cameras()
        before_case = module.ASSIGNMENT + '__precedence'
        before_saved = self.root / 'before-result.json'
        finalize(self.root, before_saved,
                 expected_manifest_sha256=module.sha(manifest_path),
                 case_id=before_case)
        second_temp = tempfile.TemporaryDirectory()
        self.addCleanup(second_temp.cleanup)
        second = Path(second_temp.name) / 'advance'
        shutil.copytree(self.root, second)
        second_site_path = second / 'site-context.json'
        second_site = json.loads(second_site_path.read_text())
        second_site['case_id'] = module.ASSIGNMENT + '__advance'
        second_site_path.write_text(json.dumps(second_site))
        other_ego = self.rows(11, 3, 8, 'x')
        (second / 'ego-body-history.jsonl').write_text(''.join(
            json.dumps(row) + '\n' for row in other_ego))
        second_trace = [json.loads(line) for line in
                        (second / 'trace.jsonl').read_text().splitlines()]
        for row, body_row in zip(second_trace, other_ego):
            row['position']['x'] = sum(point[0] for point in
                                       body_row['body_vertices_xy_m']) / 4
        (second / 'trace.jsonl').write_text(''.join(
            json.dumps(row) + '\n' for row in second_trace))
        second_manifest_path = second / 'source-manifest.json'
        second_manifest = json.loads(second_manifest_path.read_text())
        for name in ('site-context.json', 'ego-body-history.jsonl', 'trace.jsonl'):
            second_manifest[name]['sha256'] = module.sha(second / name)
        second_manifest_path.write_text(json.dumps(second_manifest))
        after_saved = second / 'after-result.json'
        finalize(second, after_saved,
                 expected_manifest_sha256=module.sha(second_manifest_path),
                 case_id=second_site['case_id'])
        result = compare_saved(self.root, before_saved, second, after_saved)
        self.assertEqual(result['comparison_id'], 'official_stop_precedence')
        self.assertFalse(result['legal_verdict_claimed'])
        changed = json.loads(second_site_path.read_text())
        changed['camera_dimensions']['approach'] = [3, 2]
        second_site_path.write_text(json.dumps(changed))
        second_manifest['site-context.json']['sha256'] = module.sha(second_site_path)
        second_manifest_path.write_text(json.dumps(second_manifest))
        with self.assertRaisesRegex(ValueError, 'saved original manifest binding changed'):
            compare_saved(self.root, before_saved, second, after_saved)

    def test_encoded_views_and_independent_delivery_full_decode(self):
        manifest_path, _ = self.seal_cameras()
        case = module.ASSIGNMENT + '__precedence'
        saved = self.root / 'saved-result.json'
        finalize(self.root, saved,
                 expected_manifest_sha256=module.sha(manifest_path),
                 case_id=case)
        videos = self.root / 'encoded-views'
        receipt = encode(self.root, videos,
                         camera_dimensions=self.site['camera_dimensions'])
        audited = delivery_audit(self.root, saved, videos, receipt,
                                 probe_id='precedence')
        self.assertEqual(audited['decoded_view_frames'], 40)
        self.assertTrue(audited['full_video_decode'])
        self.assertFalse(audited['actual_pixels_verified'])
        (videos / 'overview.mkv').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'encoded camera bytes differ'):
            delivery_audit(self.root, saved, videos, receipt, probe_id='precedence')


if __name__ == "__main__":
    unittest.main()
