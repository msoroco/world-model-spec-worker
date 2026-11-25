"""Build five exact crosswalk constructions and risk-based speed fallbacks."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MODULES = ("runner.py", "native_entry.py", "reviewed_site.py", "analysis.py",
           "crosswalk_delivery.py", "delivery_audit.py")
OFFLINE_TEST = '''import json
import unittest
from pathlib import Path
from runner import check

class ExactCrosswalkOffline(unittest.TestCase):
    def test_source_gated_bundle(self):
        root = Path(__file__).resolve().parents[1]
        selected = check(root)
        self.assertEqual(selected["case_id"], json.loads((root / "config.json").read_text())["selected_case_id"])
        self.assertIn("reviewed original", selected["source_gate"])

if __name__ == "__main__":
    unittest.main()
'''


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    ids = [case["case_id"] for case in plan["cases"]]
    entries = []
    for case in plan["cases"]:
        cid = case["case_id"]
        folder = ROOT / "cases" / cid.split("__")[-1]
        description = {"channels": [
            {"name": "pedestrian_crosswalk_motion", "unit": "m", "sampling_rate_hz": 20,
             "method": "source-bound original walker position and passage station",
             "time_window": "900 original frames", "reference_frame": "reviewed crosswalk XY",
             "uncertainty": "physical passage pending"},
            {"name": "right_half_space", "unit": "m", "sampling_rate_hz": 20,
             "method": "source-bound original obstacle and available-space readback",
             "time_window": "900 original frames", "reference_frame": "direction-relative right half",
             "uncertainty": "legal practicability unresolved"},
            {"name": "nearby_participants", "unit": "inventory", "sampling_rate_hz": 20,
             "method": "original participant actor and pose readback",
             "time_window": "900 original frames", "reference_frame": "reviewed crosswalk XY",
             "uncertainty": "participant visibility pending"}],
            "context_inputs": [{"name": "crosswalk_source", "unit": "source",
                "method": "reviewed map, crosswalk, access, signal, obstacle and pedestrian source hashes"}],
            "limitations": ["No legal practicability threshold is adopted."]}
        config = {"law_id": "NRS-484B-293", "cell_id": "C150911", "actor": "pedestrian",
            "selected_case_id": cid, "supported_case_ids": ids, "required_atoms": [],
            "source_packets": [], "rate_hz": 20, "duration_s": 45,
            "cameras": [{"name": name, "width": width, "height": height,
                "fov_deg": 75, "pose_strategy": "reviewed original crossing and right-half view"}
                for name, width, height in (("overview", 1920, 1080), ("approach", 1280, 720),
                    ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))],
            "physical_completion": {"criterion": "observed_crosswalk_passage",
                "completion_goal_method": "900 original source-bound walker frames and full crossing station"},
            "case": {"case_id": cid, "physical_target": "direction-relative crosswalk passage",
                     "recording_description": description}}
        spec = {"case_id": cid, "direction": case["direction"],
                "target_half": case["target_half"],
                "obstacle_context": case["obstacle_context"],
                "site_source_status": "reviewed original C150911 crosswalk, access, signal and obstruction required",
                "legal_practicability": "unresolved"}
        write(folder / "config.json", config)
        write(folder / "case-spec.json", spec)
        for candidate, speed in (("primary", 1.2), ("fallback1", .8)):
            control = {"walker_speed_mps": speed,
                "source": "predeclared path tracking alternative on unchanged reviewed site",
                "physical_acceptance": False}
            source_name = "controller-" + candidate + ".json"
            write(folder / source_name, control)
            files = [{"path": name, "source": str((ROOT / name).relative_to(REPO)),
                      "content": (ROOT / name).read_text()} for name in MODULES]
            for name, value, source in (("config.json", config, folder / "config.json"),
                                        ("case-spec.json", spec, folder / "case-spec.json"),
                                        ("controller.json", control, folder / source_name)):
                files.append({"path": name, "source": str(source.relative_to(REPO)),
                              "content": json.dumps(value, indent=2, sort_keys=True) + "\n"})
            files.append({"path": "tests/test_offline.py", "content": OFFLINE_TEST})
            construction = {"law_id": "NRS-484B-293", "cell_id": "C150911",
                "actor": "pedestrian", "case_id": cid, "entrypoint": "runner.py",
                "files": files, "recording_description": description,
                "measurement_plan": {"selected_requirement": "NRS 484B.293",
                    "original_source": "reviewed crosswalk and 900-frame pedestrian/obstacle/participant streams",
                    "saved_method": "direction-relative lateral position and available right-half passage"},
                "static_checks": ["exact case, 20 Hz and four cameras",
                    "reviewed original site required before Native world mutation"],
                "termination_rules": {"duration_s": 45,
                    "early_termination": "retain failed capture; do not publish as full passage"}}
            name = "construction.json" if candidate == "primary" else "fallback1-construction.json"
            digest = write(folder / name, construction)
            if candidate == "primary":
                entry = {"case_id": cid, "construction": str((folder / name).relative_to(ROOT)),
                    "construction_sha256": digest, "kind": "delivery",
                    "measurement_procedure": {"entrypoint": "analysis.py"},
                    "fixture_recipe": str((folder / "fixture-recipe.json").relative_to(REPO)),
                    "measurement_contract": str((folder / "measurement-contract.json").relative_to(ROOT)),
                    "acquisition": {"crosswalk_passage": {"entrypoint": "runner.py",
                        "method": "run_native", "evidence": ["original-site.json",
                            "original-pedestrian.jsonl", "original-obstacles.jsonl",
                            "original-participants.jsonl", "original-receipt.json"]}},
                    "candidate_risk": {"status": "physical",
                        "reason": "Walker can overshoot source path or leave four-camera footprint before full crossing"},
                    "candidates": []}
            else:
                entry["candidates"].append({"id": "fallback1",
                    "construction": str((folder / name).relative_to(ROOT)),
                    "construction_sha256": digest,
                    "trigger": {"source": "original walker position and four-view frame audit",
                        "metric": "path deviation or missing synchronized camera frame",
                        "failure_condition": "primary leaves reviewed crosswalk geometry or loses a camera frame"},
                    "changed_knobs": ["walker speed 1.2 to 0.8 m/s on unchanged site and route"]})
        entries.append(entry)
    write(ROOT / "execution-manifest.draft.json", {"format": "worker-execution-manifest-draft",
        "assignment_id": ROOT.name,
        "runtime_manifest_sha256": "5e2dd81ac49dd2d9814a10b71ee30cf85323868a8369116020b06a69cbfcc5e3",
        "status": "reviewed-original-crosswalk-source-pending", "cases": entries})
    return entries


if __name__ == "__main__":
    print(json.dumps({"cases": len(build()), "status": "source-gated draft"}))
