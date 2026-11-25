import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import saved_comparison
from test_median_opening import scene, trace


def attempt(root, suffix, ego_entry):
    root.mkdir()
    selected = scene(suffix)
    (root / "scene.json").write_text(json.dumps(selected))
    source = {
        "native_trace": json.dumps(trace(selected, ego_entry=ego_entry)).encode(),
        "opendrive": b"inspected map",
        "device_inventory": b"original device inventory",
        "camera_front": b"front", "camera_rear": b"rear",
        "camera_left": b"left", "camera_right": b"right",
    }
    refs = {}
    for name, body in source.items():
        (root / name).write_bytes(body)
        refs[name] = {"path": name, "sha256": hashlib.sha256(body).hexdigest()}
    (root / "source-manifest.json").write_text(json.dumps({
        "case_id": selected["case_id"], "frame_count": 900, "sources": refs}))


class SavedComparisonTests(unittest.TestCase):
    def test_two_sealed_original_histories_are_compared(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            attempt(root / "precedence", "precedence", 60)
            attempt(root / "advance", "advance", 45)
            result = saved_comparison.audit(root / "precedence", root / "advance")
            self.assertEqual(result["comparison_id"], "inoperative_signal_precedence")
            self.assertEqual(len(result["source_sha256"]), 2)
            self.assertTrue(result["observations"][0]["ego_waited_until_other_exit"])
            self.assertFalse(result["observations"][1]["ego_waited_until_other_exit"])
            self.assertEqual(result["legal_applicability"], "unresolved")

    def test_missing_tampered_or_wrong_pair_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = root / "precedence", root / "advance"
            attempt(first, "precedence", 60)
            attempt(second, "advance", 45)
            (second / "camera_left").unlink()
            with self.assertRaisesRegex(ValueError, "missing original source"):
                saved_comparison.audit(first, second)
            (second / "camera_left").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "stale original source"):
                saved_comparison.audit(first, second)
            (second / "camera_left").write_bytes(b"left")
            wrong = copy.deepcopy(json.loads((second / "scene.json").read_text()))
            wrong["other_highway"] = "changed"
            (second / "scene.json").write_text(json.dumps(wrong))
            with self.assertRaisesRegex(ValueError, "fixed condition"):
                saved_comparison.audit(first, second)
            (second / "scene.json").write_text(json.dumps(scene("advance")))
            altered = json.loads((second / "source-manifest.json").read_text())
            body = b"different official device inventory"
            (second / "device_inventory").write_bytes(body)
            altered["sources"]["device_inventory"]["sha256"] = hashlib.sha256(body).hexdigest()
            (second / "source-manifest.json").write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError, "fixed device inventory"):
                saved_comparison.audit(first, second)
            (second / "device_inventory").write_bytes(b"original device inventory")
            altered["sources"]["device_inventory"]["sha256"] = hashlib.sha256(b"original device inventory").hexdigest()
            (second / "source-manifest.json").write_text(json.dumps(altered))
            wrong = json.loads((second / "source-manifest.json").read_text())
            wrong["case_id"] = scene("precedence")["case_id"]
            (second / "source-manifest.json").write_text(json.dumps(wrong))
            with self.assertRaisesRegex(ValueError, "wrong exact comparison case"):
                saved_comparison.audit(first, second)


if __name__ == "__main__":
    unittest.main()
