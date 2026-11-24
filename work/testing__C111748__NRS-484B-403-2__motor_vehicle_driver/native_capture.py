"""Acquire original 20 Hz device and ego history without importing CARLA.

The local runner supplies live callbacks after constructing the reviewed site.
This records readbacks; it does not decide that the sign is legally official or
that the sign is legible in the final camera pixels.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import tempfile


ROOT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("device_site_for_capture", ROOT / "construct.py")
_site = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_site)
_spec = importlib.util.spec_from_file_location("device_measurement_for_capture", ROOT / "native_device.py")
_measure = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_measure)

CAMERAS = ("overview", "detail_left", "detail_center", "detail_right")
FPS = 20
DELIVERY_FRAMES = 900


class CaptureError(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise CaptureError(reason)


def capture(site_path: Path, site_sha256: str, case_id: str, output: Path,
            *, tick, apply_control, sample, brake, frames: int = DELIVERY_FRAMES,
            diagnostic: bool = False) -> dict:
    """Record a case through injected live callbacks and seal original readbacks.

    tick() returns (original_frame, original_seconds). apply_control(i, site)
    requests behavior for the next tick. sample(frame) returns ego, device and
    camera readbacks, each obtained from that same original frame. brake() must
    apply a safe stop even when a readback or source check fails.
    """
    site = _site.load_site(site_path, site_sha256, case_id)
    require(site["device"].get("device_id") is not None, "reviewed device identity missing")
    require(site.get("camera_plan_sha256"), "camera plan source missing")
    require(frames == DELIVERY_FRAMES or diagnostic, "short capture requires diagnostic flag")
    require(isinstance(frames, int) and frames >= 3, "invalid frame count")
    require(callable(tick) and callable(apply_control) and callable(sample) and callable(brake), "live callbacks missing")
    route_raw = json.dumps(site["u_turn_route"], sort_keys=True, separators=(",", ":")).encode()
    packet = {
        "case_id": case_id, "actor": "motor_vehicle_driver", "site_sha256": site_sha256,
        "map_sha256": site["map_sha256"],
        "route_sha256": hashlib.sha256(route_raw).hexdigest(),
        "highway_status": site["highway_status"],
        "device": dict(site["device"]), "ego_id": site["ego_id"],
        "camera_plan_sha256": site["camera_plan_sha256"],
        "duration_s": frames / FPS, "diagnostic": bool(diagnostic), "frames": [],
    }
    first_frame = None
    first_time = None
    try:
        for i in range(frames):
            apply_control(i, site)
            original_frame, original_seconds = tick()
            require(isinstance(original_frame, int) and not isinstance(original_frame, bool), "original frame identity missing")
            require(isinstance(original_seconds, (int, float)) and math.isfinite(original_seconds), "original time missing")
            if first_frame is None:
                first_frame, first_time = original_frame, original_seconds
            require(original_frame == first_frame + i, "original frame gap")
            require(abs((original_seconds - first_time) - i / FPS) <= 0.002, "20 Hz original time drift")
            readback = sample(original_frame)
            require(isinstance(readback, dict), "live sample missing")
            ego, device, cameras = (readback.get(k) for k in ("ego", "device_readback", "cameras"))
            require(isinstance(ego, dict) and ego.get("id") == site["ego_id"], "ego live identity mismatch")
            require(isinstance(device, dict) and device.get("device_id") == site["device"]["device_id"], "device live identity mismatch")
            require(device.get("prohibits_u_turn") == site["device"]["prohibits_u_turn"], "live display differs from reviewed setup")
            require(isinstance(cameras, dict) and set(cameras) == set(CAMERAS), "four camera readbacks missing")
            require(all(cameras[name] == original_frame for name in CAMERAS), "camera original frame mismatch")
            packet["frames"].append({"frame": original_frame, "time_s": original_seconds,
                                     "ego": ego, "device_readback": device, "cameras": cameras})
        output.parent.mkdir(parents=True, exist_ok=True)
        raw = (json.dumps(packet, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        sha256 = hashlib.sha256(raw).hexdigest()
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".native-device-", delete=False) as tmp:
            temp_path = Path(tmp.name)
            tmp.write(raw)
        try:
            measurement = _measure.analyze(temp_path, case_id=case_id, sha256=sha256)
            os.replace(temp_path, output)
        finally:
            temp_path.unlink(missing_ok=True)
        return {"native_path": str(output), "native_sha256": sha256,
                "frame_count": frames, "diagnostic": bool(diagnostic),
                "measurement": measurement, "physical_completion": False,
                "actual_pixels": False}
    finally:
        brake()
