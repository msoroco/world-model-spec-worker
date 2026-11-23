"""Protocol checks for seven-case numerical binding; no reviewed site claim."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from bind_semantic_packet import bind
from test_native_scene import MAP_TEXT, packet


class SemanticPacketBindingTests(unittest.TestCase):
    def make_packet(self, root):
        root = Path(root)
        witness = root / "synthetic-map-source.xodr"
        witness.write_text(MAP_TEXT, encoding="utf-8")
        document = packet()
        document["diagnostic_fixture"] = True
        decisions = {"format": "c179789-seven-case-numerical-decisions-v1",
                     "assignment_id": document["assignment_id"], "cases": {}}
        for case_id, item in document["cases"].items():
            decisions["cases"][case_id] = {
                "reviewer": "synthetic fixture reviewer",
                "decision_basis": "diagnostic test values only",
                "variables": item["variables"],
                "road_id": item["road_id"], "lane_id": item["lane_id"],
                "ego_station_m": item["ego_station_m"]}
        decisions_path = root / "synthetic-decisions.json"
        decisions_path.write_text(json.dumps(decisions), encoding="utf-8")
        document["evidence_sources"] = [{"path": witness.name, "kind": "opendrive",
                                         "sha256": hashlib.sha256(witness.read_bytes()).hexdigest()},
                                        {"path": decisions_path.name,
                                         "kind": "numerical_decisions",
                                         "sha256": hashlib.sha256(decisions_path.read_bytes()).hexdigest()}]
        path = root / "packet.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return path, witness

    def test_seven_exact_case_values_and_six_isolated_pairs(self):
        with tempfile.TemporaryDirectory() as root:
            path, _ = self.make_packet(root)
            proposal = bind(path, diagnostic_test=True)
            self.assertEqual(len(proposal["cases"]), 8)
            self.assertTrue(proposal["numeric_binding_source"]["diagnostic_test"])
            for case in proposal["cases"]:
                if case["target_type"] == "baseline":
                    continue
                self.assertIsNone(case["variable_assignments"]["ego_speed"]["value"])
                self.assertEqual(case["variable_assignments"]["commanded_approach_speed"]["value"],
                                 packet()["cases"][case["case_id"]]["variables"]["ego_speed_request_mps"])
                self.assertFalse(case["numeric_binding_source"]["physical_acceptance_claimed"])

    def test_diagnostic_packet_cannot_bind_delivery(self):
        with tempfile.TemporaryDirectory() as root:
            path, _ = self.make_packet(root)
            with self.assertRaisesRegex(ValueError, "diagnostic packet"):
                bind(path)

    def test_changed_source_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path, witness = self.make_packet(root)
            witness.write_text("changed\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source bytes differ"):
                bind(path, diagnostic_test=True)

    def test_unbound_map_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path, _ = self.make_packet(root)
            document = json.loads(path.read_text())
            document["evidence_sources"][0]["kind"] = "text"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "OpenDRIVE map bytes"):
                bind(path, diagnostic_test=True)

    def test_unbound_numerical_decisions_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path, _ = self.make_packet(root)
            document = json.loads(path.read_text())
            document["evidence_sources"].pop()
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "numerical decisions"):
                bind(path, diagnostic_test=True)

    def test_changed_numerical_decision_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path, _ = self.make_packet(root)
            document = json.loads(path.read_text())
            decision_path = Path(root) / "synthetic-decisions.json"
            decisions = json.loads(decision_path.read_text())
            case_id = next(iter(decisions["cases"]))
            decisions["cases"][case_id]["variables"]["leader_initial_gap_m"] += 1
            decision_path.write_text(json.dumps(decisions), encoding="utf-8")
            document["evidence_sources"][1]["sha256"] = hashlib.sha256(
                decision_path.read_bytes()).hexdigest()
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "numerical decisions differ"):
                bind(path, diagnostic_test=True)

    def test_unplanned_case_change_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path, _ = self.make_packet(root)
            document = json.loads(path.read_text())
            case_id = next(key for key in document["cases"] if key.endswith("__faster"))
            document["cases"][case_id]["variables"]["leader_initial_gap_m"] += 1
            decision_path = Path(root) / "synthetic-decisions.json"
            decisions = json.loads(decision_path.read_text())
            decisions["cases"][case_id]["variables"]["leader_initial_gap_m"] += 1
            decision_path.write_text(json.dumps(decisions), encoding="utf-8")
            document["evidence_sources"][1]["sha256"] = hashlib.sha256(
                decision_path.read_bytes()).hexdigest()
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "undeclared comparison"):
                bind(path, diagnostic_test=True)


if __name__ == "__main__":
    unittest.main()
