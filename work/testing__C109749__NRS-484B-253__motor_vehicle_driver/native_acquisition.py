"""Prospective 20 Hz Native acquisition for the exact left-turn case.

An adapter supplies real tick, actor and sensor callbacks. This module never
connects to CARLA on import. It preserves raw observed snapshots and sensor
bytes; it does not infer legal yielding or physical acceptance.
"""

import hashlib
import io
import json
from pathlib import Path

from PIL import Image

from left_turn_measurements import body_occupancy, opposing_approach
from native_intersection import validate
from saved_left_turn import ASSIGNMENT_ID

CAMERAS = ("front", "rear", "left", "right")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def _source_packet(adapter, packet):
    """Require an explicit adapter attestation for a non-diagnostic receipt."""
    attestation = adapter.source_attestation()
    if not isinstance(attestation, dict):
        raise ValueError("Native source attestation missing")
    if not attestation.get("source_id") or attestation.get("native_map_sha256") != packet["map_sha256"]:
        raise ValueError("Native source/map attestation mismatch")
    return attestation


def capture(*, adapter, case_id, map_path, output, frame_count=900, start_frame=None):
    """Seal exact original actor snapshots and four image callbacks per tick.

    Adapter contract: source_attestation() -> source_id/native_map_sha256/
    native_origin; tick() -> (frame, time_s, actor_sample, camera_png_bytes).
    Adapter must have already spawned both vehicles and four synchronized
    cameras. The caller owns world restore, actor cleanup and braking.
    """
    if not case_id.startswith(ASSIGNMENT_ID + "__"):
        raise ValueError("exact assignment case ID required")
    if not isinstance(frame_count, int) or frame_count < 2:
        raise ValueError("positive Native frame count required")
    packet = json.loads(Path(map_path).read_text(encoding="utf-8"))
    validate(packet)
    attestation = _source_packet(adapter, packet)
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Native attempt output must be empty")
    output.mkdir(parents=True, exist_ok=True)
    frames_dir = output / "original-frames"
    frames_dir.mkdir()
    rows, frame_map = [], []
    for index in range(frame_count):
        frame, timestamp, sample, cameras = adapter.tick()
        if not isinstance(frame, int) or (index and frame != rows[-1]["frame"] + 1):
            raise ValueError("Native actor tick dropped or duplicated frame")
        if index == 0 and start_frame is not None and frame != start_frame:
            raise ValueError("Native start frame mismatch")
        if index and abs(timestamp - rows[-1]["time_s"] - 0.05) > 0.002:
            raise ValueError("Native actor tick is not 20 Hz")
        if not isinstance(sample, dict) or not isinstance(cameras, dict) or set(cameras) != set(CAMERAS):
            raise ValueError("original actor snapshot and four cameras required")
        row = {"frame": frame, "time_s": timestamp, **sample}
        # Reject missing source fields before sealing; no controller requests
        # may be substituted for measured controls or actor bodies.
        required = ("ego_vertices", "opponent_vertices", "ego_heading",
                    "opponent_heading", "ego_speed_mps", "opponent_speed_mps",
                    "ego_signal_left", "ego_turn_committed", "opponent_cleared",
                    "ego_braking")
        if any(key not in row for key in required):
            raise ValueError("Native actor snapshot missing measured field")
        body_occupancy(row["ego_vertices"], packet["intersection_polygon"])
        body_occupancy(row["opponent_vertices"], packet["intersection_polygon"])
        opposing_approach(row["ego_heading"], row["opponent_heading"])
        image_refs = {}
        for name in CAMERAS:
            pixels = cameras[name]
            if not isinstance(pixels, bytes):
                raise ValueError("camera callback must return original PNG bytes")
            try:
                with Image.open(io.BytesIO(pixels)) as image:
                    image.verify()
                with Image.open(io.BytesIO(pixels)) as image:
                    if image.format != "PNG" or min(image.size) <= 0:
                        raise ValueError("camera callback is not a valid PNG")
            except Exception as exc:
                raise ValueError("camera callback is not a valid PNG") from exc
            target = frames_dir / f"{frame:09d}-{name}.png"
            target.write_bytes(pixels)
            image_refs[name] = {"path": str(target.relative_to(output)), "sha256": _sha(target)}
        frame_map.append({"frame": frame, "time_s": timestamp, "cameras": image_refs})
        rows.append(row)
    trace_path = output / "original-trace.jsonl"
    trace_path.write_text("".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in rows), encoding="utf-8")
    frame_map_path = output / "original-frame-map.json"
    _write_json(frame_map_path, {"case_id": case_id, "frames": frame_map})
    map_copy = output / "original-map.json"
    map_copy.write_bytes(Path(map_path).read_bytes())
    diagnostic = not (attestation.get("native_origin") is True and
                      packet.get("reviewed_original_map") is True)
    receipt = {"assignment_id": ASSIGNMENT_ID, "case_id": case_id,
               "source_id": attestation["source_id"], "native_map_sha256": packet["map_sha256"],
               "map_sha256": _sha(map_copy), "trace_sha256": _sha(trace_path),
               "frame_map_sha256": _sha(frame_map_path), "frame_count": frame_count,
               "camera_names": list(CAMERAS), "simulator_frame_rate_hz": 20,
               "diagnostic_fixture": diagnostic, "physical_acceptance": "unverified"}
    receipt_path = output / "acquisition-receipt.json"
    _write_json(receipt_path, receipt)
    return {"map_path": map_copy, "trace_path": trace_path,
            "frame_map_path": frame_map_path, "receipt_path": receipt_path}
