"""Materialize ten exact source-gated route bundles and fallback candidates."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PLAN = json.loads((ROOT / "case-plan.json").read_text())
PROPOSAL = json.loads((ROOT / "proposals/cases.json").read_text())
DESCRIPTION = {row["case_id"]: row["recording_description"] for row in
               PROPOSAL["cases"] if row["target_law_id"]}
SOURCES = ("runner.py", "analysis.py", "native_route_capture.py", "alternate_route.py",
           "reviewed_route_scene.py", "source_gated_sweeps.py", "case-plan.json")
TESTS = tuple(sorted(path.relative_to(ROOT).as_posix() for path in
                     (ROOT / "tests").glob("test*.py")))
CAMERAS = [
    {"name": "overview", "width": 1920, "height": 1080,
     "pose_strategy": "SHA-reviewed fixed highway and route-divergence view", "fov_deg": 90},
    {"name": "approach", "width": 1280, "height": 720,
     "pose_strategy": "SHA-reviewed fixed ego and immediate follower approach", "fov_deg": 90},
    {"name": "reference_corner", "width": 1280, "height": 720,
     "pose_strategy": "SHA-reviewed fixed alternate entry and main continuation", "fov_deg": 90},
    {"name": "driver_reference", "width": 1280, "height": 720,
     "pose_strategy": "SHA-reviewed ego-mounted forward route reference", "fov_deg": 90},
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def construction(folder: Path, config: dict, case_id: str) -> Path:
    dump(folder / "config.json", config)
    files = []
    for name in (*SOURCES, *TESTS, "config.json"):
        path = folder / "config.json" if name == "config.json" else ROOT / name
        files.append({"path": name, "source": path.relative_to(REPO).as_posix(),
                      "content": path.read_text()})
    value = {"law_id": PLAN["law_id"], "cell_id": PLAN["cell_id"],
             "actor": PLAN["actor"], "case_id": case_id,
             "entrypoint": "runner.py", "files": files,
             "recording_description": DESCRIPTION[case_id],
             "mechanisms": ["SHA-verified original route/map/restriction gate before CARLA import",
                            "synchronous 20 Hz Native ego/follower motion and route readback",
                            "four synchronized original CARLA camera streams"],
             "measurement_plan": {
                 "source_context": "Reviewed highway, access, restriction, journey and driver sources",
                 "participant_motion": "900 original frame ego/follower speed, spacing and station history",
                 "route_observation": "actual terminal road identity and alternate entry evidence",
                 "judgments": "legal impediment and possibility remain unresolved"},
             "static_checks": ["exact cell/law/case and source hashes", "reviewed route divergence",
                               "900 joined Native frames and four camera views"],
             "termination_rules": ["stop after 900 synchronous ticks",
                                   "abort on original source, frame, map, route or camera mismatch"]}
    path = folder / "construction.json"
    dump(path, value)
    return path


def main() -> None:
    ids = [row["case_id"] for row in PLAN["cases"]]
    if len(ids) != 10 or set(ids) != set(DESCRIPTION):
        raise ValueError("ten selected route cases required")
    entries = []
    for index, row in enumerate(PLAN["cases"]):
        case_id = row["case_id"]
        tag = case_id.rsplit("__", 1)[-1]
        folder = ROOT if index == 0 else ROOT / "cases" / tag
        config = {"assignment_id": PLAN["assignment_id"], "selected_case_id": case_id,
                  "supported_case_ids": ids, "law_id": PLAN["law_id"],
                  "cell_id": PLAN["cell_id"], "actor": PLAN["actor"],
                  "rate_hz": 20, "duration_s": 45, "required_atoms": [],
                  "source_packets": [], "cameras": CAMERAS,
                  "follower_request_mps": 8.0,
                  "case": {"case_id": case_id, "target": row["target"],
                           "recording_description": DESCRIPTION[case_id]},
                  "physical_completion": {"criterion": "travel_progress",
                      "motion_source": "body_history.jsonl",
                      "body_key": "body_vertices_m", "heading_key": "heading_deg",
                      "minimum_progress_m": 10, "minimum_samples": 2,
                      "engineering_tolerances_not_legal": True}}
        primary_path = construction(folder, config, case_id)
        fallback_config = copy.deepcopy(config)
        fallback_config["follower_request_mps"] = 7.0
        fallback_folder = ROOT / "cases" / tag / "fallback1"
        fallback_path = construction(fallback_folder, fallback_config, case_id)
        rows = []
        for position, disposition in enumerate(PLAN["requirement_dispositions"]):
            if case_id not in disposition["case_ids"]:
                continue
            if position == 0:
                key, kind, inputs = "highway_vehicle_context", "sourced_context", ["original-site.json"]
            elif position == 1:
                key, kind, inputs = "following_motion_measurement", "measured", ["original-route-motion.json"]
            else:
                key, kind, inputs = "alternate_route_measurement", "measured", ["original-site.json", "original-route-motion.json"]
            rows.append({"disposition_index": position,
                         "requirement": disposition["requirement"],
                         "source": disposition["source"],
                         "output_key": key, "method": "build_report",
                         "value_type": "object", "kind": kind, "inputs": inputs})
        contract = folder / "measurement-contract.json"
        dump(contract, {"format": "worker-measurement-contract",
                        "requirements": rows,
                        "negative": {"remove": ["original-route-motion.json"],
                                     "error_contains": "Missing required source: original-route-motion.json"}})
        channels = [item["name"] for item in DESCRIPTION[case_id]["channels"]]
        contexts = [item["name"] for item in DESCRIPTION[case_id]["context_inputs"]]
        acquisition = {name: {"entrypoint": "analysis.py",
                              "evidence": "channels/" + name + ".jsonl",
                              "method": "Saved projection of SHA-verified original Native samples"}
                       for name in channels}
        acquisition.update({name: {"entrypoint": "analysis.py",
                                   "evidence": "channels/context.json",
                                   "method": "Saved projection of SHA-verified original route site"}
                            for name in contexts})
        entries.append({"case_id": case_id, "kind": "delivery",
                        "construction": primary_path.relative_to(ROOT).as_posix(),
                        "construction_sha256": sha(primary_path),
                        "fixture_recipe": (ROOT / ("diagnostic-" + tag + "-recipe.json")).relative_to(REPO).as_posix(),
                        "measurement_contract": contract.relative_to(ROOT).as_posix(),
                        "measurement_procedure": {"entrypoint": "analysis.py"},
                        "acquisition": acquisition,
                        "native_handoff": {"host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT",
                                           "python_env_var": "CARLA_PYTHON", "site_env_var": "ROUTE_SITE_PATH",
                                           "site_sha256_env_var": "ROUTE_SITE_SHA256"},
                        "candidate_risk": row["physical_risk"],
                        "candidates": [{"id": "fallback1",
                            "construction": fallback_path.relative_to(ROOT).as_posix(),
                            "construction_sha256": sha(fallback_path),
                            "changed_knobs": ["follower engineering speed request 8 to 7 m/s"],
                            "trigger": {"source": "original Native ego/follower station and speed trace",
                                        "metric": "following gap and route progress after control request",
                                        "failure_condition": "primary follower loses the reviewed shared approach before route divergence"}}]})
    batch = json.loads((REPO / "batch.json").read_text())
    dump(ROOT / "execution-manifest.json", {
        "format": "worker-execution-manifest", "assignment_id": PLAN["assignment_id"],
        "runtime_manifest_sha256": batch["runtime"]["source_manifest_sha256"],
        "cases": entries, "comparisons": PLAN["comparisons"]})


if __name__ == "__main__":
    main()
