"""Independent camera inventory and Native lifecycle gate for C110454.

Fixture mode proves source shape only. A physical acceptance result requires a
separate delivery audit with actual-pixel and physical-completion review.
"""
import json
import subprocess
import sys
from pathlib import Path

from source_join_audit import audit as source_audit, read, require, sha

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/pipeline"))
from scenario_pipeline.worker_exchange import media  # noqa: E402

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
DIMENSIONS = {"overview": [1920, 1080], "approach": [1280, 720],
              "reference_corner": [1280, 720], "driver_reference": [1280, 720]}


def check_camera(attempt, saved, name, *, decoded=None):
    path = attempt / (name + ".mkv")
    require(path.is_file(), "Missing original camera source: " + name)
    digest = sha(path)
    require(saved.get("original_source_hashes", {}).get(path.name) == digest,
            "Saved camera source hash differs: " + name)
    try:
        probe = json.loads(subprocess.check_output([
            "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,nb_read_frames",
            "-of", "json", str(path)], text=True))["streams"][0]
    except (subprocess.CalledProcessError, KeyError, IndexError) as error:
        raise ValueError("Camera probe failed: " + name) from error
    require([probe.get("width"), probe.get("height")] == DIMENSIONS[name] and
            probe.get("r_frame_rate") == "20/1" and
            int(probe.get("nb_read_frames", -1)) == 480,
            "Camera frame count, dimensions or rate differ: " + name)
    if decoded is not None:
        full = decoded.get(digest)
        if full is None:
            full = media.audit(path, 480)
            decoded[digest] = full
        require(full.get("video_sha256") == digest and full.get("frames") == 480 and
                full.get("dimensions") == DIMENSIONS[name],
                "Full camera decode differs: " + name)
    return {"sha256": digest, "frames": 480, "dimensions": DIMENSIONS[name],
            "full_decode_verified": decoded is not None}


def check_release(seal, exit_record, release, saved, handoff, case_id, candidate_id,
                  seal_sha256, exit_sha256, release_sha256, processing_sha256, cameras):
    """Check cross-record closure bindings; caller must verify original files."""
    construction_sha256 = saved.get("native_revision", {}).get("construction_sha256")
    events = ["capture_finished", "encoders_closed", "restoration_verified",
              "native_exit", "owner_released", "saved_processing_started"]
    require(isinstance(construction_sha256, str) and len(construction_sha256) == 64 and
            seal.get("native_revision", {}).get("construction_sha256") == construction_sha256 and
            seal.get("format") == "worker-sealed-capture" and
            seal.get("events") == events[:3] and seal.get("frames") == 480 and
            seal.get("provenance_kind") == "native" and
            seal.get("diagnostic_fixture") is False and
            exit_record.get("event") == "native_exit" and
            exit_record.get("native_process_exit_code") == 0 and
            exit_record.get("capture_command_failed") is False and
            exit_record.get("capture_seal_sha256") == seal_sha256 and
            exit_record.get("native_revision") == seal.get("native_revision") and
            release.get("event") == "owner_released" and
            release.get("operator_attested") is True and
            release.get("no_resource_operation_performed") is True and
            release.get("native_construction_sha256") == construction_sha256 and
            release.get("native_exit_sha256") == exit_sha256 and
            (saved.get("events") or [None])[0] == "saved_processing_started" and
            handoff.get("format") == "c110454-original-owner-handoff-v1" and
            handoff.get("case_id") == case_id and
            handoff.get("candidate_id") == candidate_id and
            handoff.get("construction_sha256") == construction_sha256 and
            handoff.get("capture_seal_sha256") == seal_sha256 and
            handoff.get("native_exit_sha256") == exit_sha256 and
            handoff.get("owner_release_sha256") == release_sha256 and
            handoff.get("processing_sha256") == processing_sha256 and
            handoff.get("events") == events and
            handoff.get("recording_accepted") is False and
            handoff.get("physical_or_legal_acceptance_claimed") is False and
            all(seal.get("sources", {}).get(name + ".mkv") == item["sha256"]
                for name, item in cameras.items()),
            "Native exit, owner release or camera seal differs")


def audit(attempt, processing_path, case_id, candidate_id, construction_sha256,
          *, diagnostic=False, decoded=None):
    attempt, processing_path = Path(attempt).resolve(), Path(processing_path).resolve()
    joined = source_audit(attempt, processing_path, case_id, candidate_id,
                          construction_sha256, diagnostic=diagnostic)
    saved = read(processing_path)
    receipt_path = attempt / "four-view-receipt.json"
    require(receipt_path.is_file(), "Four-view composition receipt missing")
    receipt = read(receipt_path)
    require(receipt.get("format") == "synchronized-four-view" and
            receipt.get("frames") == 480 and
            set(receipt.get("sources", {})) == set(CAMERAS) and
            receipt.get("primary_sha256") == sha(attempt / "raw.mkv") and
            receipt.get("frame_map_sha256") == sha(attempt / "video_frames.jsonl"),
            "Four-view composition binding differs")
    cameras = {}
    for name in CAMERAS:
        cameras[name] = check_camera(attempt, saved, name, decoded=decoded)
        require(receipt["sources"][name] == cameras[name]["sha256"],
                "Four-view source binding differs: " + name)
    if not diagnostic:
        seal_path, exit_path = attempt / "capture-seal.json", attempt / "native-exit.json"
        release_path = attempt / "owner-release.json"
        handoff_path = processing_path.parent / "owner-handoff.json"
        require(release_path.is_file() and handoff_path.is_file(),
                "Owner release handoff missing before saved processing")
        seal, exit_record, release, handoff = map(read, (seal_path, exit_path,
                                                       release_path, handoff_path))
        check_release(seal, exit_record, release, saved, handoff, case_id, candidate_id,
                      sha(seal_path), sha(exit_path), sha(release_path),
                      sha(processing_path), cameras)
    return {"format": "c110454-camera-lifecycle-cpu-v1", "case_id": case_id,
            "candidate_id": candidate_id, "source_join_sha256": joined["source_sha256"],
            "camera_sources": cameras, "diagnostic_fixture": diagnostic,
            "camera_source_shape_passed": True, "owner_release_verified": not diagnostic,
            "actual_pixels_reviewed": False, "physical_completion_verified": False,
            "passed": False, "delivery_accepted": False}
