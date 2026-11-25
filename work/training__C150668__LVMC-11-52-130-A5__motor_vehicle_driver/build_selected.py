"""Build exact selected Native requests with explicit original fixture-source gates."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))
CHANNELS = ("st.obstruction", "st.sidewalk", "rel.centre_distance",
            "drv.standing_or_parked", "rel.occupies", "kin.extent")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def build():
    description = {"channels": [{"name": name, "unit": "structured",
        "sampling_rate_hz": 20, "time_window": "600 original frames",
        "method": "saved Native footprint/frame join and separately reviewed fixture source roles",
        "reference_frame": "original Native frame and one-way sidewalk fixture",
        "uncertainty": "50 ms cadence; fixture identity and frontage require original review"}
        for name in CHANNELS], "context_inputs": [],
        "limitations": ["A box prop is not an elevator or chute; traffic conflict and officer/device direction require separate original sources."]}
    entries = []
    for suffix, stop_case in (("probe_1", "outside"), ("probe_2", "side_band")):
        case = ASSIGNMENT + "__" + suffix
        contract_rel = f"selected-measurements/{suffix}/measurement-contract.json"
        write(HERE / contract_rel, {"format": "worker-measurement-contract",
            "case_id": case, "requirements": [{"disposition_index": 0,
                "requirement": "text-0-side-band", "source": "LVMC 11.52.130(A)(5)",
                "output_key": "fixture_stop", "method": "measure_fixture_stop",
                "value_type": "object", "kind": "measured",
                "inputs": ["vehicle-poses.jsonl", "video_frames.jsonl",
                           "fixture-review/fixture-identity.json",
                           "fixture-review/fixture-geometry.json",
                           "fixture-review/sidewalk-geometry.json",
                           "fixture-review/front-orientation.json", "road.xodr"]}],
            "negative": {"remove": ["fixture-review/fixture-identity.json"],
                "error_contains": "Missing required source: fixture-review/fixture-identity.json"}})
        candidates = []
        for candidate, margin in (("primary", 1.5), ("fallback1", 2.0)):
            config = {"case_id": case, "selected_case_id": case,
                "supported_case_ids": [ASSIGNMENT + "__probe_1", ASSIGNMENT + "__probe_2"],
                "candidate_id": candidate, "law_id": "LVMC-11-52-130-A5",
                "cell_id": "C150668", "actor": "motor_vehicle_driver",
                "stop_case": stop_case, "brake_margin_m": margin,
                "rate_hz": 20, "duration_s": 30, "duration_frames": 600,
                "required_atoms": [], "source_packets": [], "source_actor_ids": ["ego"],
                "case": {"case_id": case, "recording_description": description},
                "cameras": [{"name": name, "fps": 20, "width": width,
                    "height": height, "pose_strategy": "fixed sidewalk and approach view",
                    "fov_deg": 85} for name, width, height in CAMERAS],
                "recording_description": description,
                "physical_verified": False, "legal_verdict": None}
            files = [{"path": "config.json", "content": json.dumps(config, indent=2) + "\n"}]
            for name in ("runner.py", "geometry.py", "stop_route.py", "measure_fixture.py",
                         "source_review.py", "finalize.py"):
                files.append({"path": name, "content": (HERE / "native" / name).read_text()})
            files.append({"path": "tests/test_native.py", "content":
                          (HERE / "native/tests/test_native.py").read_text()})
            construction = {"format": "worker-inline-construction",
                "case_id": case, "cell_id": "C150668", "actor": "motor_vehicle_driver",
                "entrypoint": "runner.py", "files": files,
                "recording_description": description,
                "measurement_plan": "Saved original 600-frame body/map/camera join; require reviewed elevator/chute identity, geometry and front orientation source bytes.",
                "static_checks": ["exact law/cell/actor", "600 frames at 20 Hz",
                                  "four canonical source cameras", "no legal verdict"],
                "termination_rules": ["600 original frames or explicit Native failure"],
                "mechanisms": ["one-way authored street and sidewalk fixture proxy",
                               "feedback stop controller with requested station and brake margin",
                               "saved-only source-gated fixture meter"],
                "status": "selected_cpu_source_dependency"}
            rel = (f"native/{suffix}/construction.json" if candidate == "primary" else
                   f"fallbacks/{suffix}/fallback1/construction.json")
            write(HERE / rel, construction)
            candidates.append((rel, sha(HERE / rel)))
        primary, fallback = candidates
        entries.append({"case_id": case, "kind": "delivery",
            "construction": primary[0], "construction_sha256": primary[1],
            "candidate_risk": {"status": "physical",
                "reason": "Native braking may stop outside the requested side band or fail to settle."},
            "candidates": [{"id": "fallback1", "construction": fallback[0],
                "construction_sha256": fallback[1],
                "trigger": {"source": "original Native vehicle-poses.jsonl and reviewed fixture geometry",
                    "metric": "stationary vehicle-body side clearance",
                    "failure_condition": "primary stop misses requested side-band target"},
                "changed_knobs": ["brake_margin_m 1.5 to 2.0"]}],
            "measurement_procedure": {"entrypoint": "finalize.py"},
            "measurement_contract": contract_rel,
            "fixture_recipe": f"work/{ASSIGNMENT}/diagnostic-{suffix}-recipe.json",
            "delivery_readiness": "incomplete_original_fixture_source_pending",
            "id": "primary"})
    write(HERE / "execution-manifest.json", {"format": "worker-execution-manifest",
        "assignment_id": ASSIGNMENT,
        "runtime_manifest_sha256": json.loads((ROOT / "batch.json").read_text())["runtime"]["source_manifest_sha256"],
        "status": "selected_cpu_source_dependency", "cases": entries})
    return {"cases": [{"case_id": x["case_id"],
                       "construction_sha256": x["construction_sha256"]} for x in entries]}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
