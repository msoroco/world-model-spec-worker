"""Generate exact offline construction bundles without accessing CARLA."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODULES = ("runner.py", "road_geometry.py", "site_source.py", "native_entry.py", "analysis.py", "walking_measure.py")
OFFLINE_TEST = '''import json
import unittest
from pathlib import Path
from runner import check

class ExactWalkingOffline(unittest.TestCase):
    def test_case_and_source_gate(self):
        result = check(Path(__file__).resolve().parents[1])
        self.assertEqual(result["case_id"], json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text())["selected_case_id"])
        self.assertIn("reviewed original", result["source_gate"])

if __name__ == "__main__":
    unittest.main()
'''


def write(path: Path, value: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> None:
    plan = json.loads((HERE / "case-plan.json").read_text(encoding="utf-8"))
    ids = [case["case_id"] for case in plan["cases"]]
    entries = []
    for case in plan["cases"]:
        short = case["case_id"].split("__")[-1]
        folder = HERE / "cases" / short
        config = {"law_id": plan["law_id"], "cell_id": plan["cell_id"], "actor": plan["actor"], "selected_case_id": case["case_id"], "supported_case_ids": ids, "required_atoms": [], "source_packets": [], "rate_hz": 20, "duration_s": 45, "cameras": [{"name": name, "width": width, "height": height, "fov_deg": 75, "pose_strategy": "reviewed original walking segment and approaching vehicle"} for name, (width, height) in (("overview", (1920, 1080)), ("approach", (1280, 720)), ("reference_corner", (1280, 720)), ("driver_reference", (1280, 720)))], "physical_completion": {"criterion": "travel_progress", "motion_source": "trace.jsonl", "position_key": "position_m", "minimum_progress_m": 5.0, "minimum_samples": 3, "engineering_tolerances_not_legal": True}, "case": {"case_id": case["case_id"], "physical_target": "original pedestrian walking along public highway without sidewalk, side and facing measured relative to approaching traffic", "recording_description": {"channels": [{"name": "pedestrian_motion", "unit": "m", "sampling_rate_hz": 20, "method": "original pedestrian transform", "time_window": "900 original frames", "reference_frame": "reviewed highway", "uncertainty": "physical realization pending"}, {"name": "approaching_traffic", "unit": "m", "sampling_rate_hz": 20, "method": "original vehicle route and transform", "time_window": "900 original frames", "reference_frame": "reviewed highway", "uncertainty": "actual approach pending"}], "context_inputs": [{"name": "public_highway_and_sidewalk", "unit": "source", "method": "reviewed source-hashed site packet"}], "limitations": ["Physical side, facing and highway status require original review; no legal verdict from fixture"]}}}
        spec = {key: case[key] for key in ("case_id", "approach_direction", "pedestrian_highway_side", "pedestrian_heading")}
        write(folder / "config.json", config)
        write(folder / "case-spec.json", spec)
        write(folder / "measurement-contract.json", {"format": "worker-measurement-contract", "case_id": case["case_id"], "requirements": [{"disposition_index": 0, "requirement": plan["requirement_dispositions"][0]["requirement"], "source": plan["requirement_dispositions"][0]["source"], "kind": "measured", "method": "measure_walking_source", "output_key": "walking_side_and_facing", "value_type": "object", "inputs": ["original-walking-observations.json", "original-walking-receipt.json"]}], "negative": {"remove": ["original-walking-observations.json"], "error_contains": "Missing required source: original-walking-observations.json"}})
        entry = {"case_id": case["case_id"], "kind": "delivery",
                 "fixture_recipe": str((folder / "fixture-recipe.json").relative_to(ROOT)),
                 "measurement_contract": str((folder / "measurement-contract.json").relative_to(HERE)),
                 "measurement_procedure": {"entrypoint": "analysis.py"},
                 "candidate_risk": {"status": "physical", "reason": case["physical_risk"]},
                 "candidates": [], "native_handoff": {"python_env_var": "CARLA_PYTHON",
                 "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}}
        for candidate, speed in (("primary", 1.0), ("fallback1", 0.8)):
            controller_name = "controller-" + candidate + ".json"
            controller = {"walker_speed_mps": speed,
                "method": "same reviewed walking edge and route; speed is a controller target",
                "physical_acceptance": False}
            write(folder / controller_name, controller)
            files = [{"path": name, "source": str((HERE / name).relative_to(ROOT)),
                      "content": (HERE / name).read_text(encoding="utf-8")} for name in MODULES]
            files.append({"path": "tests/test_offline.py", "content": OFFLINE_TEST})
            for name in ("config.json", "case-spec.json"):
                files.append({"path": name, "source": str((folder / name).relative_to(ROOT)),
                    "content": (folder / name).read_text(encoding="utf-8")})
            files.append({"path": "controller.json", "source": str((folder / controller_name).relative_to(ROOT)),
                "content": (folder / controller_name).read_text(encoding="utf-8")})
            construction = {"law_id": plan["law_id"], "cell_id": plan["cell_id"],
                "actor": plan["actor"], "case_id": case["case_id"], "entrypoint": "runner.py",
                "files": files, "recording_description": config["case"]["recording_description"],
                "measurement_plan": {"selected_requirement": plan["requirement_dispositions"][0]["requirement"],
                    "original_source": "reviewed site and 900 original pedestrian/vehicle frames",
                    "saved_method": "source-bound side/facing trajectory"},
                "mechanisms": ["source-gated highway site", "mirrored pedestrian and approaching vehicle routes",
                    "bounded walker controller and moving vehicle"],
                "static_checks": ["exact case, 20 Hz and four cameras",
                    "reviewed source packet required before Native"],
                "termination_rules": {"duration_s": 45,
                    "early_termination": "retain failed capture; do not publish as original walking"}}
            path = folder / ("construction.json" if candidate == "primary" else "fallback1-construction.json")
            digest = write(path, construction)
            if candidate == "primary":
                entry["construction"] = str(path.relative_to(HERE))
                entry["construction_sha256"] = digest
            else:
                entry["candidates"].append({"id": "fallback1",
                    "construction": str(path.relative_to(HERE)), "construction_sha256": digest,
                    "trigger": {"source": "original pedestrian 20 Hz path and four-camera pixel audit",
                        "metric": "synchronized pedestrian body visibility",
                        "failure_condition": "primary walker loses body visibility in a synchronized view"},
                    "changed_knobs": ["walker speed target 1.0 to 0.8 m/s on the same reviewed route"]})
        entries.append(entry)
    write(HERE / "execution-manifest.draft.json", {"format": "worker-execution-manifest", "assignment_id": HERE.name, "runtime_manifest_sha256": hashlib.sha256((ROOT / "runtime/SOURCE-MANIFEST.json").read_bytes()).hexdigest(), "cases": entries})


if __name__ == "__main__":
    build()
