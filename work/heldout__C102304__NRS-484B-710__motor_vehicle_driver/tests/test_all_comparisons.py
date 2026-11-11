"""Independent source-bound audits for stopped boundaries and exception."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


FOLDER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FOLDER))
spec = importlib.util.spec_from_file_location("comparison_audit", FOLDER / "fire_comparison_audit.py")
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)


class AllComparisonsTests(unittest.TestCase):
    def test_stopped_below_at_above_and_exception(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)

            def row(name):
                folder = FOLDER / "cases" / name
                diagnostic = json.loads((folder / "diagnostic.json").read_text())
                receipt = json.loads((folder / "primary-compatibility.json").read_text())
                value = receipt["measurement_examples"]["fire_boundary_observation"]["value"]
                path = base / name
                path.mkdir()
                for source in ("participant_footprints.jsonl", "participant_state.jsonl"):
                    (path / source).write_text(diagnostic["files"][source])
                measurement = path / "measurement.json"
                measurement.write_text(json.dumps(value))
                from hashlib import sha256
                return {"case_id": FOLDER.name + "__" + name,
                        "measurement_path": str(measurement),
                        "measurement_sha256": sha256(measurement.read_bytes()).hexdigest(),
                        "participant_path": str(path / "participant_footprints.jsonl"),
                        "state_path": str(path / "participant_state.jsonl")}

            for branch in ("stopped_drive_to", "stopped_park"):
                cases = [row(f"{branch}_{target}ft") for target in (450, 500, 550)]
                expected = {case["case_id"]: label for case, label in
                            zip(cases, ("below", "at", "above"))}
                comparison = {"comparison_id": branch + "_500_boundary", "cases": cases,
                              "fixed_conditions": ["branch", "apparatus_answered_alarm",
                                                   "authorized_emergency", "official_business"],
                              "deliberate_difference": "boundary_bin", "expected_values": expected}
                self.assertTrue(audit_module.audit(comparison)["passed"])
                changed = json.loads((Path(cases[0]["participant_path"])).read_text().splitlines()[0])
                changed["ego_corners"][0][0] += 1
                lines = Path(cases[0]["participant_path"]).read_text().splitlines()
                lines[0] = json.dumps(changed)
                Path(cases[0]["participant_path"]).write_text("\n".join(lines) + "\n")
                with self.assertRaisesRegex(ValueError, "source hash mismatch"):
                    audit_module.audit(comparison)

            # The ordinary 500 ft diagnostic is stored at the package root.
            diagnostic = json.loads((FOLDER / "diagnostic-input.json").read_text())
            receipt = json.loads((FOLDER / "first-compatibility.json").read_text())
            value = receipt["measurement_examples"]["fire_boundary_observation"]["value"]
            path = base / "ordinary"
            path.mkdir()
            for source in ("participant_footprints.jsonl", "participant_state.jsonl"):
                (path / source).write_text(diagnostic["files"][source])
            measurement = path / "measurement.json"
            measurement.write_text(json.dumps(value))
            from hashlib import sha256
            ordinary = {"case_id": FOLDER.name + "__traveling_follow_500ft",
                        "measurement_path": str(measurement),
                        "measurement_sha256": sha256(measurement.read_bytes()).hexdigest(),
                        "participant_path": str(path / "participant_footprints.jsonl"),
                        "state_path": str(path / "participant_state.jsonl")}
            exception = row("authorized_emergency_at500")
            comparison = {"comparison_id": "authorized_emergency_exception",
                          "cases": [ordinary, exception],
                          "fixed_conditions": ["branch", "apparatus_answered_alarm", "boundary_bin"],
                          "deliberate_difference": "authorized_emergency",
                          "expected_values": {ordinary["case_id"]: False,
                                              exception["case_id"]: True}}
            self.assertTrue(audit_module.audit(comparison)["passed"])
            comparison["deliberate_difference"] = "official_business"
            self.assertTrue(audit_module.audit(comparison)["passed"])


if __name__ == "__main__":
    unittest.main()
