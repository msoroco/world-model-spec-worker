import hashlib
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("compare_saved", ROOT / "compare_saved.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SavedPairTests(unittest.TestCase):
    def make_attempt(self, root, name, x, *, packet_change=None, time_change=0):
        attempt = root / name
        channel = attempt / "channels" / "reverse-body-crosswalk.jsonl"
        channel.parent.mkdir(parents=True, exist_ok=True)
        from test_site_packet import site
        original = site()
        if packet_change:
            original.update(packet_change)
        source_bytes = json.dumps(original, sort_keys=True).encode()
        packet = dict(original, case_id=name, site_source_path="fixture-only",
                      site_source_sha256=hashlib.sha256(source_bytes).hexdigest())
        packet_bytes = json.dumps(packet, sort_keys=True).encode()
        (attempt / "original-site-packet.json").write_bytes(packet_bytes)
        (attempt / "original-site-source.json").write_bytes(source_bytes)
        frames = []
        for index in range(2):
            frames.append({"frame": index, "time_s": index * .05 + (time_change if index else 0),
                           "vehicle_actor_id": 4,
                           "body_polygon_xy": [[x, 1], [x + 1, 1], [x + 1, 2], [x, 2]],
                           "crosswalk_polygon_xy": packet["crosswalk_polygon_xy"],
                           "velocity_xy": [-1, 0], "forward_xy": [1, 0], "reverse_gear": True})
        channel.write_text("".join(json.dumps(frame) + "\n" for frame in frames))
        source = {"map_packet": packet, "frames_sha256": hashlib.sha256(channel.read_bytes()).hexdigest(),
                  "source_id": name, "vehicle_actor_id": 4,
                  "original_site_packet_sha256": hashlib.sha256(packet_bytes).hexdigest(),
                  "original_site_source_sha256": hashlib.sha256(source_bytes).hexdigest()}
        (attempt / "reviewed-crosswalk-source.json").write_text(json.dumps(source) + "\n")
        return attempt, channel

    def test_exact_pairs(self):
        with tempfile.TemporaryDirectory(dir=pathlib.Path.cwd() / ".runtime-work") as tmp:
            root = pathlib.Path(tmp)
            clear, _ = self.make_attempt(root, "clear", 3)
            tangent, _ = self.make_attempt(root, "tangent", 2)
            overlap, _ = self.make_attempt(root, "overlap", 1.5)
            for name, right in (("reverse_contact_vs_clear", tangent),
                                ("reverse_overlap_vs_clear", overlap)):
                report = module.compare_attempts(clear, right, comparison_id=name)
                self.assertEqual(report["comparison_id"], name)
                self.assertEqual(report["legal_judgment"], "unresolved")
                self.assertEqual(len(report["original_frame_sha256"]), 2)

    def test_reject_missing_distinction_and_reused_attempt(self):
        with tempfile.TemporaryDirectory(dir=pathlib.Path.cwd() / ".runtime-work") as tmp:
            root = pathlib.Path(tmp)
            clear, _ = self.make_attempt(root, "clear", 3)
            also_clear, _ = self.make_attempt(root, "also-clear", 3)
            with self.assertRaisesRegex(ValueError, "target relation"):
                module.compare_attempts(clear, also_clear,
                                        comparison_id="reverse_overlap_vs_clear")
            with self.assertRaisesRegex(ValueError, "distinct saved"):
                module.compare_attempts(clear, clear,
                                        comparison_id="reverse_overlap_vs_clear")

    def test_reject_changed_fixed_source_and_frame_hash(self):
        with tempfile.TemporaryDirectory(dir=pathlib.Path.cwd() / ".runtime-work") as tmp:
            root = pathlib.Path(tmp)
            clear, _ = self.make_attempt(root, "clear", 3)
            overlap, channel = self.make_attempt(root, "overlap", 1.5,
                                                 packet_change={"driver_source": "other-driver"})
            with self.assertRaisesRegex(ValueError, "fixed source differs: driver_source"):
                module.compare_attempts(clear, overlap,
                                        comparison_id="reverse_overlap_vs_clear")
            overlap, channel = self.make_attempt(root, "overlap", 1.5)
            channel.write_text(channel.read_text() + "\n")
            with self.assertRaisesRegex(ValueError, "hash differs"):
                module.compare_attempts(clear, overlap,
                                        comparison_id="reverse_overlap_vs_clear")

    def test_reject_original_time_mismatch(self):
        with tempfile.TemporaryDirectory(dir=pathlib.Path.cwd() / ".runtime-work") as tmp:
            root = pathlib.Path(tmp)
            clear, _ = self.make_attempt(root, "clear", 3)
            overlap, _ = self.make_attempt(root, "overlap", 1.5, time_change=.0005)
            with self.assertRaisesRegex(ValueError, "original times differ"):
                module.compare_attempts(clear, overlap,
                                        comparison_id="reverse_overlap_vs_clear")


if __name__ == "__main__":
    unittest.main()
