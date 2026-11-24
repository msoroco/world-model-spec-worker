"""Small textual three-actor sources exercise the saved join, not CARLA motion."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reciprocal_saved import ASSIGNMENT, SOURCE, audit_saved


def body(x):
    return [[x + dx, y, z] for z in (-0.5, 0.5)
            for dx in (-0.5, 0.5) for y in (-0.5, 0.5)]


def write(root, name, value):
    path = root / name
    path.write_text(value, encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(root, case_id, braking):
    polygon = [[-5, -5], [5, -5], [5, 5], [-5, 5]]
    map_sha = write(root, "original-map.json", json.dumps({"intersection_polygon": polygon}) + "\n")
    primary, later = [], []
    for index in range(900):
        frame = 100 + index
        primary.append({"frame": frame, "time_s": index / 20,
                        "ego_actor_id": 1, "opponent_actor_id": 2,
                        "opponent_vertices": body(0 if index == 0 else 10),
                        "ego_heading": [1, 0], "ego_turn_committed": index >= 2})
        later.append({"frame": frame, "time_s": index / 20,
                      "later_opponent_actor_id": 3,
                      "later_opponent_vertices": body(10 if index < 3 else 0),
                      "later_opponent_heading": [-1, 0],
                      "later_opponent_speed_mps": 4,
                      "later_opponent_braking": braking and index == 2,
                      "later_opponent_driver_control_source": "original get_control"})
    trace_sha = write(root, "original-trace.jsonl",
                      "".join(json.dumps(row) + "\n" for row in primary))
    later_sha = write(root, SOURCE, "".join(json.dumps(row) + "\n" for row in later))
    receipt = {"case_id": case_id, "simulator_frame_rate_hz": 20,
               "frame_count": 900, "map_sha256": map_sha,
               "trace_sha256": trace_sha, "later_opponent_trace_sha256": later_sha}
    write(root, "acquisition-receipt.json", json.dumps(receipt) + "\n")


class ReciprocalSavedTests(unittest.TestCase):
    def test_both_exact_responses_and_missing_or_stale_sources(self):
        for suffix, braking in (("reciprocal_yield", True),
                                ("reciprocal_no_yield", False)):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                case_id = ASSIGNMENT + "__" + suffix
                fixture(root, case_id, braking)
                result = audit_saved(root, case_id=case_id)
                self.assertEqual(result["joined_original_frames"], 900)
                self.assertEqual(result["observations"]["later_opponent_actor_id"], 3)
                self.assertEqual(result["observations"]["later_braking_during_conflict"], braking)
                source = root / SOURCE
                original = source.read_bytes()
                source.write_bytes(original + b" ")
                with self.assertRaisesRegex(ValueError, "hash drift"):
                    audit_saved(root, case_id=case_id)
                source.write_bytes(original)
                source.unlink()
                with self.assertRaisesRegex(ValueError, "missing or outside"):
                    audit_saved(root, case_id=case_id)

    def test_cross_case_and_frame_join_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case_id = ASSIGNMENT + "__reciprocal_yield"
            fixture(root, case_id, True)
            with self.assertRaisesRegex(ValueError, "identity"):
                audit_saved(root, case_id=ASSIGNMENT + "__reciprocal_no_yield")
            source = root / SOURCE
            rows = source.read_text().splitlines()
            altered = json.loads(rows[5])
            altered["frame"] += 1
            rows[5] = json.dumps(altered)
            digest = write(root, SOURCE, "\n".join(rows) + "\n")
            receipt = root / "acquisition-receipt.json"
            data = json.loads(receipt.read_text())
            data["later_opponent_trace_sha256"] = digest
            receipt.write_text(json.dumps(data) + "\n")
            with self.assertRaisesRegex(ValueError, "frame join"):
                audit_saved(root, case_id=case_id)


if __name__ == "__main__":
    unittest.main()
