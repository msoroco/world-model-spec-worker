import hashlib
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("analyze_source", ROOT / "analyze_source.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SavedAnalysisTests(unittest.TestCase):
    def make_attempt(self, root):
        from test_site_packet import site
        original = site()
        source_bytes = json.dumps(original, sort_keys=True).encode()
        packet = dict(original, case_id="fixture-only", site_source_path="fixture-only",
                      site_source_sha256=hashlib.sha256(source_bytes).hexdigest())
        packet_bytes = json.dumps(packet, sort_keys=True).encode()
        (root / "original-site-packet.json").write_bytes(packet_bytes)
        (root / "original-site-source.json").write_bytes(source_bytes)
        body = [[1.5, 1], [2.5, 1], [2.5, 2], [1.5, 2]]
        frame = {"frame": 0, "time_s": 0, "vehicle_actor_id": 4,
                 "body_polygon_xy": body, "crosswalk_polygon_xy": packet["crosswalk_polygon_xy"],
                 "velocity_xy": [-1, 0], "forward_xy": [1, 0], "reverse_gear": True}
        path = root / "reverse-body-crosswalk-source.jsonl"
        path.write_text(json.dumps(frame) + "\n")
        context = {"map_packet": packet, "frames_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                   "source_id": "fixture-only", "vehicle_actor_id": 4,
                   "original_site_packet_sha256": hashlib.sha256(packet_bytes).hexdigest(),
                   "original_site_source_sha256": hashlib.sha256(source_bytes).hexdigest()}
        (root / "reviewed-crosswalk-source.json").write_text(json.dumps(context) + "\n")
        return path

    def test_positive_and_negative_missing_source(self):
        with tempfile.TemporaryDirectory(dir=pathlib.Path.cwd() / ".runtime-work") as tmp:
            root = pathlib.Path(tmp)
            frames = self.make_attempt(root)
            report = module.analyze(root, expected_relation="overlap")
            self.assertEqual(report["measurements"]["crosswalk_relation"]["value"]["observed_relation"], "overlap")
            with self.assertRaises(ValueError):
                module.analyze(root, expected_relation="contact")
            frames.unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source"):
                module.analyze(root, expected_relation="overlap")

    def test_reject_source_hash_change(self):
        with tempfile.TemporaryDirectory(dir=pathlib.Path.cwd() / ".runtime-work") as tmp:
            root = pathlib.Path(tmp)
            frames = self.make_attempt(root)
            frames.write_text(frames.read_text() + "\n")
            with self.assertRaisesRegex(ValueError, "hash differs"):
                module.analyze(root, expected_relation="overlap")

    def test_reject_missing_original_site_document(self):
        with tempfile.TemporaryDirectory(dir=pathlib.Path.cwd() / ".runtime-work") as tmp:
            root = pathlib.Path(tmp)
            self.make_attempt(root)
            (root / "original-site-source.json").unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source"):
                module.analyze(root, expected_relation="overlap")


if __name__ == "__main__":
    unittest.main()
