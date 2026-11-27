"""Deterministically bind eight exact Native constructions to shared source."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    if len(plan["cases"]) != 8:
        raise ValueError("eight exact branch cases required")
    source_files = {
        "runner.py": "runner.py",
        "native/bus_scene.py": "native/bus_scene.py",
        "native/bus_construction.py": "native/bus_construction.py",
        "native/bus_capture.py": "native/bus_capture.py",
        "analysis/independent_audits.py": "analysis/independent_audits.py",
        "analysis/saved_only.py": "analysis/saved_only.py",
        "finalize.py": "finalize.py",
        "tests/test_bus_scene.py": "native/test_bus_scene.py",
    }
    terms = list(plan["source_observation_mapping"])
    description = {
        "channels": [{"name": term, "unit": "structured", "sampling_rate_hz": 20,
                      "method": "source-hashed original bus/route/map/body/camera join; unknowns remain unknown",
                      "time_window": "all 600 frames", "reference_frame": "original Native frame",
                      "uncertainty": "actual loading, designation and exception require original review"}
                     for term in terms],
        "context_inputs": [{"name": name, "unit": "structured",
                            "method": "original source hash and frame identity"}
                           for name in ("native_map", "motion", "bus_body", "passenger_body",
                                        "camera_manifest")],
        "limitations": ["Authored route and zone category are requests, not legal designation.",
                        "Door request and pedestrian motion do not prove passenger exchange."]}
    entries = []
    for case in plan["cases"]:
        ident = case["case_id"]
        slug = ident.removeprefix(AID + "__")
        config = {"assignment_id": AID, "law_id": plan["law_id"], "cell_id": plan["cell_id"],
                  "actor": plan["actor"], "selected_case_id": ident,
                  "supported_case_ids": [item["case_id"] for item in plan["cases"]],
                  "case": {"case_id": ident}, "zone_kind_requested": case["requested_setting"],
                  "vehicle_class_requested": case["vehicle_class_requested"],
                  "emergency_requested": case["emergency_requested"],
                  "rate_hz": 20, "duration_s": 30,
                  "cameras": [
                      {"name": "overview", "width": 1920, "height": 1080,
                       "pose_strategy": "fixed street overhead", "fov_deg": 90},
                      {"name": "approach", "width": 1280, "height": 720,
                       "pose_strategy": "fixed curb approach", "fov_deg": 90},
                      {"name": "reference_corner", "width": 1280, "height": 720,
                       "pose_strategy": "fixed loading place", "fov_deg": 90},
                      {"name": "driver_reference", "width": 1280, "height": 720,
                       "pose_strategy": "attached bus interior", "fov_deg": 90}],
                  "required_atoms": [], "source_packets": [],
                  "recording_description": description}
        files = [{"path": target, "source": str((ROOT / source).relative_to(REPO)),
                  "content": (ROOT / source).read_text()} for target, source in source_files.items()]
        files.append({"path": "config.json", "content": json.dumps(config, indent=2) + "\n"})
        proposal = {"case_id": ident, "law_id": plan["law_id"], "cell_id": plan["cell_id"],
                    "actor": plan["actor"], "entrypoint": "runner.py", "files": files,
                    "status": "authored_original_unverified", "recording_description": description,
                    "measurement_plan": {"saved_only": "analysis/saved_only.py",
                                         "original_sources": ["bus_context.json", "bus_motion.jsonl",
                                                              "bus_body.jsonl", "passenger_body.jsonl",
                                                              "video_frames.jsonl"]},
                    "static_checks": ["scene geometry", "20 Hz timing", "four camera actors"],
                    "termination_rules": ["600 source frames", "restore world settings"],
                    "mechanisms": ["route bus and passenger actor", "curb loading zone marker",
                                   "door and walking requests"]}
        construction = ROOT / "cases" / slug / "construction.json"
        dump(construction, proposal)
        entries.append({"case_id": ident, "kind": "delivery",
                        "construction": str(construction.relative_to(ROOT)),
                        "construction_sha256": sha(construction),
                        "measurement_procedure": {"entrypoint": "finalize.py"},
                        "measurement_contract": "measurement-" + slug + ".json",
                        "fixture_recipe": "work/" + AID + "/selected-recipe-" + slug + ".json",
                        "recording_description": description,
                        "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                           "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
                        "candidate_risk": {"status": "none",
                                           "reason": "Curb camera and passenger crossing risk assessed; no tested alternate yet"},
                        "candidates": []})
    dump(ROOT / "draft-native-manifest.json", {"format": "worker-execution-manifest",
         "assignment_id": AID, "status": "draft_exact_offline",
         "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
         "physical_acceptance_claimed": False, "cases": entries})
    dump(ROOT / "proposals/cases.json", {"actor": plan["actor"],
         "cell_id": plan["cell_id"], "status": "proposed_original_unverified",
         "sweeps_expanded": True, "sweep_specs": [],
         "cases": [{"case_id": case["case_id"], "target_law_id": plan["law_id"],
                    "target_type": "selected_delivery_comparison",
                    "rationale": "exact statutory place, exception or bus-class contrast; original source pending",
                    "recording_description": description}
                   for case in plan["cases"]]})
    return len(entries)


if __name__ == "__main__":
    print(build())
