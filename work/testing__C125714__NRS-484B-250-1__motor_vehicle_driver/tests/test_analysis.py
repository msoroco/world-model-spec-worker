import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis import build_report


def _rectangle(y):
    return [[-.2, y-.2], [.2, y-.2], [.2, y+.2], [-.2, y+.2]]


def fixture(folder):
    folder = Path(folder)
    context = {
        "ego_actor_id": 11, "other_actor_id": 22,
        "crossing": {"crossing_id": "A-B-west", "roadway_id": "A-west",
                     "bounds_xy_m": [-1, -1, 1, 1]},
        "law_context": {"map_source": "map hash", "ego_highway": "A",
                        "other_highway": "B", "public_access_source": "road inventory hash",
                        "device_inventory_source": "map inspection hash",
                        "driver_scope_source": "actor blueprint hash",
                        "public_access": True, "human_driver": True, "devices": [],
                        "approach_relation": "crossing", "left_turn_intent": False,
                        "left_turn_realized": False},
    }
    (folder / "intersection-context.json").write_text(json.dumps(context))
    for name, ident, entry, exit_frame in (
            ("ego", 11, 4, 6), ("other", 22, 2, 4)):
        with (folder / f"{name}-body-history.jsonl").open("w") as stream:
            for frame in range(9):
                y = -2 if frame < entry else (0 if frame < exit_frame else 2)
                stream.write(json.dumps({"frame": frame, "time_s": frame / 20,
                                         "actor_id": ident,
                                         "body_vertices_xy_m": _rectangle(y)}) + "\n")
    names = ("intersection-context.json", "ego-body-history.jsonl",
             "other-body-history.jsonl")
    acquisition = {name: {"kind": "original_native",
                          "sha256": hashlib.sha256((folder / name).read_bytes()).hexdigest()}
                   for name in names}
    (folder / "acquisition.json").write_text(json.dumps(acquisition))


class SavedAnalysisTests(unittest.TestCase):
    def test_original_sources_measure_entry_and_keep_judgment_open(self):
        with TemporaryDirectory() as tmp:
            fixture(tmp)
            report = build_report(tmp)
            item = report["measurements"]["crossing_entry_measurement"]
            self.assertTrue(item["value"]["other_entered_before_ego"])
            self.assertFalse(item["value"]["other_cleared_before_ego_entry"])
            self.assertEqual(item["value"]["legal_judgment"], "unresolved")
            self.assertEqual(len(item["sources"]), 3)

    def test_missing_and_stale_source_rejected(self):
        with TemporaryDirectory() as tmp:
            fixture(tmp)
            path = Path(tmp) / "other-body-history.jsonl"
            original = path.read_text()
            path.unlink()
            with self.assertRaisesRegex(ValueError, "Missing required"):
                build_report(tmp)
            path.write_text(original + "\n")
            with self.assertRaisesRegex(ValueError, "stale original"):
                build_report(tmp)

    def test_actor_binding_and_frame_time_join_rejected(self):
        with TemporaryDirectory() as tmp:
            fixture(tmp)
            path = Path(tmp) / "other-body-history.jsonl"
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            rows[2]["actor_id"] = 999
            path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            acquisition = json.loads((Path(tmp) / "acquisition.json").read_text())
            acquisition[path.name]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            (Path(tmp) / "acquisition.json").write_text(json.dumps(acquisition))
            with self.assertRaisesRegex(ValueError, "actor identity"):
                build_report(tmp)
            rows[2]["actor_id"] = 22
            rows[2]["time_s"] += .01
            path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            acquisition[path.name]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            (Path(tmp) / "acquisition.json").write_text(json.dumps(acquisition))
            with self.assertRaisesRegex(ValueError, "frame/time join"):
                build_report(tmp)


if __name__ == "__main__":
    unittest.main()
