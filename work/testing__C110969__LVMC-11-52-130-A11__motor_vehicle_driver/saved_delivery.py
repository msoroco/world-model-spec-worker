"""Independent source-integrity audit for one original C110969 attempt.

This is a CPU audit of saved evidence bindings. It never asserts video pixels,
legal necessity, or physical completion from a diagnostic fixture.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
from PIL import Image, UnidentifiedImageError

from measure_gap import measure


PREFIX = "testing__C110969__LVMC-11-52-130-A11__motor_vehicle_driver__"
SUFFIXES = {"stop_14ft", "stop_15ft", "stop_16ft", "stand_14ft",
            "traffic_14ft", "police_14ft", "device_14ft"}
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
PROFILE_DIMENSIONS = {"overview": (1920, 1080), "approach": (1280, 720),
                      "reference_corner": (1280, 720),
                      "driver_reference": (1280, 720)}
METERS_PER_FOOT = 0.3048


def _source(root, binding):
    relative = Path(binding["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Source path escapes attempt")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Required source missing or outside attempt")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != binding["sha256"]:
        raise ValueError("Required source hash mismatch")
    return path


def _rows(path):
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _frame_ids(rows, name, world_frames):
    if len(rows) != 900 or [row.get("frame") for row in rows] != list(range(900)):
        raise ValueError(name + " needs exact 900 frame indices")
    if [row.get("world_frame") for row in rows] != world_frames:
        raise ValueError(name + " world frame join mismatch")


def audit(attempt_path, *, allow_diagnostic=False):
    attempt_path = Path(attempt_path)
    packet = json.loads(attempt_path.read_text(encoding="utf-8"))
    case_id = packet.get("case_id")
    if not isinstance(case_id, str) or not case_id.startswith(PREFIX) or \
            case_id.removeprefix(PREFIX) not in SUFFIXES:
        raise ValueError("Wrong exact case")
    if not packet.get("attempt_id") or not packet.get("recording_id"):
        raise ValueError("Attempt or recording identity missing")
    if packet.get("acquisition_kind") != "original_native" and not allow_diagnostic:
        raise ValueError("Diagnostic source cannot satisfy delivery audit")
    root = attempt_path.parent
    provenance_root = root if (root / "fixture-provenance.json").is_file() else root.parent
    diagnostic_text_only = (packet.get("acquisition_kind") == "diagnostic_fixture" and
                            (provenance_root / "fixture-provenance.json").is_file())
    if diagnostic_text_only:
        marker = json.loads((provenance_root / "fixture-provenance.json").read_text())
        provenance = json.loads((provenance_root / "acquisition-provenance.json").read_text())
        if (not allow_diagnostic or marker.get("diagnostic_fixture") is not True or
                "CPU diagnostic only" not in marker.get("scope", "") or
                provenance.get("diagnostic_fixture") is not True or
                provenance.get("provenance_kind") != "synthetic_fixture"):
            raise ValueError("Synthetic text-only diagnostic provenance required")
    measurement_path = _source(root, packet["measurement_packet"])
    measurement_packet = json.loads(measurement_path.read_text(encoding="utf-8"))
    pose_path = _source(measurement_path.parent, measurement_packet["pose_source"])
    map_path = _source(measurement_path.parent, measurement_packet["map_source"])
    source_map_path = _source(root, packet["map_packet"])
    map_geometry = json.loads(map_path.read_text(encoding="utf-8"))
    source_map = json.loads(source_map_path.read_text(encoding="utf-8"))
    if map_geometry.get("map_source_sha256") != packet["map_packet"]["sha256"] or \
            map_geometry.get("opendrive_sha256") != source_map.get("opendrive_sha256") or \
            map_geometry.get("map_id") != source_map.get("map_name") or \
            case_id not in source_map.get("case_ids", []):
        raise ValueError("Map source and measurement geometry binding mismatch")
    measurement = measure(measurement_path)
    pose_rows = _rows(pose_path)
    world_frames = [row.get("world_frame") for row in pose_rows]
    if any(not isinstance(value, int) for value in world_frames) or \
            world_frames != list(range(world_frames[0], world_frames[0] + 900)):
        raise ValueError("Original Native world frames are not contiguous")
    frame_map_path = _source(root, packet["frame_map"])
    frame_rows = _rows(frame_map_path)
    _frame_ids(frame_rows, "Frame map", world_frames)
    if any(abs(row.get("time_s", -1) - row["frame"] / 20) > 1e-6
           for row in frame_rows):
        raise ValueError("Frame map timing mismatch")
    context_path = _source(root, packet["context"])
    context_rows = _rows(context_path)
    _frame_ids(context_rows, "Original context", world_frames)
    if any(not isinstance(row.get("participants"), list) or
           not isinstance(row.get("directions"), dict) for row in context_rows):
        raise ValueError("Original context observation fields missing")
    camera_bindings = packet.get("cameras", {})
    if set(camera_bindings) != set(CAMERAS):
        raise ValueError("Four named camera sources required")
    camera_hashes = {}
    decoded_images = 0
    for name in CAMERAS:
        path = _source(root, camera_bindings[name])
        rows = _rows(path)
        _frame_ids(rows, name, world_frames)
        seen_paths = set()
        for row in rows:
            if row.get("camera") != name or not row.get("original_frame_sha256") or \
                    not row.get("original_frame_path"):
                raise ValueError(name + " original camera frame receipt missing")
            relative_frame = Path(row["original_frame_path"])
            if relative_frame.is_absolute() or ".." in relative_frame.parts or \
                    relative_frame.suffix != ".png" or \
                    len(row["original_frame_sha256"]) != 64:
                raise ValueError(name + " original camera frame receipt malformed")
            frame_path = (root / relative_frame).resolve()
            if not frame_path.is_relative_to(root.resolve()) or frame_path in seen_paths:
                raise ValueError(name + " reuses an original camera frame path")
            seen_paths.add(frame_path)
            if diagnostic_text_only:
                if frame_path.exists():
                    raise ValueError("Text-only diagnostic unexpectedly supplies camera pixels")
                continue
            frame_path = _source(root, {"path": row["original_frame_path"],
                                        "sha256": row["original_frame_sha256"]})
            try:
                with Image.open(frame_path) as image:
                    if image.format != "PNG" or image.mode not in ("RGB", "RGBA"):
                        raise ValueError(name + " original camera frame is not RGB PNG")
                    if packet.get("acquisition_kind") == "original_native" and \
                            image.size != PROFILE_DIMENSIONS[name]:
                        raise ValueError(name + " original camera resolution mismatch")
                    image.load()
            except (UnidentifiedImageError, OSError) as exc:
                raise ValueError(name + " original camera frame cannot be decoded") from exc
            decoded_images += 1
        camera_hashes[name] = camera_bindings[name]["sha256"]
    suffix = case_id.removeprefix(PREFIX)
    expected_gap_ft = int(suffix.split("_")[1].removesuffix("ft")) if suffix in SUFFIXES else None
    if packet.get("requested_front_body_gap_ft") != expected_gap_ft:
        raise ValueError("Exact case requested gap mismatch")
    return {
        "format": "worker-saved-source-audit",
        "case_id": case_id,
        "attempt_id": packet["attempt_id"],
        "recording_id": packet["recording_id"],
        "native_source": packet.get("acquisition_kind") == "original_native",
        "time_join": True,
        "four_camera_receipts": True,
        "original_frame_count": 900,
        "decoded_original_images": decoded_images,
        "measurement": measurement,
        "frame_map_sha256": packet["frame_map"]["sha256"],
        "context_sha256": packet["context"]["sha256"],
        "camera_receipt_sha256": camera_hashes,
        "full_video_decode": False,
        "original_pixels_decoded": not diagnostic_text_only,
        "actual_pixels": False,
        "all_participants": False,
        "physical_completion": False,
        "legal_necessity": "unresolved",
    }


def process_saved(attempt_path, output_path, *, allow_diagnostic=False):
    """Write one source-bound measurement receipt after full saved audit passes."""
    output_path = Path(output_path)
    if output_path.exists():
        raise ValueError("Saved process receipt already exists")
    source_audit = audit(attempt_path, allow_diagnostic=allow_diagnostic)
    packet_bytes = Path(attempt_path).read_bytes()
    packet = json.loads(packet_bytes)
    requested_ft = packet["requested_front_body_gap_ft"]
    minimum_m = source_audit["measurement"]["minimum_halt_body_gap_m"]
    maximum_m = source_audit["measurement"]["maximum_halt_body_gap_m"]
    if not all(math.isfinite(value) and value >= 0 for value in (minimum_m, maximum_m)):
        raise ValueError("Observed halt gap is invalid")
    target_m = requested_ft * METERS_PER_FOOT
    # A half-foot band is a construction tolerance, never a legal threshold.
    target_observed = (abs(minimum_m - target_m) <= 0.5 * METERS_PER_FOOT and
                       abs(maximum_m - target_m) <= 0.5 * METERS_PER_FOOT)
    result = {
        "format": "c110969-saved-process-v1",
        "case_id": source_audit["case_id"],
        "attempt_id": source_audit["attempt_id"],
        "recording_id": source_audit["recording_id"],
        "attempt_packet_sha256": hashlib.sha256(packet_bytes).hexdigest(),
        "source_audit": source_audit,
        "requested_front_body_gap_ft": requested_ft,
        "observed_halt_gap_m": {"minimum": minimum_m, "maximum": maximum_m},
        "observed_halt_intervals": source_audit["measurement"]["halt_intervals"],
        "construction_target_observed": target_observed,
        "legal_necessity": "unresolved",
        "physical_completion": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("attempt", type=Path)
    parser.add_argument("--allow-diagnostic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, allow_diagnostic=args.allow_diagnostic), sort_keys=True))
