import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("original_release_axis", HERE / "original_release_axis.py")
axis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(axis)


class OriginalReleaseAxisTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.roots = []
        for release in (8, 9, 10, 11):
            root = Path(self.temporary.name) / str(release)
            root.mkdir()
            config = {"ego_release_frame": release, "other_release_frame": 10,
                      "site": {"crossing_id": "fixed"}}
            (root / "config.json").write_text(json.dumps(config))
            for name in ("controller_history.jsonl", "crossing_history.jsonl",
                         "video_frames.jsonl", "trace.jsonl"):
                (root / name).write_text("original-source\n")
            sources = {name: axis._sha(root / name) for name in (
                "config.json", "controller_history.jsonl", "crossing_history.jsonl",
                "video_frames.jsonl", "trace.jsonl")}
            (root / "capture-seal.json").write_text(json.dumps({
                "format": "worker-sealed-capture", "provenance_kind": "native",
                "diagnostic_fixture": False, "restoration": {"restored": True},
                "frames": 1100, "sources": sources}))
            self.roots.append(root)

    def _measured(self, root):
        release = json.loads((root / "config.json").read_text())["ego_release_frame"]
        return {"first_body_entry": {"ego": {"time_s": release * .05 + .5}},
                "release_to_entry_delay_s": {"ego": .5}, "sources": {}}

    def test_accepts_fixed_source_bound_measured_axis(self):
        with patch.object(axis._builder, "audit_release_attempt", self._measured), patch.object(
                axis, "_check_controls", return_value={"held_before_release": True,
                                                       "driven_after_release": True}):
            proof = axis.audit_axis(self.roots, "ego")
        self.assertEqual([row["release_frame"] for row in proof["rows"]], [8, 9, 10, 11])
        self.assertFalse(proof["legal_threshold_claimed"])

    def test_rejects_static_body_entry(self):
        with patch.object(axis, "_check_controls", return_value={}), patch.object(
                axis._builder, "audit_release_attempt", lambda root: {
            "first_body_entry": {"ego": {"time_s": 1.0}},
            "release_to_entry_delay_s": {"ego": .5}, "sources": {}}):
            with self.assertRaisesRegex(ValueError, "did not respond"):
                axis.audit_axis(self.roots, "ego")

    def test_rejects_changed_fixed_condition_and_missing_seal(self):
        root = self.roots[1]
        config = json.loads((root / "config.json").read_text())
        config["site"]["crossing_id"] = "changed"
        (root / "config.json").write_text(json.dumps(config))
        with patch.object(axis._builder, "audit_release_attempt", self._measured), patch.object(
                axis, "_check_controls", return_value={}):
            with self.assertRaisesRegex(ValueError, "sealed acquisition"):
                axis.audit_axis(self.roots, "ego")
        seal = json.loads((root / "capture-seal.json").read_text())
        seal["sources"]["config.json"] = axis._sha(root / "config.json")
        (root / "capture-seal.json").write_text(json.dumps(seal))
        with patch.object(axis._builder, "audit_release_attempt", self._measured), patch.object(
                axis, "_check_controls", return_value={}):
            with self.assertRaisesRegex(ValueError, "Fixed construction condition changed"):
                axis.audit_axis(self.roots, "ego")
        root.joinpath("capture-seal.json").unlink()
        with patch.object(axis._builder, "audit_release_attempt", self._measured), patch.object(
                axis, "_check_controls", return_value={}):
            with self.assertRaisesRegex(ValueError, "seal required"):
                axis.audit_axis(self.roots, "ego")

    def test_requires_observed_stop_and_applied_release(self):
        path = self.roots[0] / "controller_history.jsonl"
        rows = []
        for index in range(1100):
            rows.append({"release_permissions": {"ego": index >= 8},
                         "ego_control": {"hold": index < 8,
                                         "brake": 1.0 if index < 8 else 0.0,
                                         "throttle": 0.0 if index < 8 else .2}})
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        self.assertTrue(axis._check_controls(path, "ego", 8)["driven_after_release"])
        rows[7]["ego_control"]["brake"] = 0.0
        for row in rows[:7]:
            row["ego_control"]["brake"] = 0.0
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        with self.assertRaisesRegex(ValueError, "transition unproved"):
            axis._check_controls(path, "ego", 8)


if __name__ == "__main__":
    unittest.main()
