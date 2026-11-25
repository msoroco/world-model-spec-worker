"""Saved-only measurements of the original nearest-view and signal sources.

This finalizer reports observations. It never decides immediate hazard, legal
right of way, or physical visibility from a synthetic fixture.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
from pathlib import Path
from zipfile import ZipFile

from PIL import Image

from nearest_view import measure as measure_yield, verify_source_bytes
from signal_exception import measure as measure_signal

ASSIGNMENT = "testing__C158196__NRS-484B-257-1__motor_vehicle_driver"
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
DIMENSIONS = ((1920, 1080), (1280, 720), (1280, 720), (1280, 720))


def _source(attempt: Path, name: str) -> tuple[Path, str]:
    path = attempt / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    body = path.read_bytes()
    if not body:
        raise ValueError("Empty required source: " + name)
    return path, hashlib.sha256(body).hexdigest()


def report(attempt: Path) -> dict:
    attempt = Path(attempt).resolve()
    packet_path, packet_hash = _source(attempt, "nearest-view-original.json")
    camera_path, camera_hash = _source(attempt, "camera-frame-map.json")
    camera_receipt_path, camera_receipt_hash = _source(attempt, "camera-sources.json")
    packet = json.loads(packet_path.read_text())
    case_id = packet.get("case_id")
    if not isinstance(case_id, str) or not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("wrong exact saved case")
    suffix = case_id.rsplit("__", 1)[1]
    if suffix not in ("nearest_view_hold", "nearest_view_continue",
                      "nearest_view_clear", "active_signal_exception"):
        raise ValueError("unknown exact saved case")
    verify_source_bytes(packet, attempt)
    camera_rows = json.loads(camera_path.read_text())
    frames = packet.get("frames")
    if not isinstance(frames, list) or len(frames) != 900 or not isinstance(camera_rows, list) or len(camera_rows) != 900:
        raise ValueError("original 900-frame source and camera map required")
    for frame, camera in zip(frames, camera_rows):
        if camera.get("frame") != frame.get("frame") or set(camera.get("pixel_sha256", {})) != set(VIEWS):
            raise ValueError("original camera and body frame join differs")
        for digest in camera["pixel_sha256"].values():
            if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise ValueError("original camera pixel hash invalid")
    camera_receipt = json.loads(camera_receipt_path.read_text())
    diagnostic = camera_receipt.get("format") == "c158196-diagnostic-four-camera-sources-v1"
    if (camera_receipt.get("case_id") != case_id or
            camera_receipt.get("frame_map_sha256") != camera_hash or
            set(camera_receipt.get("sources", {})) != set(VIEWS)):
        raise ValueError("original camera source receipt differs")
    if diagnostic:
        provenance_path, _ = _source(attempt, "fixture-provenance.json")
        provenance = json.loads(provenance_path.read_text())
        if (provenance.get("diagnostic_fixture") is not True or
                provenance.get("physical_acceptance_claimed") is not False or
                camera_receipt.get("diagnostic") is not True):
            raise ValueError("untrusted diagnostic camera provenance")
        for name in VIEWS:
            ref = camera_receipt["sources"][name]
            video, _ = _source(attempt, name + ".mkv")
            if ref.get("path") != video.name or ref.get("frame_count") != 900:
                raise ValueError(name + " diagnostic video source differs")
            probe = json.loads(subprocess.check_output([
                "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                "-show_entries", "stream=nb_read_frames", "-of", "json", str(video)],
                text=True))
            if int(probe["streams"][0]["nb_read_frames"]) != 900:
                raise ValueError(name + " diagnostic video frame count differs")
    else:
        if camera_receipt.get("format") != "c158196-original-four-camera-sources-v1":
            raise ValueError("original camera source receipt differs")
        for name, dimensions in zip(VIEWS, DIMENSIONS):
            ref = camera_receipt["sources"][name]
            archive, archive_hash = _source(attempt, name + ".png.zip")
            if (ref.get("path") != archive.name or ref.get("sha256") != archive_hash or
                    ref.get("frame_count") != 900 or ref.get("dimensions") != list(dimensions)):
                raise ValueError(name + " original camera archive source differs")
            with ZipFile(archive) as source:
                expected = [f"{frame['frame']:08d}.png" for frame in frames]
                if source.namelist() != expected:
                    raise ValueError(name + " original camera archive frame identities differ")
                for row, path in zip(camera_rows, expected):
                    encoded = source.read(path)
                    if hashlib.sha256(encoded).hexdigest() != row["pixel_sha256"][name]:
                        raise ValueError(name + " original camera pixels differ")
                    with Image.open(io.BytesIO(encoded)) as image:
                        if image.format != "PNG" or image.size != dimensions:
                            raise ValueError(name + " original camera PNG dimensions differ")
                        image.verify()
    measured = measure_signal(packet, attempt) if suffix == "active_signal_exception" else measure_yield(packet)
    if suffix == "nearest_view_clear" and measured["through_occupied_during_crossing"]:
        raise ValueError("clear exact case has occupied through crossing")
    if suffix in ("nearest_view_hold", "nearest_view_continue") and not measured["through_occupied_during_crossing"]:
        raise ValueError("occupied exact case lacks through crossing")
    source_hashes = {"nearest-view-original.json": packet_hash,
                     "camera-frame-map.json": camera_hash,
                     "camera-sources.json": camera_receipt_hash}
    output_values = {
        "nearest_view_location_observation": {"view_frame": measured.get("first_view_frame"),
             "entry_frame": measured.get("first_entry_frame"),
             "site_source_hashes": packet.get("site_source_hashes", {})},
        "yield_approach_observation": {"minimum_approach_speed_mps": measured.get("minimum_approach_speed_mps"),
             "first_entry_frame": measured.get("first_entry_frame")},
        "through_traffic_crossing_observation": {"through_center_at_view_m": measured.get("through_center_at_view_m"),
             "occupied_during_crossing": measured.get("through_occupied_during_crossing"),
             "crossing_frame_count": measured.get("crossing_frame_count")},
        "signal_exception_observation": {"signal_governs_ego_approach": measured.get("signal_governs_ego_approach"),
             "observed_signal_states": measured.get("observed_signal_states")},
    }
    used = (["signal_exception_observation"] if suffix == "active_signal_exception" else
            ["nearest_view_location_observation", "yield_approach_observation",
             "through_traffic_crossing_observation"])
    return {"format": "worker-analysis-report", "case_id": case_id,
            "measurements": {key: {"value": output_values[key], "method": "report",
                                   "sources": source_hashes} for key in used},
            "source_complete": True, "physical_acceptance": False,
            "legal_verdict_claimed": False,
            "limitations": ["Actual pixels and physical site require independent review.",
                            "Immediate hazard and right of way remain unresolved judgments."]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    value = report(args.attempt)
    if args.output.exists():
        raise ValueError("saved analysis output already exists")
    result_path = args.attempt / "result.json"
    if result_path.exists():
        raise ValueError("saved Native result already exists")
    from saved_package import finalize
    native = finalize(args.attempt, value)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2) + "\n")
    result_path.write_text(json.dumps(native, indent=2) + "\n")


if __name__ == "__main__":
    main()
