import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import aspect_capture
import saved_aspect


class AspectCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.site = {
            "official_head_id": "17",
            "ego_approach_id": "north",
            "arrow_movement": "left",
        }

    def tearDown(self):
        self.temp.cleanup()

    def readback(self, i):
        return {
            "frame": 100 + i,
            "elapsed_seconds": i / 20,
            "head_id": "17",
            "facing_approach_id": "north",
            "arrow_color": "yellow",
            "arrow_direction": "left",
            "arrow_lit": (i // 10) % 2 == 0,
            "source_kind": "display_sensor",
            "source_id": "camera-head-17",
            "native_head_state": "Yellow",
            "concurrent_indications": [],
        }

    def test_sealed_900_frame_history_and_diagnostic_gate(self):
        result = aspect_capture.capture(self.site, self.root, self.readback,
                                        diagnostic=True)
        self.assertEqual(result["frame_count"], 900)
        self.assertGreater(result["observed_transitions"], 2)
        checked = saved_aspect.audit(self.site, self.root, delivery=False)
        self.assertEqual(checked["original_aspect_sha256"], result["source_sha256"])
        with self.assertRaisesRegex(aspect_capture.AspectError, "diagnostic"):
            saved_aspect.audit(self.site, self.root, delivery=True)

    def test_tamper_and_path_escape_rejected(self):
        aspect_capture.capture(self.site, self.root, self.readback)
        source = self.root / "arrow-aspect-original.json"
        source.write_text(source.read_text() + " ")
        with self.assertRaisesRegex(aspect_capture.AspectError, "hash mismatch"):
            saved_aspect.audit(self.site, self.root)
        receipt = self.root / "arrow-aspect-receipt.json"
        doc = json.loads(receipt.read_text())
        doc["source_path"] = "../outside.json"
        receipt.write_text(json.dumps(doc))
        with self.assertRaisesRegex(aspect_capture.AspectError, "escapes"):
            saved_aspect.audit(self.site, self.root)

    def test_missing_flashing_and_wrong_identity_rejected(self):
        with self.assertRaisesRegex(aspect_capture.AspectError, "transitions"):
            aspect_capture.capture(self.site, self.root,
                                  lambda i: dict(self.readback(i), arrow_lit=True))
        with self.assertRaisesRegex(aspect_capture.AspectError, "head mismatch"):
            aspect_capture.capture(self.site, self.root,
                                  lambda i: dict(self.readback(i), head_id="99"))
        with self.assertRaisesRegex(aspect_capture.AspectError, "time join"):
            aspect_capture.capture(self.site, self.root,
                                  lambda i: dict(self.readback(i), elapsed_seconds=i / 10))

    def test_no_overwrite(self):
        aspect_capture.capture(self.site, self.root, self.readback)
        with self.assertRaisesRegex(aspect_capture.AspectError, "already exists"):
            aspect_capture.capture(self.site, self.root, self.readback)

    def test_event_join_rejects_invented_arrow(self):
        aspect_capture.capture(self.site, self.root, self.readback, diagnostic=True)
        events = []
        for i in range(900):
            aspect = self.readback(i)
            events.append({
                "frame": aspect["frame"],
                "official_head_id": aspect["head_id"],
                "facing_approach_id": aspect["facing_approach_id"],
                "lit_aspects": ["flashing_yellow_turn_arrow"] if aspect["arrow_lit"] else [],
                "concurrent_indications": [],
            })
        path = self.root / "events.json"
        def seal():
            path.write_text(json.dumps(events))
            return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        self.assertTrue(saved_aspect.join_event_history(self.site, self.root, seal(),
                                                       delivery=False)["event_aspect_join"])
        events[10]["lit_aspects"] = ["flashing_yellow_turn_arrow"]
        with self.assertRaisesRegex(aspect_capture.AspectError, "display mismatch"):
            saved_aspect.join_event_history(self.site, self.root, seal(), delivery=False)


if __name__ == "__main__":
    unittest.main()
