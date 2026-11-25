"""Select exact parked-side deliveries with separately gated notice sources."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
LAW = "NRS-484B-493"
CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))
CHANNELS = ("vehicle_footprint", "notice_and_street_context", "dev.regulatory_sign",
            "dev.governs", "st.one_way_roadway", "st.lane_direction",
            "drv.standing_or_parked", "rel.occupies")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def build():
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    ids = [ASSIGNMENT + "__controlled_1", ASSIGNMENT + "__controlled_2"]
    plan["requirement_dispositions"] = [
        {"requirement": "text-0-activation", "source": "NRS 484B.493",
         "source_text": "When official traffic-control devices are erected giving notice thereof,",
         "status": "selected_required", "case_ids": ids,
         "evidence_or_gap": "Separate official source and legal one-way designation are required; authored OpenDRIVE signal alone cannot supply them."},
        {"requirement": "text-0-side", "source": "NRS 484B.493",
         "source_text": "a person shall not stand or park a vehicle upon the left-hand side of a one-way street.",
         "status": "selected_required", "case_ids": ids,
         "evidence_or_gap": "Exact opposite parked-side requests selected; source-observed stationary footprint and legal purpose need original review."}]
    plan["source_topic_inventory"] = [
        {"topic_id": "text-0", "kind": "statutory_text",
         "text": "When official traffic-control devices are erected giving notice thereof, a person shall not stand or park a vehicle upon the left-hand side of a one-way street.",
         "source": "NRS 484B.493"},
        {"topic_id": "reviewed-scope-0", "kind": "reviewed_scope",
         "text": "park_left_side", "source": "inputs/planning/focused-coverage-20261016-v1/coverage-witnesses.json"}]
    for case in plan["cases"]:
        case["kind"] = "selected_delivery_cpu_preparation"
        case["planning_status"] = "selected_cpu_preparation_in_progress"
    plan["source_observation_mapping"] = {name: {
        "evidence": "Saved original footprint/frame join and separately reviewed source records; physical pixels and legal purpose pending.",
        "channels": [name],
        "source_refs": ["vehicle-pose.jsonl", "video_frames.jsonl", "road-context.json",
                        "authority-review/device-authority.json"]}
        for name in CHANNELS if name in {item["term"] for item in
                                     json.loads((ROOT / "inputs" / ASSIGNMENT / "assignment.json").read_text())["source_observation_terms"]}}
    plan["camera_plan"] = {"profile": "overview1080-capability", "duration_s": 30,
        "composition": "synchronized_four_view_primary",
        "coverage": [{"view": name, "subject": "ego vehicle and posted left-side notice",
                      "interval": "all 600 source frames"} for name, _, _ in CAMERAS]}
    plan["controlled_activation_negatives"] = [
        {"kind": "absent_notice", "source_role": "device-content",
         "expected": "Required activation unverified: device-content",
         "proof": "finalizer-source-proof.log"},
        {"kind": "two_way", "source_role": "one-way-designation",
         "expected": "Required activation unverified: one-way-designation",
         "proof": "finalizer-source-proof.log"}]
    plan["runtime_uncertainties"] = [
        "Official device authority, erection, notice content, one-way legal designation and street boundary need separate original sources; no supplied accepted recording proves them.",
        "Standing versus parking purpose and activity need original review; stationary speed is not a legal definition.",
        "Original Native curb motion, sign pixels, camera framing and legal applicability remain unverified."]
    write(plan_path, plan)
    description = {"channels": [{"name": name, "unit": "structured",
        "sampling_rate_hz": 20, "time_window": "600 original frames",
        "method": "saved Native footprint/frame join plus separate review records",
        "reference_frame": "permitted street direction and original Native frame",
        "uncertainty": "50 ms cadence; official status, purpose and physical pixels need original review"}
        for name in CHANNELS],
        "context_inputs": [],
        "limitations": ["Authored sign and road geometry do not establish official authority or legal designation; stationary motion does not define stand or park."]}
    entries, proposals = [], []
    for suffix, side in (("controlled_1", "right"), ("controlled_2", "left")):
        case = ASSIGNMENT + "__" + suffix
        config = {"case_id": case, "selected_case_id": case,
                  "law_id": LAW, "cell_id": "C135709", "actor": "motor_vehicle_driver",
                  "rate_hz": 20, "duration_s": 30, "duration_frames": 600,
                  "candidate_id": "primary", "moving_throttle": .18,
                  "brake_start_frame": 210, "required_atoms": [], "source_packets": [],
                  "source_actor_ids": ["ego"], "parking_side": side,
                  "cameras": [{"name": name, "fps": 20, "width": width,
                      "height": height, "pose_strategy": "fixed authored curb and sign view",
                      "fov_deg": 85} for name, width, height in CAMERAS],
                  "physical_verified": False, "legal_verdict": None,
                  "recording_description": description}
        config["case"] = {"case_id": case, "recording_description": description}
        files = [{"path": "config.json", "content": json.dumps(config, indent=2) + "\n"}]
        files += [{"path": target, "content": (HERE / source).read_text()}
                  for target, source in (("runner.py", "native/runner.py"),
                      ("geometry.py", "native/geometry.py"),
                      ("one_way_saved_measure.py", "one_way_saved_measure.py"),
                      ("source_review.py", "source_review.py"),
                      ("finalize.py", "native/finalize.py"),
                      ("tests/test_native.py", "native/tests/test_native.py"))]
        construction = {"format": "worker-inline-construction", "case_id": case,
            "cell_id": "C135709", "actor": "motor_vehicle_driver",
            "entrypoint": "runner.py", "files": files,
            "recording_description": description,
            "measurement_plan": "Retain original 600-frame vehicle footprint and four cameras; bind separate operator-reviewed one-way, boundary, authority, notice and erection sources before saved side analysis.",
            "static_checks": ["exact law/cell/actor", "600 frames at 20 Hz",
                              "four source cameras", "no legal verdict"],
            "termination_rules": ["600 original frames or explicit Native capture failure"],
            "mechanisms": ["authored one-way narrow street with left notice proposal",
                           "Native curbside vehicle and four FFV1 encodes",
                           "PipelineCapture, FrameMap and sealed original trace",
                           "saved-only separately sourced notice and footprint meter"],
            "status": "selected_delivery_cpu_in_progress"}
        primary_rel = f"native/{suffix}/construction.json"
        write(HERE / primary_rel, construction)
        fallback = json.loads(json.dumps(construction))
        fallback_config = json.loads(fallback["files"][0]["content"])
        fallback_config.update(candidate_id="fallback1", moving_throttle=.23,
                               brake_start_frame=260)
        fallback["files"][0]["content"] = json.dumps(fallback_config, indent=2) + "\n"
        fallback["status"] = "physical_stop_extent_fallback_cpu_request"
        fallback_rel = f"fallbacks/{suffix}/fallback1/construction.json"
        write(HERE / fallback_rel, fallback)
        contract_rel = f"selected-measurements/{suffix}/measurement-contract.json"
        write(HERE / contract_rel, {"format": "worker-measurement-contract",
            "case_id": case, "requirements": [
                {"disposition_index": 0, "requirement": "text-0-activation",
                 "source": "NRS 484B.493", "output_key": "notice_context",
                 "method": "measure_notice_context", "value_type": "object",
                 "kind": "sourced_context", "inputs": ["authority-review/device-authority.json",
                    "authority-review/one-way-designation.json", "road.xodr"]},
                {"disposition_index": 1, "requirement": "text-0-side",
                 "source": "NRS 484B.493", "output_key": "stationary_side",
                 "method": "measure_stationary_side", "value_type": "object",
                 "kind": "measured", "inputs": ["vehicle-pose.jsonl",
                    "video_frames.jsonl", "road-context.json"]}],
            "negative": {"remove": ["authority-review/device-authority.json"],
                "error_contains": "Missing required source: authority-review/device-authority.json"}})
        entries.append({"case_id": case, "kind": "delivery",
            "construction": primary_rel, "construction_sha256": sha(HERE / primary_rel),
            "candidate_risk": {"status": "physical",
                "reason": "Primary may brake outside the governed curb extent or leave the shoulder in Native dynamics."},
            "candidates": [{"id": "fallback1", "construction": fallback_rel,
                "construction_sha256": sha(HERE / fallback_rel),
                "trigger": {"source": "original Native vehicle-pose.jsonl and reviewed street extent",
                    "metric": "stationary footprint within governed extent and curb shoulder",
                    "failure_condition": "primary stops outside governed extent or fails to settle at requested curb"},
                "changed_knobs": ["moving_throttle .18 to .23",
                                  "brake_start_frame 210 to 260"]}],
            "measurement_procedure": {"entrypoint": "finalize.py"},
            "measurement_contract": contract_rel,
            "fixture_recipe": f"work/{ASSIGNMENT}/diagnostic-{suffix}-recipe.json",
            "delivery_readiness": "incomplete", "id": "primary"})
        proposals.append({"case_id": case, "target_law_id": LAW,
            "target_type": "compliant_attempt" if side == "right" else "violating_attempt",
            "rationale": "Frozen left-side parking witness with exact opposite curb-side comparison",
            "paired_probe_id": "c135709_parking_side",
            "deliberate_differences": ["parking_side"],
            "probe": {"primary_variable": "parking_side",
                      "comparison_or_standard": "left side of sourced one-way street",
                      "target_value_or_branch": side},
            "variable_assignments": {"parking_side": {"kind": "controller", "value": side}},
            "recording_description": description,
            "unresolved_judgment_calls": ["official authority and erection",
                "one-way legal designation", "stand or park legal purpose"]})
    write(HERE / "execution-manifest.json", {"format": "worker-execution-manifest",
        "assignment_id": ASSIGNMENT,
        "runtime_manifest_sha256": json.loads((ROOT / "batch.json").read_text())["runtime"]["source_manifest_sha256"],
        "status": "selected_delivery_cpu_in_progress", "cases": entries})
    write(HERE / "proposals/cases.json", {"cell_id": "C135709",
        "actor": "motor_vehicle_driver", "status": "draft",
        "sweep_specs": [], "sweeps_expanded": True,
        "cases": proposals})
    print(json.dumps({"cases": [{"case_id": e["case_id"],
        "construction_sha256": e["construction_sha256"]} for e in entries]}, indent=2))


if __name__ == "__main__":
    build()
