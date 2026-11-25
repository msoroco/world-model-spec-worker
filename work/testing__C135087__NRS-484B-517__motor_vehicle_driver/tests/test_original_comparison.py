"""Exercise original comparison isolation without claiming a physical capture."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audit_original_comparisons as original
from stand import SourceError


HERE = Path(__file__).resolve().parents[1]
SCRATCH = HERE.parents[1] / ".runtime-work"
PLAN = json.loads((HERE / "case-plan.json").read_text())
PAIR = PLAN["comparisons"][0]


class OriginalComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=SCRATCH, prefix="c135087-comparison-")
        self.addCleanup(self.temporary.cleanup)
        self.roots = [Path(self.temporary.name) / name for name in ("left", "right")]
        for root in self.roots:
            root.mkdir()

    def _write(self, root, obstructed):
        rows = [{"frame": index + 1, "subject_speed_mps": 0,
                 "passenger_loading_active": True, "access_obstructed": obstructed,
                 "entrant_waiting": False, "entrant_about_to_enter": True}
                for index in range(900)]
        body = json.dumps(rows).encode()
        (root / "actor-rows.json").write_bytes(body)
        (root / "attempt-source.json").write_text(json.dumps({
            "actor_rows": {"path": "actor-rows.json", "sha256": hashlib.sha256(body).hexdigest()}}))
        self._select(root, PAIR["case_ids"][self.roots.index(root)])

    def _select(self, root, case_id, candidate="primary"):
        manifest_path = HERE / "execution-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        entry = next(item for item in manifest["cases"] if item["case_id"] == case_id)
        selected = entry if candidate == "primary" else next(
            item for item in entry["candidates"] if item["id"] == candidate)
        (root / "candidate-selection.json").write_text(json.dumps({
            "format": "worker-candidate-selection", "case_id": case_id,
            "candidate_id": candidate, "construction_sha256": selected["construction_sha256"],
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest()}))

    def _fake_sweep(self, root, *_):
        index = self.roots.index(root)
        return {"case_id": PAIR["case_ids"][index], "measurements": {
            "stopped_frames": 900, "loading_during_stop_frames": 900,
            "access_obstructed_during_stop_frames": 900 * index,
            "entrant_waiting_or_about_during_stop_frames": 900}}

    def test_distinct_source_measured_access_comparison(self):
        self._write(self.roots[0], False)
        self._write(self.roots[1], True)
        with patch.object(original, "extract", side_effect=self._fake_sweep):
            result = original.audit(PAIR["comparison_id"], *self.roots, "a" * 64, "b" * 64)
        self.assertEqual(result["measured_values"], [0, 900])
        self.assertFalse(result["physical_acceptance_claimed"])

    def test_equal_original_measurement_rejected(self):
        self._write(self.roots[0], False)
        self._write(self.roots[1], False)
        def equal_sweep(root, *_):
            value = self._fake_sweep(root)
            value["measurements"]["access_obstructed_during_stop_frames"] = 0
            return value
        with patch.object(original, "extract", side_effect=equal_sweep):
            with self.assertRaisesRegex(SourceError, "measured difference absent"):
                original.audit(PAIR["comparison_id"], *self.roots, "a" * 64, "b" * 64)

    def test_changed_actor_rows_rejected(self):
        self._write(self.roots[0], False)
        self._write(self.roots[1], True)
        (self.roots[1] / "actor-rows.json").write_text("[]")
        with patch.object(original, "extract", side_effect=self._fake_sweep):
            with self.assertRaisesRegex(SourceError, "actor rows changed"):
                original.audit(PAIR["comparison_id"], *self.roots, "a" * 64, "b" * 64)

    def test_loading_comparison_uses_saved_loading_not_case_label(self):
        pair = next(item for item in PLAN["comparisons"] if item["comparison_id"] == "loading_activity")
        for index, root in enumerate(self.roots):
            self._write(root, True)
            self._select(root, pair["case_ids"][index])
            rows = json.loads((root / "actor-rows.json").read_text())
            for row in rows:
                row["passenger_loading_active"] = index == 0
            body = json.dumps(rows).encode()
            (root / "actor-rows.json").write_bytes(body)
            (root / "attempt-source.json").write_text(json.dumps({
                "actor_rows": {"path": "actor-rows.json", "sha256": hashlib.sha256(body).hexdigest()}}))
        def sweep(root, *_):
            index = self.roots.index(root)
            return {"case_id": pair["case_ids"][index], "measurements": {
                "stopped_frames": 900, "loading_during_stop_frames": 900 if index == 0 else 0,
                "access_obstructed_during_stop_frames": 900,
                "entrant_waiting_or_about_during_stop_frames": 900}}
        with patch.object(original, "extract", side_effect=sweep):
            result = original.audit(pair["comparison_id"], *self.roots, "a" * 64, "b" * 64)
        self.assertEqual(result["measured_values"], [900, 0])

    def test_entrant_comparison_checks_waiting_against_approaching(self):
        pair = next(item for item in PLAN["comparisons"] if item["comparison_id"] == "entrant_status")
        for index, root in enumerate(self.roots):
            self._write(root, False)
            self._select(root, pair["case_ids"][index])
            rows = json.loads((root / "actor-rows.json").read_text())
            for row in rows:
                row["entrant_waiting"] = index == 1
                row["entrant_about_to_enter"] = index == 0
            body = json.dumps(rows).encode()
            (root / "actor-rows.json").write_bytes(body)
            (root / "attempt-source.json").write_text(json.dumps({
                "actor_rows": {"path": "actor-rows.json", "sha256": hashlib.sha256(body).hexdigest()}}))
        def sweep(root, *_):
            index = self.roots.index(root)
            return {"case_id": pair["case_ids"][index], "measurements": {
                "stopped_frames": 900, "loading_during_stop_frames": 900,
                "access_obstructed_during_stop_frames": 0,
                "entrant_waiting_or_about_during_stop_frames": 900}}
        with patch.object(original, "extract", side_effect=sweep):
            result = original.audit(pair["comparison_id"], *self.roots, "a" * 64, "b" * 64)
        self.assertEqual(result["measured_values"], [(0, 900), (900, 0)])

    def test_changed_spawn_candidate_rejected(self):
        self._write(self.roots[0], False)
        self._write(self.roots[1], True)
        self._select(self.roots[1], PAIR["case_ids"][1], "fallback1")
        with patch.object(original, "extract", side_effect=self._fake_sweep):
            with self.assertRaisesRegex(SourceError, "spawn candidate"):
                original.audit(PAIR["comparison_id"], *self.roots, "a" * 64, "b" * 64)

    def test_synthetic_original_source_rejected(self):
        for root in self.roots:
            (root / "acquisition-provenance.json").write_text(json.dumps({
                "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}))
        with self.assertRaisesRegex(SourceError, "original Native acquisition"):
            original.audit(PAIR["comparison_id"], *self.roots, "a" * 64, "b" * 64)


if __name__ == "__main__":
    unittest.main()
