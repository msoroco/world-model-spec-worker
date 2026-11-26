"""Build five exact source-gated yield bundles and bounded control fallbacks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from yield_source import CAMERAS, DIMENSIONS

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MODULES = ("runner.py", "analysis.py", "yield_site.py", "yield_source.py",
           "yield_measure.py", "native_yield_entry.py", "capture_yield.py",
           "carla_yield_readback.py", "yield_video_sources.py", "delivery_audit.py")
OFFLINE_TEST = '''import json
import unittest
from pathlib import Path
from runner import check

class ExactYieldOffline(unittest.TestCase):
    def test_source_gated_static_bundle(self):
        root = Path(__file__).resolve().parents[1]
        selected = check(root)
        self.assertEqual(selected["case_id"], json.loads((root / "config.json").read_text())["selected_case_id"])
        self.assertIn("reviewed original", selected["source_gate"])

if __name__ == "__main__":
    unittest.main()
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return sha(path)


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text(encoding="utf-8"))
    case_ids = [case["case_id"] for case in plan["cases"]]
    entries = []
    for index, case in enumerate(plan["cases"]):
        cid, tag = case["case_id"], case["variant"]
        folder = ROOT if index == 0 else ROOT / "cases" / tag
        description = {"channels": [
            {"name": name, "unit": "structured", "method": "SHA-verified original Native yield readback",
             "sampling_rate_hz": 20, "time_window": "900 original frames",
             "reference_frame": "reviewed Native yield-site map XY",
             "uncertainty": "original view, physical stopping and legal safety review pending"}
            for name in ("original_body_polygon", "original_speed", "yield_control_readback",
                         "approaching_traffic_readback",
                         "original_view_geometry", "four_camera_frames")],
            "context_inputs": [{"name": "reviewed_yield_context", "unit": "source",
                "method": "independently reviewed original yield sign, crossing inventory, occluder, driver viewpoint, traffic and safety source"}],
            "limitations": ["Geometric sight rays do not prove original driver perception or safety necessity."]}
        config = {"assignment_id": ROOT.name, "law_id": plan["law_id"], "cell_id": plan["cell_id"],
            "actor": plan["actor"], "selected_case_id": cid, "supported_case_ids": case_ids,
            "requested_stop_behavior": tag, "required_atoms": [], "source_packets": [],
            "plan_sha256": sha(ROOT / "case-plan.json"), "rate_hz": 20, "duration_s": 45,
            "physical_completion": {"criterion": "travel_progress", "motion_source": "trace.jsonl",
                "position_key": "position_m", "minimum_progress_m": 1.0,
                "minimum_samples": 3, "engineering_tolerances_not_legal": True,
                "completion_goal_method": "Original vehicle displacement is an engineering check; actual stop at source-selected reference, sight and safety need review"},
            "cameras": [{"name": name, "width": DIMENSIONS[name][0], "height": DIMENSIONS[name][1],
                "fov_deg": 75, "pose_strategy": "reviewed original yield approach and reference visibility"}
                for name in CAMERAS],
            "case": {"case_id": cid, "recording_description": description}}
        for candidate, throttle in (("primary", .3), ("fallback1", .2)):
            candidate_folder = folder if candidate == "primary" else ROOT / "cases" / tag / "fallback1"
            controller = {"target_behavior": tag, "throttle": throttle,
                "source": "bounded predeclared engineering route controller", "physical_acceptance": False}
            config_path = candidate_folder / "config.json"
            controller_path = candidate_folder / "controller.json"
            write(config_path, config)
            write(controller_path, controller)
            files = [{"path": name, "source": (ROOT / name).relative_to(REPO).as_posix(),
                      "content": (ROOT / name).read_text(encoding="utf-8")} for name in MODULES]
            for name, source in (("config.json", config_path), ("controller.json", controller_path)):
                files.append({"path": name, "source": source.relative_to(REPO).as_posix(),
                              "content": source.read_text(encoding="utf-8")})
            files.append({"path": "tests/test_offline.py", "content": OFFLINE_TEST})
            construction = {"law_id": plan["law_id"], "cell_id": plan["cell_id"],
                "actor": plan["actor"], "case_id": cid, "entrypoint": "runner.py", "files": files,
                "recording_description": description,
                "measurement_plan": {"selected_requirement": "NRS 484A.450(3)",
                    "original_source": "reviewed yield sign, crosswalk/line inventory, actual occluder, driver sight candidates, approaching traffic and safety source",
                    "saved_method": "900 original 20 Hz body, stop speed, source reference and four-camera frames; no automatic legal cutoff"},
                "static_checks": ["exact assignment/plan and yield-site source gate",
                    "bounded source-selected stop reference and original route",
                    "20 Hz four-camera original frame join"],
                "mechanisms": ["SHA-sealed independently reviewed original yield-site, map and camera sources",
                    "physical yield sign, occluder and approaching traffic actor construction with readback",
                    "bounded Native route and stop controller with original body/speed readback",
                    "900 synchronized original 20 Hz body, control and four-camera frames"],
                "termination_rules": {"duration_s": 45,
                    "early_termination": "retain failed attempt; never publish as completed"}}
            construction_path = candidate_folder / "construction.json"
            digest = write(construction_path, construction)
            if candidate == "primary":
                entry = {"case_id": cid, "kind": "delivery",
                    "construction": construction_path.relative_to(ROOT).as_posix(),
                    "construction_sha256": digest,
                    "fixture_recipe": (ROOT / "cases" / tag / "fixture-recipe.json").relative_to(REPO).as_posix(),
                    "measurement_contract": (ROOT / "cases" / tag / "measurement-contract.json").relative_to(ROOT).as_posix(),
                    "measurement_procedure": {"entrypoint": "analysis.py"},
                    "native_handoff": {"python_env_var": "CARLA_PYTHON", "host_env_var": "CARLA_HOST",
                        "port_env_var": "CARLA_PORT", "source_env_var": "C24823_YIELD_REVIEW"},
                    "acquisition": {name: {"entrypoint": "native_yield_entry.py", "method": "run_native",
                        "evidence": ["original-yield-site.json", "original-yield-trace.jsonl",
                                     "original-yield-receipt.json", "trace.jsonl", "video_frames.jsonl"]}
                        for name in ("original_body_polygon", "original_speed", "yield_control_readback",
                                     "approaching_traffic_readback",
                                     "original_view_geometry", "four_camera_frames")},
                    "candidate_risk": {"status": "physical",
                        "reason": "Reviewed blind-approach route braking and four-camera synchronization can fail at the selected reference"},
                    "candidates": []}
                entry["acquisition"]["reviewed_yield_context"] = {"entrypoint": "yield_source.py",
                    "method": "load_reviewed", "evidence": ["original-yield-site.json", "original-yield-receipt.json"]}
            else:
                entry["candidates"].append({"id": "fallback1",
                    "construction": construction_path.relative_to(ROOT).as_posix(),
                    "construction_sha256": digest,
                    "trigger": {"source": "original route, stop-target and four-camera frame audit",
                        "metric": "route cross-track and stop-reference overshoot or missing synchronized camera frame",
                        "failure_condition": "primary overshoots the selected source reference or loses an original camera frame"},
                    "changed_knobs": ["controller throttle 0.30 to 0.20 on unchanged reviewed site and requested stopping reference"]})
        entries.append(entry)
    write(ROOT / "execution-manifest.draft.json", {"format": "worker-execution-manifest",
        "assignment_id": ROOT.name, "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
        "cases": entries, "comparisons": plan["comparisons"]})
    (ROOT / "tests/test_offline.py").write_text(OFFLINE_TEST, encoding="utf-8")
    return len(entries)


if __name__ == "__main__":
    print(build())
