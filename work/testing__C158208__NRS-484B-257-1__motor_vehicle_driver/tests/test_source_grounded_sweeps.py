import hashlib
import json
import unittest
from unittest.mock import patch

from build_semantic_proposals import JUDGMENTS, LAW
from source_grounded_sweeps import verify, measure_realization
from test_source_tick_capture import GEOMETRY
import test_build_production_construction as production_fixtures


class SourceGroundedSweepTests(unittest.TestCase):
    def setUp(self):
        fixture = production_fixtures.ProductionConstructionTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.root = fixture.root
        self.site_path = fixture.site_path
        self.site = fixture.site
        self.sweep_path = self.root / "reviewed-sweeps.json"
        self.proposal = {"site_sha256": hashlib.sha256(self.site_path.read_bytes()).hexdigest(),
                         "law_id": LAW, "legal_cutoff": None, "sweep_specs": []}
        for index, (phrase, note, _) in enumerate(JUDGMENTS):
            survey = ("yield_sign", "nearest_view_survey", "through_highway_survey",
                      "stop_line_survey")[index]
            self.proposal["sweep_specs"].append({
                "sweep_id": "survey-range-" + str(index), "target_law_id": LAW,
                "judgment_refs": [{"phrase": phrase, "note": note}],
                "status": "complete", "mode": "one_dimensional",
                "axes": [{"variable": "engineering_target", "observable": "measured_trajectory",
                          "unit": "m", "min": 1.0, "max": 5.0, "spacing": 1.0,
                          "measurement": {"method": "original ticks", "time_window": "full approach",
                                          "statistic": "minimum"},
                          "range_rationale": "fixture survey range", "spacing_rationale": "fixture resolution",
                          "feasibility_evidence": {"survey": survey,
                              "sha256": self.site["source_bindings"][survey]["sha256"],
                              "observation": "source-shaped test fixture only"}}],
                "landmarks": [], "variable_assignments": {"engineering_target": 1.0},
                "recording_description": {"channels": ["original ticks"]}})
        self.write_sweep()

    def write_sweep(self):
        self.sweep_path.write_text(json.dumps(self.proposal) + "\n")

    def test_original_source_shaped_sweeps_bind_all_phrases(self):
        receipt = verify(self.site_path, self.sweep_path)
        self.assertEqual(len(receipt["judgment_phrases"]), 4)
        self.assertEqual(receipt["legal_status"], "unresolved")

    def test_rejects_tampered_survey_and_legal_cutoff(self):
        (self.root / "yield_sign.txt").write_text("changed")
        with self.assertRaisesRegex(ValueError, "source hash differs"):
            verify(self.site_path, self.sweep_path)
        (self.root / "yield_sign.txt").write_text("yield_sign")
        self.proposal["legal_cutoff"] = 3.0
        self.write_sweep()
        with self.assertRaisesRegex(ValueError, "legal cutoff"):
            verify(self.site_path, self.sweep_path)

    def test_rejects_unbound_range_and_diagnostic_site(self):
        self.proposal["sweep_specs"][1]["axes"][0]["feasibility_evidence"]["sha256"] = "0" * 64
        self.write_sweep()
        with self.assertRaisesRegex(ValueError, "original survey source"):
            verify(self.site_path, self.sweep_path)
        self.site["diagnostic_fixture"] = True
        self.fixture.write_site()
        with self.assertRaisesRegex(ValueError, "original reviewed"):
            verify(self.site_path, self.sweep_path)

    def test_sealed_tick_realization_is_numeric_and_never_legal(self):
        self.site["stopping_reference_station_m"] = 8.0
        self.fixture.write_site()
        digest = hashlib.sha256(self.site_path.read_bytes()).hexdigest()
        self.proposal["site_sha256"] = digest
        for spec in self.proposal["sweep_specs"]:
            spec["axes"][0]["observable"] = "minimum_approach_speed_mps"
            spec["axes"][0]["unit"] = "m/s"
        self.write_sweep()
        attempt = self.root / "attempt"
        attempt.mkdir()
        case = "testing__C158208__NRS-484B-257-1__motor_vehicle_driver__nearest_view_response"
        (attempt / "capture-identity.json").write_text(json.dumps({
            "case_id": case, "site_packet_sha256": digest,
            "provenance_kind": "synthetic_fixture"}) + "\n")
        samples = []
        for index, station in enumerate((0.0, 8.0, 12.0)):
            samples.append({"frame": index + 1, "time_s": index * .05,
                            "ego_speed_mps": 2.0, "ego_front_station_m": station,
                            "through_center_station_m": float(index),
                            "through_vehicle_within_intersection": False,
                            "intersection_entry": index == 2,
                            "through_traffic_visible": True})
        packet = {"geometry": GEOMETRY, "reviewed_context": self.site["reviewed_context"],
                  "samples": samples}
        with patch("source_grounded_sweeps.verify_seal", return_value=packet):
            report = measure_realization(attempt, self.site_path, self.sweep_path,
                                         case, diagnostic_fixture=True)
            self.assertEqual([row["value"] for row in report["realized_axes"]], [2.0] * 4)
            self.assertEqual(report["legal_status"], "unresolved")
            with self.assertRaisesRegex(ValueError, "900 sealed Native ticks"):
                measure_realization(attempt, self.site_path, self.sweep_path, case)


if __name__ == "__main__":
    unittest.main()
