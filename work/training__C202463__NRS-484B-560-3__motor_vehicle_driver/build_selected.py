"""Build five exact source-gated rail-stop Native construction requests."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))
CHANNELS = ("st.railway_crossing", "drv.stopped", "st.road_edge", "rel.occupies",
            "rel.longitudinal_overlap", "drv.laned_roadway", "st.lane_adjacency",
            "st.lane_marking")
VARIANTS = (("probe_a", "right_single", 2), ("probe_b", "left_single", 2),
            ("probe_c", "left_abreast", 2), ("probe_d", "left_abreast", 4),
            ("probe_e", "left_abreast", 5))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def build():
    description = {"channels": [{"name": name, "unit": "structured",
        "sampling_rate_hz": 20, "time_window": "600 original Native frames",
        "method": "source-reviewed saved actor, gate, road, marked-lane and video joins",
        "reference_frame": "original Native frame and reviewed crossing",
        "uncertainty": "50 ms cadence; stop authority and rightmost possible require independent source review"}
        for name in CHANNELS], "context_inputs": [],
        "limitations": ["Gate indication alone does not establish stop authority; far-right possibility and legal verdict remain source-reviewed judgments."]}
    entries, proposals = [], []
    for suffix, queue_mode, lanes in VARIANTS:
        case = ASSIGNMENT + "__" + suffix
        contract = f"selected-measurements/{suffix}/measurement-contract.json"
        roles = (("required-stop", "measure_required_stop", "required_stop", "sourced_context",
                  ["rail-review/required-stop.json", "rail-review/required-stop.source.txt", "gate.jsonl", "road.xodr"]),
                 ("far-right", "measure_far_right", "far_right", "measured",
                  ["actors.jsonl", "geometry.json", "rail-review/right-edge.json", "rail-review/right-availability.json"]),
                 ("two-lanes", "measure_two_lanes", "two_lanes", "measured",
                  ["actors.jsonl", "gate.jsonl", "geometry.json", "video_frames.jsonl"]),
                 ("four-lane-qualifier", "measure_marked_lanes", "marked_lanes", "sourced_context",
                  ["road.xodr", "rail-inventory.json", "rail-review/lane-markings.json",
                   "rail-review/lane-markings.source.txt"]))
        write(HERE / contract, {"format": "worker-measurement-contract", "case_id": case,
            "requirements": [{"disposition_index": i, "requirement": req,
                "source": "NRS 484B.560(3)", "output_key": key, "method": method,
                "value_type": "object", "kind": kind, "inputs": inputs}
                for i, (req, method, key, kind, inputs) in enumerate(roles)],
            "negative": {"remove": ["rail-review/required-stop.json"],
                "error_contains": "Missing required source: rail-review/required-stop.json"}})
        candidates = []
        for candidate, margin in (("primary", 1.5), ("fallback1", 2.0)):
            config = {"case_id": case, "selected_case_id": case,
                "supported_case_ids": [ASSIGNMENT + "__" + s for s, _, _ in VARIANTS],
                "candidate_id": candidate, "law_id": "NRS-484B-560-3",
                "cell_id": "C202463", "actor": "motor_vehicle_driver",
                "queue_mode": queue_mode, "marked_lane_count": lanes,
                "brake_margin_m": margin, "rate_hz": 20, "duration_s": 30,
                "duration_frames": 600, "required_atoms": [], "source_packets": [],
                "source_actor_ids": ["ego", "other"],
                "case": {"case_id": case, "recording_description": description},
                "cameras": [{"name": name, "fps": 20, "width": width, "height": height,
                    "pose_strategy": "fixed reviewed rail crossing and approach view",
                    "fov_deg": 85} for name, width, height in CAMERAS],
                "recording_description": description,
                "physical_verified": False, "legal_verdict": None}
            files = [{"path": "config.json", "content": json.dumps(config, indent=2) + "\n"}]
            for name in ("runner.py", "source_review.py", "measure_rail_queue.py", "finalize.py"):
                files.append({"path": name, "content": (HERE / "native" / name).read_text()})
            files.append({"path": "tests/test_native.py",
                          "content": (HERE / "native/tests/test_native.py").read_text()})
            construction = {"format": "worker-inline-construction", "case_id": case,
                "cell_id": "C202463", "actor": "motor_vehicle_driver",
                "entrypoint": "runner.py", "files": files,
                "recording_description": description,
                "measurement_plan": "Saved 600-frame original gate/actor/camera join and separately reviewed stop authority, crossing, right edge, right availability and all marked lanes.",
                "static_checks": ["exact law/cell/actor", "600 frames at 20 Hz",
                    "four canonical source cameras", "required-stop authority independent of gate state",
                    "no legal verdict"],
                "termination_rules": ["600 original frames or explicit Native failure"],
                "mechanisms": ["original reviewed railroad crossing and gate acquisition",
                    "two vehicle controller with lateral queue position",
                    "source-gated marked-lane count below, at and above four",
                    "saved-only source-gated rail meter"],
                "status": "selected_cpu_source_dependency"}
            rel = (f"native/{suffix}/construction.json" if candidate == "primary" else
                   f"fallbacks/{suffix}/fallback1/construction.json")
            write(HERE / rel, construction)
            candidates.append((rel, sha(HERE / rel)))
        primary, fallback = candidates
        entries.append({"case_id": case, "kind": "delivery",
            "construction": primary[0], "construction_sha256": primary[1],
            "candidate_risk": {"status": "physical",
                "reason": "Native braking or vehicle occupancy may miss the requested stopped position."},
            "candidates": [{"id": "fallback1", "construction": fallback[0],
                "construction_sha256": fallback[1],
                "trigger": {"source": "original Native actors.jsonl and reviewed road/gate sources",
                    "metric": "settled stop position and right-edge/queue frame measurement",
                    "failure_condition": "primary fails to settle at requested rail queue geometry"},
                "changed_knobs": ["brake_margin_m 1.5 to 2.0"]}],
            "measurement_procedure": {"entrypoint": "finalize.py"},
            "measurement_contract": contract,
            "fixture_recipe": f"work/{ASSIGNMENT}/diagnostic-{suffix}-recipe.json",
            "delivery_readiness": "incomplete_original_rail_source_pending", "id": "primary"})
        proposals.append({"case_id": case, "target_law_id": "NRS-484B-560-3",
            "target_type": "boundary_probe" if suffix in ("probe_c", "probe_d", "probe_e") else "judgment_sweep",
            "rationale": "Required-stop rail queue duties and marked-lane qualifier with original authority gate",
            "paired_probe_id": "c202463_rail_queue_and_lanes",
            "deliberate_differences": ["marked_lane_count"] if suffix in ("probe_d", "probe_e") else ["queue_mode"],
            "probe": {"primary_variable": "marked_lane_count" if suffix in ("probe_c", "probe_d", "probe_e") else "queue_mode",
                "comparison_or_standard": "four or more marked lanes at required rail stop",
                "target_value_or_branch": lanes if suffix in ("probe_c", "probe_d", "probe_e") else queue_mode,
                **({"threshold_ref": "obligation.numeric_conditions[0]", "operator": ">=",
                    "unit": "lanes", "test_value": lanes} if suffix in ("probe_c", "probe_d", "probe_e") else {})},
            **({"epsilon_used": {"value": 1, "unit": "lanes",
                "rationale": "Integer marked-lane count brackets exact four-lane statutory boundary."}}
                if suffix in ("probe_c", "probe_d", "probe_e") else {}),
            "variable_assignments": {"queue_mode": {"kind": "controller", "value": queue_mode},
                "marked_lane_count": {"kind": "world_setup", "value": lanes}},
            "recording_description": description,
            "unresolved_judgment_calls": ["independent required-stop authority",
                "rightmost possible position in sourced traffic and road context"]})
    write(HERE / "execution-manifest.json", {"format": "worker-execution-manifest",
        "assignment_id": ASSIGNMENT,
        "runtime_manifest_sha256": json.loads((ROOT / "batch.json").read_text())["runtime"]["source_manifest_sha256"],
        "status": "selected_cpu_source_dependency", "cases": entries})
    write(HERE / "proposals/cases.json", {"cell_id": "C202463", "actor": "motor_vehicle_driver",
        "status": "draft", "sweep_specs": [], "sweeps_expanded": True, "cases": proposals})
    return {"case_count": len(entries), "construction_sha256": [e["construction_sha256"] for e in entries]}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
