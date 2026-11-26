"""Build nine exact crossing bundles and one shared camera-risk fallback each."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PLAN = json.loads((HERE / "case-plan.json").read_text())
VIEWS = (("overview", 1920, 1080), ("approach", 1280, 720),
         ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))
SOURCES = ("runner.py", "analysis.py", "crosswalk_site.py", "native_output_bridge.py",
           "crosswalk_clearance.py", "crosswalk_measure.py", "native_capture.py",
           "case-plan.json")
TESTS = tuple(path.relative_to(HERE).as_posix()
              for path in sorted((HERE / "tests").glob("test*.py")))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    all_ids = [case["case_id"] for case in PLAN["cases"]]
    entries = []
    for index, case in enumerate(PLAN["cases"]):
        case_id = case["case_id"]
        tag = case["variant"]
        folder = HERE if index == 0 else HERE / "cases" / tag
        channels = [{"name": name, "unit": "structured", "sampling_rate_hz": 20,
                     "method": "source-sealed original Native readback",
                     "time_window": "all 900 ticks", "reference_frame": "original CARLA map/world",
                     "uncertainty": "physical and legal classification pending"}
                    for name in ("original_body_polygon", "original_speed",
                                 "activity_readback", "exception_readback",
                                 "four_camera_frames")]
        description = {"channels": channels,
                       "context_inputs": [{"name": "jurisdiction_and_crossing_context",
                                           "unit": "source",
                                           "method": "reviewed jurisdiction, crossing markings and independent exception sources"}],
                       "limitations": ["Legal distance convention, exact boundary and exception judgments unresolved."]}
        base_config = {"assignment_id": PLAN["assignment_id"],
                       "law_id": PLAN["law_id"], "cell_id": PLAN["cell_id"],
                       "actor": PLAN["actor"], "selected_case_id": case_id,
                       "supported_case_ids": all_ids,
                       "plan_sha256": sha(HERE / "case-plan.json"),
                       "rate_hz": 20, "duration_s": 45,
                       "required_atoms": [], "source_packets": [],
                       "requested_body_clearance_m": float(case["body_clearance_target"].removesuffix("m")),
                       "requested_activity": case["halt_activity_request"],
                       "requested_exception": case["exception_request"],
                       "crosswalk_marked": case["crosswalk_marking_request"] == "marked",
                       "physical_completion": {"criterion": "travel_progress",
                                               "motion_source": "body_history.jsonl",
                                               "body_key": "body_vertices_m",
                                               "minimum_progress_m": 2.0,
                                               "minimum_samples": 2,
                                               "engineering_tolerances_not_legal": True},
                       "cameras": [{"name": name, "width": width, "height": height,
                                    "fov_deg": 85,
                                    "pose_strategy": "reviewed fixed crossing and full-body visibility"}
                                   for name, width, height in VIEWS],
                       "case": {"case_id": case_id,
                                "recording_description": description}}
        for candidate, camera_offset in (("primary", 0.0), ("fallback1", 2.0)):
            config = copy.deepcopy(base_config)
            config["camera_offset_m"] = camera_offset
            candidate_folder = folder if candidate == "primary" else HERE / "cases" / tag / "fallback1"
            config_path = candidate_folder / "config.json"
            write(config_path, config)
            files = []
            for name in (*SOURCES, *TESTS, "config.json"):
                source = config_path if name == "config.json" else HERE / name
                files.append({"path": name,
                              "source": source.relative_to(REPO).as_posix(),
                              "content": source.read_text()})
            construction = {
                "law_id": PLAN["law_id"], "cell_id": PLAN["cell_id"],
                "actor": PLAN["actor"], "case_id": case_id,
                "entrypoint": "runner.py", "files": files,
                "recording_description": description,
                "mechanisms": ["SHA-verified original crossing site and independent source records",
                               "Native crosswalk, route, activity and exception construction",
                               "900 original 20 Hz full-body and four-camera readbacks"],
                "measurement_plan": {"body_clearance": "Minimum full-body polygon distance to reviewed crossing polygon; 6.096 m is twenty-foot arithmetic only.",
                                     "activity": "Retain original service activity and responsible-person sources separately from requested mode.",
                                     "exception": "Retain traffic, law, police and device sources without automatic legal judgment."},
                "static_checks": ["exact source/plan hash", "crosswalk marking and geometry live readback",
                                  "900 original frame and four camera joins"],
                "termination_rules": ["stop at 900 Native ticks", "abort on missing source or readback"]}
            construction_path = candidate_folder / "construction.json"
            write(construction_path, construction)
            if candidate == "primary":
                entries.append({"case_id": case_id, "kind": "delivery",
                                "construction": construction_path.relative_to(HERE).as_posix(),
                                "construction_sha256": sha(construction_path),
                                "candidate_risk": case["physical_risk"],
                                "measurement_procedure": {"entrypoint": "analysis.py"},
                                "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                                   "host_env_var": "CARLA_HOST",
                                                   "port_env_var": "CARLA_PORT",
                                                   "site_env_var": "SCENARIO_CROSSWALK_SITE_PACKET",
                                                   "site_sha256_env_var": "SCENARIO_CROSSWALK_SITE_SHA256"},
                                "acquisition": {name: {
                                    "entrypoint": "analysis.py",
                                    "method": "Saved projection of SHA-verified original Native samples",
                                    "evidence": "channels/" + name + ".jsonl"}
                                    for name in ("original_body_polygon", "original_speed",
                                                 "activity_readback", "exception_readback",
                                                 "four_camera_frames")},
                                "candidates": []})
                entries[-1]["acquisition"]["jurisdiction_and_crossing_context"] = {
                    "entrypoint": "analysis.py", "method": "reviewed original site and source records",
                    "evidence": "channels/crosswalk_context.json"}
            else:
                entries[-1]["candidates"].append({
                    "id": "fallback1",
                    "construction": construction_path.relative_to(HERE).as_posix(),
                    "construction_sha256": sha(construction_path),
                    "changed_knobs": ["shared camera rig offset 0 to 2 m; case geometry, target and control unchanged"],
                    "trigger": {"source": "original four-view Native camera samples and crossing visibility review",
                                "metric": "complete vehicle body and crossing-marking visibility in approach/reference views",
                                "failure_condition": "primary fixed camera pose clips the original body or crossing extent"}})
    write(HERE / "execution-manifest.json", {
        "format": "worker-execution-manifest", "assignment_id": PLAN["assignment_id"],
        "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
        "cases": entries, "comparisons": PLAN["comparisons"]})
    return len(entries)


if __name__ == "__main__":
    print(build())
