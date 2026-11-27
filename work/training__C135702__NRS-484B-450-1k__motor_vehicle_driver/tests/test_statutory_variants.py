"""Exercise source-gated activity, placement, kind and exception requests."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "native"))
import statutory_variants as variants


class StatutoryVariantTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT.parents[1] / ".runtime-work",
                                                prefix="c135702-statutory-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config_path = self.root / "config.json"
        self.context_path = self.root / "context.json"
        self.config = {"case_id": variants.ASSIGNMENT + "__selected_statutory_probe",
                       "law_id": "NRS-484B-450-1k", "cell_id": "C135702",
                       "actor": "motor_vehicle_driver", "rate_hz": 20,
                       "duration_s": 30, "frames": 600,
                       "camera_names": ["overview", "approach", "reference_corner", "driver_reference"],
                       "activity_request": "park", "exception_request": None,
                       "placement_request": "opposite",
                       "obstruction_kind_request": "physical_obstruction",
                       "physical_acceptance_claimed": False, "legal_verdict_claimed": False}

    def record(self, kind, fields):
        path = self.root / (kind + ".json")
        path.write_text(json.dumps({"source_kind": kind, "original_record_id": "fixture-" + kind,
                                    **fields}) + "\n")
        return {"kind": kind, "provenance": "reviewed_original_source",
                "path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def prepare(self):
        cfg = self.config
        self.config_path.write_text(json.dumps(cfg) + "\n")
        context = {"case_id": cfg["case_id"], "source_kind": "reviewed_branch_context",
                   "activity_request": cfg["activity_request"],
                   "exception_request": cfg["exception_request"],
                   "activity_source": self.record("operator_activity", {
                       "requested_activity": cfg["activity_request"]}),
                   "exception_sources": {}, "spatial_source": {}}
        for name in sorted(variants.EXCEPTIONS):
            fields = {"requested_exception": name if cfg["exception_request"] == name else None,
                      "event_window": "0-30 s", "scene_scope": "surveyed road"}
            fields.update({"original_instruction": "fixture instruction"}
                          if name in {"police_direction", "traffic_device"} else
                          {"law_citation": "fixture citation"} if name == "law_direction" else
                          {"traffic_source_refs": ["fixture traffic"]})
            context["exception_sources"][name] = self.record(name, fields)
        context["spatial_source"]["placement"] = self.record("placement", {
            "requested_value": cfg["placement_request"], "scene_scope": "surveyed road"})
        context["spatial_source"]["obstruction_kind"] = self.record("obstruction_kind", {
            "requested_value": cfg["obstruction_kind_request"], "scene_scope": "surveyed road",
            "excavation_source_refs": ["fixture surveyed excavation"]
            if cfg["obstruction_kind_request"] == "excavation" else []})
        self.context_path.write_text(json.dumps(context) + "\n")

    def test_all_statutory_request_dimensions(self):
        for activity in sorted(variants.ACTIVITIES):
            for placement in sorted(variants.POSITIONS):
                for kind in sorted(variants.KINDS):
                    for exception in [None, *sorted(variants.EXCEPTIONS)]:
                        with self.subTest(activity=activity, placement=placement,
                                          kind=kind, exception=exception):
                            self.config.update(activity_request=activity,
                                               placement_request=placement,
                                               obstruction_kind_request=kind,
                                               exception_request=exception)
                            self.prepare()
                            proof = variants.check_request(self.config_path, self.context_path)
                            self.assertFalse(proof["physical_acceptance_claimed"])
                            self.assertIsNone(proof["authored_geometry"]["traffic_obstruction_judged"])

    def test_missing_excavation_source_rejected(self):
        self.config["obstruction_kind_request"] = "excavation"
        self.prepare()
        source = self.root / "obstruction_kind.json"
        record = json.loads(source.read_text())
        record["excavation_source_refs"] = []
        source.write_text(json.dumps(record) + "\n")
        context = json.loads(self.context_path.read_text())
        context["spatial_source"]["obstruction_kind"]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        self.context_path.write_text(json.dumps(context) + "\n")
        with self.assertRaisesRegex(ValueError, "excavation source"):
            variants.check_request(self.config_path, self.context_path)

    def test_mismatched_spatial_source_rejected(self):
        self.prepare()
        self.config["placement_request"] = "alongside"
        self.config_path.write_text(json.dumps(self.config) + "\n")
        with self.assertRaisesRegex(ValueError, "spatial source differs"):
            variants.check_request(self.config_path, self.context_path)

    def test_missing_camera_or_changed_source_rejected(self):
        self.prepare()
        self.config["camera_names"].pop()
        self.config_path.write_text(json.dumps(self.config) + "\n")
        with self.assertRaisesRegex(ValueError, "camera"):
            variants.check_request(self.config_path, self.context_path)
        self.config["camera_names"].append("driver_reference")
        self.config_path.write_text(json.dumps(self.config) + "\n")
        (self.root / "placement.json").write_text("{}\n")
        with self.assertRaisesRegex(ValueError, "missing or changed"):
            variants.check_request(self.config_path, self.context_path)


if __name__ == "__main__":
    unittest.main()
