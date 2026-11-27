"""Bind six exact passenger-curb constructions to frozen source and cell identity."""

import hashlib
import json
from pathlib import Path

from native.loading_scene import CASES, request, validate

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
PREFIX = AID + "__selected_bae4893e__"
MODULES = ("native/loading_scene.py", "native/native_construction.py",
           "native/native_capture.py", "native/measure_loading_native.py", "finalize.py")
CHANNELS = ("st.curb_zone", "dev.regulatory_sign", "drv.condition_in_effect",
            "env.civil_time", "drv.standing_or_parked", "sig.door_open",
            "ru.occupant_count", "ru.pedestrian", "kin.time")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def description():
    return {"channels": [{"name": name, "unit": "structured",
        "sampling_rate_hz": 20,
        "method": "original Native source, body, sign or synchronized camera join; unobserved values remain unknown",
        "time_window": "all 600 frames including approach, curb halt and departure",
        "reference_frame": "original CARLA frame and civil sign time",
        "uncertainty": "Actual door, occupant transfer and sign authority require independent original review"}
        for name in CHANNELS],
        "context_inputs": [{"name": name, "unit": "structured",
            "method": "original Native source hash and frame identity"}
            for name in ("native_map", "loading_zone", "ego_body", "passenger_body", "camera_manifest")],
        "limitations": ["No legal expeditiousness cutoff is declared.",
                        "Authored sign and controller requests do not prove lawful authority or physical transfer."]}


def config(slug):
    scene = request(slug)
    cid = PREFIX + slug
    record = description()
    order = ("overview", "approach", "reference_corner", "driver_reference")
    return {"assignment_id": AID, "law_id": "NRS-484B-503", "cell_id": "C149498",
        "actor": "motor_vehicle_driver", "selected_case_id": cid,
        "case": {"case_id": cid, "recording_description": record},
        "supported_case_ids": [PREFIX + key for key in CASES],
        "required_atoms": [], "source_packets": [], "rate_hz": 20,
        "duration_s": 30, "frames": 600,
        "passenger_transfer_requested": CASES[slug],
        "signed_hours_effective_requested": not slug.startswith("outside_hours"),
        "action_request": scene["controller"]["action_request"],
        "resume_request_frame": scene["controller"]["resume_request_frame"],
        "cameras": [{"name": item["name"], "width": item["size"][0],
            "height": item["size"][1], "fps": 20, "fov_deg": 80,
            "pose_strategy": item["pose_strategy"]} for item in sorted(
                scene["cameras"], key=lambda item: order.index(item["name"]))],
        "recording_description": record, "physical_acceptance_claimed": False,
        "zone_regulatory_authority": "unverified_original_source",
        "expeditiousness": "unassessed"}


def build(slug):
    if slug not in CASES:
        raise ValueError("unknown exact passenger curb case")
    scene = request(slug)
    validate(scene)
    frozen = REPO / "inputs" / AID / "assignment.json"
    assignment = json.loads(frozen.read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    if (assignment["law"]["text"] != plan["source_law"]["text"] or
            assignment["cell"]["layout"] != "one_way_road" or
            assignment["cell"]["control"] != "loading_zone_marking" or
            assignment["cell"]["maneuver"] != "load_unload"):
        raise ValueError("Frozen law or passenger-curb cell differs")
    cid = PREFIX + slug
    cfg = config(slug)
    contract = {"format": "worker-measurement-contract", "case_id": cid,
        "status": "selected_cpu_draft", "negative": {"remove": ["loading_zone.json"],
            "error_contains": "Missing required source: loading_zone.json"},
        "requirements": [{"disposition_index": i,
            "requirement": item["requirement"], "source": item["source"],
            "kind": "measured", "method": "measure_zone_timing" if i == 0 else "measure_passenger_context",
            "output_key": "zone_timing" if i == 0 else "passenger_context", "value_type": "object",
            "inputs": ["loading_zone.json", "loading_motion.jsonl", "ego_body.jsonl",
                       "passenger_body.jsonl", "video_frames.jsonl"]}
            for i, item in enumerate(plan["requirement_dispositions"])
            if cid in item["case_ids"]],
        "legal_compliance": "unassessed"}
    contract_path = HERE / ("measurement-" + slug + ".json")
    put(contract_path, contract)
    files = [{"path": "runner.py", "source": str((HERE / "runner.py").relative_to(REPO)),
              "content": (HERE / "runner.py").read_text()}]
    for name in MODULES:
        path = HERE / name
        files.append({"path": name, "source": str(path.relative_to(REPO)),
                      "content": path.read_text()})
    test_path = HERE / "tests/test_native_construction.py"
    files.append({"path": "tests/test_native_construction.py",
                  "source": str(test_path.relative_to(REPO)),
                  "content": test_path.read_text()})
    files += [{"path": "config.json", "content": json.dumps(cfg, indent=2) + "\n"},
              {"path": "inputs/" + AID + "/assignment.json", "source": "inputs/" + AID + "/assignment.json",
               "content": frozen.read_text()},
              {"path": "work/" + AID + "/case-plan.json", "source": "work/" + AID + "/case-plan.json",
               "content": (HERE / "case-plan.json").read_text()}]
    construction = {"case_id": cid, "law_id": "NRS-484B-503", "cell_id": "C149498",
        "actor": "motor_vehicle_driver", "entrypoint": "runner.py", "files": files,
        "status": "selected_cpu_prepared_original_unverified",
        "recording_description": cfg["recording_description"],
        "measurement_plan": {"method": "source-body curb occupancy, sign hours and passenger proximity without legal judgment",
            "duration_s": 30, "source_observation_channels": list(CHANNELS)},
        "static_checks": ["one-way OpenDRIVE curb and sign readback",
                          "vehicle and passenger actor creation", "four original 20 Hz cameras",
                          "600 frame Native, Core and actor joins"],
        "termination_rules": ["600 frames", "camera encoder closure and world restore"],
        "mechanisms": ["CARLA OpenDRIVE passenger curb and sign",
                       "ego and pedestrian actor control",
                       "source-joined four-view FFV1 and Native telemetry"]}
    path = HERE / "selected" / slug / "construction.json"
    put(path, construction)
    return {"case_id": cid, "kind": "delivery",
        "construction": str(path.relative_to(HERE)), "construction_sha256": sha(path),
        "measurement_procedure": {"entrypoint": "finalize.py"},
        "measurement_contract": contract_path.name,
        "fixture_recipe": "work/" + AID + "/selected-recipe-" + slug + ".json",
        "recording_description": cfg["recording_description"],
        "native_handoff": {"python_env_var": "CARLA_PYTHON", "host_env_var": "CARLA_HOST",
                           "port_env_var": "CARLA_PORT"},
        "candidate_risk": {"status": "none", "reason": "No tested fallback yet; retain primary until physical risk is measured"},
        "candidates": []}


def main():
    entries = [build(slug) for slug in CASES]
    batch = json.loads((REPO / "batch.json").read_text())
    manifest = {"format": "worker-execution-manifest", "assignment_id": AID,
        "status": "draft_incomplete_proofs",
        "runtime_manifest_sha256": batch["runtime"]["source_manifest_sha256"],
        "physical_acceptance_claimed": False, "cases": entries}
    put(HERE / "draft-native-manifest.json", manifest)
    put(HERE / "config.json", config("condition_a"))
    root = json.loads((HERE / entries[0]["construction"]).read_text())
    put(HERE / "construction.json", root)
    return {"cases": len(entries), "manifest_sha256": sha(HERE / "draft-native-manifest.json")}


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True))
