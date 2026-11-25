"""Saved source finalizer positive and missing-source negative checks."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
sys.path.insert(0, str(PACKAGE))
from finalize import finalize
from test_finalize_property import sources


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def attempt(folder: Path) -> None:
    native, survey, purpose = sources(True)
    for row in native:
        row["source_kind"] = "synthetic_native_fixture"
    survey["source_kind"] = "synthetic_native_property_survey"
    purpose["source_kind"] = "synthetic_controller_purpose_declaration"
    config = json.loads((PACKAGE / "native/config.json").read_text())
    config["recording_description"] = {"channels": [
        {"name": term, "unit": "structured", "sampling_rate_hz": 20} for term in
        ("dev.traffic_signal", "st.lane_enters", "st.driveway_or_alley_entrance",
         "kin.path_length", "rel.occupies", "st.intersection", "st.roadway", "kin.position")],
        "context_inputs": [{"name": "property_survey", "unit": "structured"},
                           {"name": "controller_purpose", "unit": "structured"}]}
    write_json(folder / "config.json", config)
    write_json(folder / "property-survey.json", survey)
    write_json(folder / "purpose-declaration.json", purpose)
    for index, row in enumerate(native):
        row["native_frame"] = index + 100
    write_rows(folder / "property-route-native.jsonl", native)
    write_rows(folder / "trace.jsonl", [
        {"frame": i + 100, "time_s": i / 20} for i in range(600)])
    write_rows(folder / "capture/evidence.jsonl", [
        {"original_frame": i + 100, "recording_time_s": i / 20,
         "ego": {"body_vertices_m": native[i]["body_vertices_xy_m"]}}
        for i in range(600)])
    write_rows(folder / "video_frames.jsonl", [
        {"native_frame": i + 100, "video_frame": i, "time_s": i / 20}
        for i in range(600)])
    write_json(folder / "capture/manifest.json", {"frames": 600, "extraction_confirmed": True})
    for name in ("overview", "approach", "reference_corner", "driver_reference"):
        (folder / (name + ".mkv")).write_bytes(b"diagnostic placeholder")


class SavedFinalizerTest(unittest.TestCase):
    def setUp(self) -> None:
        scratch = REPO / ".runtime-work/c151707-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.folder = Path(self.temp.name)
        attempt(self.folder)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_positive_original_joins_and_channels(self) -> None:
        report = finalize(self.folder, self.folder / "analysis-report.json")
        value = report["measurements"]["property_bypass_observation"]["value"]
        self.assertTrue(value["property_then_intersecting_street"])
        self.assertEqual(value["first_property_frame"], 200)
        self.assertEqual(value["first_intersecting_street_frame"], 260)
        result = json.loads((self.folder / "result.json").read_text())
        self.assertEqual(len(result["recording_evidence"]), 10)
        self.assertFalse(result["target_checks"][0]["physical_cause_confirmed"])
        self.assertEqual(result["provenance_kind"], "synthetic_fixture")

    def test_missing_original_survey_rejected(self) -> None:
        (self.folder / "property-survey.json").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source: property-survey.json"):
            finalize(self.folder, self.folder / "analysis-report.json")

    def test_capture_body_tampering_rejected(self) -> None:
        path = self.folder / "capture/evidence.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[200]["ego"]["body_vertices_m"][0][0] += 1
        write_rows(path, rows)
        with self.assertRaisesRegex(ValueError, "capture body differs"):
            finalize(self.folder, self.folder / "analysis-report.json")


if __name__ == "__main__":
    unittest.main()
