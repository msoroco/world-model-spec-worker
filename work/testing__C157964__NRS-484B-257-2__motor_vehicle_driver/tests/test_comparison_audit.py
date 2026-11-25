import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import comparison_audit as AUDIT


def write(path, payload):
    path.write_text(json.dumps(payload) + "\n")


def fixture(root, suffix, control, direction):
    root.mkdir()
    case = AUDIT.PREFIX + suffix
    context = {key: ("source" if key.endswith("source") else "site") for key in AUDIT.FIXED}
    context.update(case_id=case, officer_actor_id=12, native_map_id="CPU-map",
                   intersection_id=1, non_through_highway=True,
                   ego_entrance_device="yield", other_entrance_device="none",
                   intersection_polygon_xy_m=[[-5, -5], [5, -5], [5, 5], [-5, 5]])
    write(root / "officer_context.json", context)
    rows = [{"frame": 100 + i, "time_s": 5 + i / 20,
             "officer_direction_observed": direction,
             "traffic_control_observed": control,
             "direction_frame_source": f"approach.mkv#frame-{i}",
             "other_frame_source": f"overview.mkv#frame-{i}"} for i in range(3)]
    (root / "officer_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    entry = {"frame": 101, "time_s": 5.05, "officer_direction_observed": direction,
             "traffic_control_observed": control}
    observed = {"samples": [{"frame": row["frame"], "time_s": row["time_s"],
                             "direction": direction, "traffic_control_observed": control}
                            for row in rows],
                "first_ego_entry": None if suffix == "officer_controls_hold" else entry,
                "first_hold_observation": entry if suffix == "officer_controls_hold" else None}
    hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
              for name in ("officer_context.json", "officer_history.jsonl")}
    write(root / "analysis.json", {"format": "worker-c157964-subsection-2-saved-analysis",
                                   "case_id": case, "source_sha256": hashes,
                                   "source_report": observed,
                                   "physical_acceptance_claimed": False,
                                   "legal_conclusion": "unresolved"})


class ComparisonAuditTests(unittest.TestCase):
    def test_both_exact_contrasts_preserve_uncertainty(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root / "go", "officer_controls_go", True, "go")
            fixture(root / "inactive", "officer_present_inactive", False, "none")
            fixture(root / "hold", "officer_controls_hold", True, "stop")
            for name, second in (("officer_control_exception", "inactive"),
                                 ("officer_direction", "hold")):
                result = AUDIT.audit(name, root / "go", root / second)
                self.assertTrue(result["comparison_passed"])
                self.assertFalse(result["physical_acceptance_claimed"])
                self.assertEqual(result["legal_conclusion"], "unresolved")

    def test_changed_original_source_or_fixed_context_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root / "go", "officer_controls_go", True, "go")
            fixture(root / "inactive", "officer_present_inactive", False, "none")
            with (root / "inactive" / "officer_history.jsonl").open("a") as stream:
                stream.write("{}\n")
            with self.assertRaisesRegex(ValueError, "hash changed"):
                AUDIT.audit("officer_control_exception", root / "go", root / "inactive")
            fixture_root = root / "replacement"
            fixture(fixture_root, "officer_present_inactive", False, "none")
            context_path = fixture_root / "officer_context.json"
            context = json.loads(context_path.read_text())
            context["intersection_id"] = 2
            write(context_path, context)
            report_path = fixture_root / "analysis.json"
            report = json.loads(report_path.read_text())
            report["source_sha256"]["officer_context.json"] = hashlib.sha256(context_path.read_bytes()).hexdigest()
            write(report_path, report)
            with self.assertRaisesRegex(ValueError, "fixed site"):
                AUDIT.audit("officer_control_exception", root / "go", fixture_root)


if __name__ == "__main__":
    unittest.main()
