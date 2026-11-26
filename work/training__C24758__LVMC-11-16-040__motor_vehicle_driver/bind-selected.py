"""Bind final-hash CPU selected cases and recorded-only evidence."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def rel(path):
    return str(Path(path).relative_to(HERE))


def main():
    manifest = json.loads((HERE / "draft-execution-manifest.json").read_text())
    manifest["status"] = "cpu_prepared_pending_original_native_review"
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.rsplit("__", 1)[-1]
        proof = HERE / "proofs" / suffix
        saved_root = REPO / ".runtime-work" / f"c24758-{suffix}-final2-saved-20261125"
        processing = saved_root / "v0001/processing.json"
        receipt = json.loads(processing.read_text())
        if (receipt.get("passed") is not True or receipt.get("recorded_only") is not True or
                receipt.get("candidate_id") != "primary" or receipt.get("case_id") != case or
                receipt.get("native_revision", {}).get("construction_sha256") != entry["construction_sha256"] or
                receipt.get("originals_preserved") is not True or
                receipt.get("final_video_checks", {}).get("frames") != 600):
            raise ValueError("Selected saved-only CPU proof differs: " + case)
        saved_log = proof / "saved.log"
        write(saved_log, {"command": "runtime.py process-saved", "case_id": case,
                          "recorded_only": True, "passed": True, "frames": 600,
                          "processing_receipt_sha256": sha(processing),
                          "originals_preserved": True, "physical_acceptance_claimed": False})
        entry["post_capture"] = {"recorded_only": True,
            "command": "runtime.py process-saved --manifest work/" + HERE.name +
                "/execution-manifest.json --case " + case +
                " --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER",
            "feedback_command": "cat $SAVED_OUTPUT/feedback.json # " + case,
            "test_log": rel(saved_log), "test_log_sha256": sha(saved_log), "test_exit_code": 0}
        physical = proof / "physical-preparation.json"
        entry["physical_preparation"] = {"receipt": rel(physical), "sha256": sha(physical)}
        entry["acquisition"] = {
            "ego_speed": {"entrypoint": "native_capture.py", "method": "original Native velocity magnitude at every frame",
                          "evidence": ["native-ego-readback.jsonl", "trace.jsonl"]},
            "ego_pose": {"entrypoint": "native_capture.py", "method": "original Native pose and heading at every frame",
                         "evidence": ["native-ego-readback.jsonl", "trace.jsonl"]},
            "distance_to_boundary": {"entrypoint": "native_capture.py", "method": "signed distance from original Native pose and map readback",
                                     "evidence": ["native-ego-readback.jsonl", "native-context-readback.json", "native-map-readback.xodr"]},
            "intersection_sight": {"entrypoint": "ray_inventory.py", "method": "original driver-eye rays and source-hashed independent pixel review",
                                   "evidence": ["native-ego-readback.jsonl", "frame-map.json", "review.json", "driver_reference.mkv"]},
            "entering_approach_visibility": {"entrypoint": "ray_inventory.py", "method": "ray inventory for every entering lane with source-hashed frame review",
                                             "evidence": ["native-context-readback.json", "native-ego-readback.jsonl", "review.json"]},
            "intersection_traversal": {"entrypoint": "native_capture.py", "method": "original Native junction and pose readback joined to frames",
                                       "evidence": ["native-ego-readback.jsonl", "video_frames.jsonl", "trace.jsonl"]}}
    write(HERE / "execution-manifest.json", manifest)
    first = json.loads((HERE / manifest["cases"][0]["construction"]).read_text())
    first["measurement_plan"] = {"entrypoint": "finalize.py",
        "required_sources": ["native-map-readback.xodr", "native-context-readback.json",
                             "native-ego-readback.jsonl", "frame-map.json", "review.json",
                             "trace.jsonl", "video_frames.jsonl", "driver_reference.mkv"]}
    first["static_checks"] = ["30 seconds at 20 Hz", "four original RGB source cameras",
        "1920x1080 overview", "entering-road ray inventory", "exact sight and exception review sources"]
    first["termination_rules"] = ["600 joined Native frames", "all encoders closed",
        "owned actors destroyed", "world settings restored before capture seal"]
    first["mechanisms"] = ["same intersection and capture plan; requested speed alone varies",
        "record original Native rays and readbacks; defer sight and exception judgment to review"]
    for item in first["files"]:
        destination = HERE / item["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(item["content"])
    write(HERE / "construction.json", first)
    print(json.dumps({"selected_cases": len(manifest["cases"]), "saved_only_passed": len(manifest["cases"])}))


if __name__ == "__main__":
    main()
