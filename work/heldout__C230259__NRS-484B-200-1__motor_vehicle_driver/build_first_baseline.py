"""Build the first C230259 exact two-way baseline construction for CPU proof."""

from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
CASE = ASSIGNMENT + "__baseline_right"


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def build():
    if (HERE / "execution-manifest.json").exists():
        raise ValueError("Retain prior baseline manifest; rebind deliberately after source changes")
    cameras = [("overview", 1920, 1080, 95), ("approach", 1280, 720, 90),
               ("reference_corner", 1280, 720, 100),
               ("driver_reference", 1280, 720, 85)]
    description = {"channels": [{
        "name": "right_half_observation", "unit": "m", "sampling_rate_hz": 20,
        "method": "joined original Native full-body and directed two-way road geometry",
        "time_window": "all 80 original frames", "reference_frame": "road centerline",
        "uncertainty": "Native map lane-width and actor bounding-box precision"}],
        "context_inputs": [{"name": "road_exception_context", "unit": "structured context",
                            "method": "separately reviewed original premise inventory"}],
        "limitations": ["Physical motion, width sufficiency and legal exception applicability remain unconfirmed."]}
    config = {"selected_case_id": CASE, "law_id": "NRS-484B-200-1",
              "cell_id": "C230259", "actor": "motor_vehicle_driver",
              "rate_hz": 20, "frames": 80, "duration_s": 4,
              "required_atoms": [], "source_packets": [],
              "cameras": [{"name": name, "width": width, "height": height,
                           "fov_deg": fov,
                           "pose_strategy": "subject-mounted provisional whole-road/body source view"}
                          for name, width, height, fov in cameras],
              "case": {"case_id": CASE, "recording_description": description},
              "supported_case_ids": [CASE]}
    (HERE / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    paths = ["config.json", "runner.py", "right_half_cameras.py",
             "right_half_route.py", "road_source_capture.py",
             "right_half_measurement.py", "right_half_finalizer.py",
             "right_half_comparison_audit.py", "tests/test_runner_config.py",
             "tests/test_right_half_cameras.py"]
    construction = {"format": "worker-construction", "case_id": CASE,
                    "law_id": config["law_id"], "cell_id": config["cell_id"],
                    "actor": config["actor"], "entrypoint": "runner.py",
                    "recording_description": description,
                    "files": [{"path": path, "content": (HERE / path).read_text()}
                              for path in paths],
                    "measurement_plan": {
                        "original_sources": ["ego_road_frames.jsonl",
                                             "road_exception_context.json",
                                             "video_frames.jsonl", "trace.jsonl",
                                             *[name + ".mkv" for name, *_ in cameras]],
                        "derived_channels": ["right_half_observation"],
                        "saved_only_finalizer": "right_half_finalizer.py"},
                    "static_checks": ["Exact C230259 identity, 80 original ticks at 20 Hz",
                                      "Connected Native two-way road and full actor body readback",
                                      "Four named synchronized lossless source cameras",
                                      "Saved original road/frame/trace joins"],
                    "termination_rules": ["Stop after 80 original ticks",
                                          "Fail on missing actor, source frame or road-center geometry",
                                          "Close encoders and restore world settings"],
                    "mechanisms": {"route": "connected opposing-lane Native selector",
                                   "control": "bounded route/speed feedback with same-direction lead",
                                   "capture": "four FFV1 source cameras, PipelineCapture, FrameMap and road/body recorder",
                                   "construction_status": "first_exact_primary_cpu_proof_pending"}}
    construction_path = HERE / "construction.json"
    construction_path.write_text(json.dumps(construction, indent=2) + "\n")
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                "runtime_manifest_sha256": digest(ROOT / "runtime/SOURCE-MANIFEST.json"),
                "cases": [{"case_id": CASE, "kind": "delivery",
                           "construction": "construction.json",
                           "construction_sha256": digest(construction_path),
                           "measurement_procedure": {"entrypoint": "right_half_finalizer.py"},
                           "candidate_risk": {"status": "physical",
                                              "reason": "Two-way map geometry, opposite-side motion and four-camera visibility need Native verification"},
                           "candidates": []}]}
    manifest_path = HERE / "execution-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return {"case_id": CASE, "construction_sha256": digest(construction_path),
            "manifest_sha256": digest(manifest_path)}


if __name__ == "__main__":
    print(json.dumps(build()))
