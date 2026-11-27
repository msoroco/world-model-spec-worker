"""Synthetic source protocol tests; no original excavation is attested."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "native"))
from excavation_runner import reviewed_context


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ExcavationSourceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT.parents[1] / ".runtime-work",
                                                prefix="c135702-exc-source-")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        bundle = json.loads((ROOT / "cases/excavation_kind/excavation-construction.json").read_text())
        cfg = json.loads(next(item["content"] for item in bundle["files"] if item["path"] == "config.json"))
        self.config = self.folder / "config.json"
        self.config.write_text(json.dumps(cfg) + "\n")
        self.case_id = cfg["case_id"]
        self.design = self.folder / "excavation-design.json"
        self.design.write_text(json.dumps({"source_kind": "synthetic_cpu_test_design",
                                           "left_lane_lowering_m": -1,
                                           "station_x_m": [0, 5]}) + "\n")

    def record(self, name, fields):
        path = self.folder / (name + ".json")
        path.write_text(json.dumps({"source_kind": name, "original_record_id": "fixture-" + name,
                                    **fields}) + "\n")
        return {"kind": name, "provenance": "reviewed_original_source",
                "path": path.name, "sha256": sha(path)}

    def context(self):
        cfg = json.loads(self.config.read_text())
        context = {"case_id": self.case_id, "source_kind": "reviewed_branch_context",
                   "activity_request": "park", "exception_request": None,
                   "placement_request": "opposite", "obstruction_kind_request": "excavation",
                   "exceptions": {name: False for name in
                                  ("traffic_conflict", "law_direction", "police_direction", "traffic_device")},
                   "exception_source": {name + "_reviewed": True for name in
                                        ("traffic_conflict", "law_direction", "police_direction", "traffic_device")},
                   "activity_source": self.record("operator_activity", {"requested_activity": "park"}),
                   "exception_sources": {}, "spatial_source": {}}
        for name in context["exceptions"]:
            fields = {"requested_exception": None, "event_window": "0-30 s", "scene_scope": "surveyed road"}
            fields.update({"original_instruction": "fixture instruction"}
                          if name in {"police_direction", "traffic_device"} else
                          {"law_citation": "fixture citation"} if name == "law_direction" else
                          {"traffic_source_refs": ["fixture traffic"]})
            context["exception_sources"][name] = self.record(name, fields)
        context["spatial_source"]["placement"] = self.record("placement", {
            "requested_value": "opposite", "scene_scope": "surveyed road"})
        context["spatial_source"]["obstruction_kind"] = self.record("obstruction_kind", {
            "requested_value": "excavation", "scene_scope": "surveyed road",
            "excavation_source_refs": [{"path": self.design.name, "sha256": sha(self.design)}]})
        context["source_records"] = {"operator_activity": context["activity_source"],
                                     **context["exception_sources"], **context["spatial_source"]}
        path = self.folder / "context.json"
        path.write_text(json.dumps(context) + "\n")
        return path

    def test_design_source_positive_and_tamper_rejected(self):
        context = self.context()
        reviewed, digest = reviewed_context(context, self.case_id, self.config)
        self.assertEqual(reviewed["obstruction_kind_request"], "excavation")
        self.assertEqual(digest, sha(context))
        self.design.write_text("{}\n")
        with self.assertRaisesRegex(ValueError, "changed excavation design source"):
            reviewed_context(context, self.case_id, self.config)

    def test_missing_design_reference_rejected(self):
        context = self.context()
        record = self.folder / "obstruction_kind.json"
        body = json.loads(record.read_text())
        body["excavation_source_refs"] = []
        record.write_text(json.dumps(body) + "\n")
        data = json.loads(context.read_text())
        data["spatial_source"]["obstruction_kind"]["sha256"] = sha(record)
        data["source_records"]["obstruction_kind"] = data["spatial_source"]["obstruction_kind"]
        context.write_text(json.dumps(data) + "\n")
        with self.assertRaisesRegex(ValueError, "excavation source"):
            reviewed_context(context, self.case_id, self.config)
