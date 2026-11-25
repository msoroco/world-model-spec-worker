"""Lazy original-frame sight capture for the LVMC 11.16.040 case plan.

The caller supplies a synchronized CARLA world/ego and real ray and route readers.
This module records sensor returns; it never infers sight from the requested case.
No CARLA import occurs until the operator wires those readers in a runtime runner.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from hashlib import sha256
from math import hypot, isfinite
from pathlib import Path
from typing import Any, Callable
from io import BytesIO

from sight_construction import CASES, FEET_100_M, validate_site
from sight_measurement import evaluate


class CaptureError(ValueError):
    pass


CAMERAS = {"overview": (1920, 1080), "approach": (1280, 720),
           "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def _encoded(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _sha(value: Any) -> str:
    return sha256(_encoded(value)).hexdigest()


def capture(
    case_key: str,
    site: dict,
    world: Any,
    ego: Any,
    route_reader: Callable[[int, Any, Any], tuple[float, bool]],
    ray_reader: Callable[[int, Any, Any, list[str]], dict],
    brake: Callable[[Any], None],
    output: Path,
    camera_reader: Callable[[int, Any], dict] | None = None,
    before_tick: Callable[[Any], None] | None = None,
) -> dict:
    """Record 900 real 20 Hz ticks and seal the exact sight and speed samples.

    route_reader returns signed metres to the sourced intersection boundary and
    whether the ego body is traversing. ray_reader returns every entering arm's
    intersection/traffic rays for each frame in the last 100 feet. The reader
    must bind each ray to original sensor provenance. Calling code is responsible
    for synchronized world settings, ego/occluder spawning and actor cleanup.
    """
    if case_key not in CASES:
        raise CaptureError("unknown exact case")
    case = CASES[case_key]
    validate_site(site, case)
    if output.exists():
        raise CaptureError("capture output already exists")
    arms = site["entering_arms"]
    frames = []
    camera_rows = []
    stage = None
    try:
        if camera_reader is not None:
            stage = Path(tempfile.mkdtemp(prefix="sight-cameras-", dir=output.parent))
        for i in range(900):
            if before_tick is not None:
                before_tick(ego)
            frame_id = world.tick()
            snapshot = world.get_snapshot()
            if type(frame_id) is not int or snapshot.frame != frame_id:
                raise CaptureError("tick and original snapshot identity differ")
            if frames and frame_id != frames[-1]["frame"] + 1:
                raise CaptureError("original frame gap")
            time_s = snapshot.timestamp.elapsed_seconds
            if not isinstance(time_s, (int, float)) or not isfinite(time_s):
                raise CaptureError("original timestamp missing")
            if frames and not 0.045 <= time_s - frames[-1]["time_s"] <= 0.055:
                raise CaptureError("not a synchronized 20 Hz original stream")
            v = ego.get_velocity()
            speed = hypot(hypot(v.x, v.y), v.z)
            if not isfinite(speed) or speed < 0:
                raise CaptureError("ego velocity readback invalid")
            distance, traversing = route_reader(frame_id, snapshot, ego)
            if not isinstance(distance, (int, float)) or not isfinite(distance):
                raise CaptureError("route distance readback invalid")
            if type(traversing) is not bool:
                raise CaptureError("intersection body occupancy readback invalid")
            rays = {}
            if 0 <= distance <= FEET_100_M:
                rays = ray_reader(frame_id, snapshot, ego, arms)
                if not isinstance(rays, dict) or set(rays) != set(arms):
                    raise CaptureError("all entering-arm ray readbacks required")
                for arm, ray in rays.items():
                    if not isinstance(ray, dict) or not ray.get("ray_frame_source_sha256"):
                        raise CaptureError(f"{arm} ray source binding missing")
            frames.append({"frame": frame_id, "time_s": time_s,
                           "approach_distance_m": distance, "ego_speed_mps": speed,
                           "traversing_intersection": traversing, "rays": rays})
            if camera_reader is not None:
                from PIL import Image
                images = camera_reader(frame_id, snapshot)
                if not isinstance(images, dict) or set(images) != set(CAMERAS):
                    raise CaptureError("four original camera sources required")
                row = {"frame": frame_id, "time_s": time_s, "sources": {}}
                for name, dimensions in CAMERAS.items():
                    item = images[name]
                    if not isinstance(item, tuple) or len(item) != 2 or item[0] != frame_id:
                        raise CaptureError(f"{name} camera frame identity differs")
                    raw = item[1]
                    if not isinstance(raw, bytes):
                        raise CaptureError(f"{name} original PNG bytes required")
                    try:
                        with Image.open(BytesIO(raw)) as image:
                            if image.format != "PNG" or image.size != dimensions:
                                raise CaptureError(f"{name} original camera profile differs")
                            image.load()
                    except (OSError, ValueError) as exc:
                        raise CaptureError(f"{name} camera PNG cannot be fully decoded") from exc
                    path = f"cameras/{name}/{frame_id:08d}.png"
                    target = stage / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(raw)
                    row["sources"][name] = {"path": path, "sha256": sha256(raw).hexdigest()}
                camera_rows.append(row)
        packet = {
            "case_id": f"testing__C111278__LVMC-11-16-040__motor_vehicle_driver__{case_key}",
            "map_hash": site["map_hash"], "site_source_sha256": _sha(site),
            "boundary_source_sha256": site["boundary_source_sha256"],
            "through_source_sha256": site["ego_road_through_source_sha256"],
            "control_source_sha256": site["traffic_controlled_intersection_source_sha256"],
            "entering_arms": arms, "frames": frames,
            "frame_source_sha256": _sha(frames),
            "ray_source_sha256": _sha([f["rays"] for f in frames]),
            "speed_source_sha256": _sha([f["ego_speed_mps"] for f in frames]),
            "through_designation": site["ego_road_through"],
            "traffic_controlled": site["traffic_controlled_intersection"],
        }
        measurement = evaluate(packet)
        output.mkdir(parents=True)
        if stage is not None:
            shutil.move(str(stage / "cameras"), str(output / "cameras"))
            stage.rmdir()
            stage = None
            camera_bytes = _encoded(camera_rows)
            (output / "native-camera-map.json").write_bytes(camera_bytes)
        source_bytes = _encoded(packet)
        (output / "native-sight.json").write_bytes(source_bytes)
        receipt = {
            "case_id": packet["case_id"], "capture_kind": "original_native",
            "recorded_only": True, "fps": 20, "duration_s": 45,
            "map_hash": site["map_hash"], "site_source_sha256": packet["site_source_sha256"],
            "source_path": "native-sight.json", "source_sha256": sha256(source_bytes).hexdigest(),
            "first_frame": frames[0]["frame"], "last_frame": frames[-1]["frame"],
            "frame_count": 900, "measurement": measurement,
            "camera_capture": ("original_four_camera_png" if camera_reader is not None
                               else "pending separate original four-camera acquisition"),
            "camera_map_path": "native-camera-map.json" if camera_reader is not None else None,
            "camera_map_sha256": sha256(camera_bytes).hexdigest() if camera_reader is not None else None,
            "legal_conclusion": None,
        }
        (output / "native-sight-receipt.json").write_bytes(_encoded(receipt))
        return receipt
    finally:
        if stage is not None:
            shutil.rmtree(stage)
        brake(ego)
