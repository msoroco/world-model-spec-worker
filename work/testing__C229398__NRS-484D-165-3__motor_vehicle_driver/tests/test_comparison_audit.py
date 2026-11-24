import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import comparison_audit as audit


class ComparisonAuditTest(unittest.TestCase):
    def test_five_native_shape_pairs_and_changed_frame_rejection(self):
        plan = json.loads((ROOT / "case-plan.json").read_text())
        cases = {item["case_id"]: item for item in plan["cases"]}
        fixed = {key: "same fixed source" for key in audit.FIXED_SITE_FIELDS}
        fixed["map_sha256"] = "a" * 64
        for comparison in plan["comparisons"]:
            with self.subTest(comparison=comparison["comparison_id"]), TemporaryDirectory() as directory:
                root = Path(directory)
                attempts, reports = [], []
                for number, case_id in enumerate(comparison["case_ids"]):
                    intended = cases[case_id]["intended_conditions"]
                    attempt = root / ("native-" + str(number))
                    capture = attempt / "capture"
                    capture.mkdir(parents=True)
                    evidence = dict(fixed, case_id=case_id,
                                    lighting_assessment=intended["lighting"],
                                    time_qualifies=intended["time_qualifies"])
                    source_file = capture / "site_source.json"
                    source_file.write_text(json.dumps(evidence) + "\n")
                    source_hash = audit.sha(source_file)
                    site = dict(evidence, site_source_sha256=source_hash)
                    (capture / "site_packet.json").write_text(json.dumps(site) + "\n")
                    history = capture / "original_history.jsonl"
                    history.write_text("".join(json.dumps({
                        "frame_index": index, "time_s": index / 20,
                        "map_sha256": "a" * 64, "vehicle_alive": True,
                        "vehicle_role": "motor_vehicle_driver",
                        "placement": intended["placement"],
                        "attendance": intended["attendance"],
                        "lighting_assessment": intended["lighting"],
                        "time_qualifies": intended["time_qualifies"],
                        "front_lamp_state": intended["lamps"],
                        "rear_lamp_state": intended["lamps"],
                        "parking_brake": True, "speed_mps": 0.0}) + "\n"
                        for index in range(900)))
                    measurement = {"case_id": case_id, "map_sha256": "a" * 64,
                                   "site_source_sha256": source_hash,
                                   "fixed_site_signature": audit.fixed_signature(site),
                                   "spec": {key: intended[key] for key in audit.FIELDS if key != "time_qualifies"},
                                   "time_qualifies": intended["time_qualifies"],
                                   "original_frame_count": 900,
                                   "one_hz_original_samples": [{} for _ in range(45)]}
                    sources = {name: audit.sha(capture / Path(name).name) for name in
                               ("capture/site_packet.json", "capture/original_history.jsonl")}
                    report = root / ("native-report-" + str(number) + ".json")
                    report.write_text(json.dumps({"case_id": case_id, "analysis_complete": True,
                        "diagnostic_fixture": False, "saved_measurement": measurement,
                        "measurements": {key: {"sources": sources} for key in
                            ("parked_position", "referenced_time", "revelation_1000ft",
                             "lamp_views_500ft", "traffic_side_installation")}}) + "\n")
                    attempts.append(attempt)
                    reports.append(report)
                arguments = (comparison["comparison_id"], reports[0], reports[1],
                             attempts[0], attempts[1])
                result = audit.audit(*arguments)
                self.assertTrue(result["fixed_site_verified"])
                self.assertFalse(result["physical_acceptance_claimed"])
                history = attempts[1] / "capture/original_history.jsonl"
                rows = history.read_text().splitlines()
                changed = json.loads(rows[300]);changed["speed_mps"] = 2.0
                rows[300] = json.dumps(changed)
                history.write_text("\n".join(rows) + "\n")
                edited = json.loads(reports[1].read_text())
                for method in edited["measurements"].values():
                    method["sources"]["capture/original_history.jsonl"] = audit.sha(history)
                reports[1].write_text(json.dumps(edited) + "\n")
                with self.assertRaisesRegex(ValueError, "original frame condition differs"):
                    audit.audit(*arguments)

    def test_five_pairs_source_bound_positive_and_negative(self):
        plan = json.loads((ROOT / "case-plan.json").read_text())
        cases = {item["case_id"]: item for item in plan["cases"]}
        for comparison in plan["comparisons"]:
            with self.subTest(comparison=comparison["comparison_id"]), TemporaryDirectory() as directory:
                root = Path(directory)
                attempts, reports = [], []
                for number, case_id in enumerate(comparison["case_ids"]):
                    intended = cases[case_id]["intended_conditions"]
                    attempt = root / ("attempt-" + str(number))
                    capture = attempt / "capture"
                    capture.mkdir(parents=True)
                    packet = {"case_id": case_id, "map_sha256": "a" * 64,
                              "site_source_sha256": "b" * 64}
                    (capture / "site_packet.json").write_text(json.dumps(packet) + "\n")
                    (capture / "original_history.jsonl").write_text(json.dumps({"frame": number}) + "\n")
                    measurement = {"case_id": case_id, "map_sha256": "a" * 64,
                                   "site_source_sha256": "b" * 64,
                                   "fixed_site_signature": {"road": "same", "traffic_side": "left"},
                                   "spec": {key: intended[key] for key in audit.FIELDS if key != "time_qualifies"},
                                   "time_qualifies": intended["time_qualifies"]}
                    (attempt / "diagnostic-source.json").write_text(json.dumps({
                        "case_id": case_id, "diagnostic_fixture": True,
                        "measurement": measurement}) + "\n")
                    sources = {name: audit.sha(capture / Path(name).name) for name in
                               ("capture/site_packet.json", "capture/original_history.jsonl")}
                    report = root / ("report-" + str(number) + ".json")
                    report.write_text(json.dumps({"case_id": case_id, "analysis_complete": True,
                        "diagnostic_fixture": True, "saved_measurement": measurement,
                        "measurements": {key: {"sources": sources} for key in
                            ("parked_position", "referenced_time", "revelation_1000ft",
                             "lamp_views_500ft", "traffic_side_installation")}}) + "\n")
                    attempts.append(attempt)
                    reports.append(report)
                arguments = (comparison["comparison_id"], reports[0], reports[1],
                             attempts[0], attempts[1])
                result = audit.audit(*arguments, diagnostic=True)
                self.assertTrue(result["fixed_site_verified"])
                self.assertFalse(result["physical_acceptance_claimed"])
                with self.assertRaisesRegex(ValueError, "source hash differs"):
                    audit.audit(comparison["comparison_id"], reports[0], reports[1],
                                attempts[0], attempts[0], diagnostic=True)
                changed = json.loads(reports[1].read_text())
                changed["saved_measurement"]["fixed_site_signature"]["road"] = "different"
                reports[1].write_text(json.dumps(changed) + "\n")
                with self.assertRaisesRegex(ValueError, "diagnostic comparison source differs"):
                    audit.audit(*arguments, diagnostic=True)
                fixture = attempts[1] / "diagnostic-source.json"
                source = json.loads(fixture.read_text())
                source["measurement"]["fixed_site_signature"]["road"] = "different"
                fixture.write_text(json.dumps(source) + "\n")
                with self.assertRaisesRegex(ValueError, "comparison fixed site changed"):
                    audit.audit(*arguments, diagnostic=True)
                altered_plan = root / "plan.json"
                edited = json.loads((ROOT / "case-plan.json").read_text())
                match = next(item for item in edited["comparisons"] if
                             item["comparison_id"] == comparison["comparison_id"])
                match["changed_fields"] = ["attendance" if comparison["changed_fields"] != ["attendance"]
                                           else "lamps"]
                altered_plan.write_text(json.dumps(edited) + "\n")
                with self.assertRaisesRegex(ValueError, "undeclared or absent difference"):
                    audit.audit(*arguments, diagnostic=True, plan_path=altered_plan)


if __name__ == "__main__":
    unittest.main()
