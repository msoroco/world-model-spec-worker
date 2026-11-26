"""Complete CPU-backed fields of the source-gated draft; do not select delivery."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.source-gated-draft.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        kind = case_id.split("__")[-1]
        for candidate_id, candidate in (("primary", entry),
                                        ("fallback1", entry["candidates"][0])):
            log = HERE / ("cpu-nov26c-deferred-" + kind +
                          ("-offline.log" if candidate_id == "primary" else
                           "-fallback1-offline.log"))
            if json.loads(log.read_text()).get("offline_passed") is not True:
                raise ValueError("offline receipt changed: " + kind)
            command = (str(ROOT / ".venv-cpu/bin/python") + " " + str(ROOT / "runtime.py") +
                       " offline --manifest " + str(MANIFEST) + " --case " + case_id +
                       " --candidate " + candidate_id + " --output " +
                       str(ROOT / ".runtime-work/c158208-owner-nov26b/deferred-offline-v3/attempts" / kind / candidate_id) +
                       " --python " + str(ROOT / ".venv-cpu/bin/python"))
            candidate["offline"] = {"command": command, "exit_code": 0,
                                    "construction_sha256": candidate["construction_sha256"],
                                    "log": log.name, "log_sha256": sha(log)}
        fallback = entry["candidates"][0]
        fallback["trigger"] = {
            "source": "original 900-tick ego station and speed history",
            "metric": "ego clearance station by the 45 s capture limit",
            "failure_condition": "primary 4.0 m/s controller overshoots the reviewed stopping reference or fails to clear the source-reviewed intersection"}
        fallback["changed_knobs"] = ["candidate_target_speed_mps: 4.0 to 3.5"]
        entry["candidate_risk"] = {
            "status": "physical",
            "reason": "The source-reviewed stopping reference may be overshot at the primary engineering target speed; fallback reduces target speed while preserving case, geometry, cameras and observations.",
            "source_review_required": True}
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                    "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}
        entry["acquisition"] = {
            "ego_body_and_speed": {"entrypoint": "source_tick_capture.py",
                                   "method": "20 Hz original ego pose, body and velocity readback",
                                   "evidence": ["nearest-view-original-ticks.jsonl", "nearest-view-tick-seal.json"]},
            "through_vehicle_body_and_occupancy": {"entrypoint": "through_traffic_control.py",
                                                   "method": "original through-vehicle pose, body and occupancy history",
                                                   "evidence": ["nearest-view-original-ticks.jsonl"]},
            "nearest_view_raycast": {"entrypoint": "source_tick_capture.py",
                                     "method": "original line-of-sight probe at each captured world tick",
                                     "evidence": ["nearest-view-original-ticks.jsonl"]},
            "camera_pixels": {"entrypoint": "camera_sources.py",
                              "method": "four synchronized original camera PNG streams and encoded video",
                              "evidence": ["nearest-view-camera-manifest.json", "overview.mkv",
                                           "approach.mkv", "reference_corner.mkv", "driver_reference.mkv"]}}
        entry["post_capture"] = {
            "command": str(ROOT / ".venv-cpu/bin/python") + " " + str(ROOT / "runtime.py") +
                       " process-saved --manifest " + str(ROOT / "work" / HERE.name / "execution-manifest.json") +
                       " --case " + case_id + " --attempt ${C158208_ATTEMPT} --output ${C158208_SAVED_OUTPUT}" +
                       " --library " + str(ROOT / "runtime/library") +
                       " --validator ${C158208_ADAPTER_CHECK} --owner-release-receipt ${C158208_OWNER_RELEASE}",
            "owner_release_required_for_original_capture": True}
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return {"cpu_backed_draft_cases": len(manifest["cases"]),
            "draft_manifest_sha256": sha(MANIFEST),
            "selected": False, "source_grounded_sweeps_expanded": False}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
