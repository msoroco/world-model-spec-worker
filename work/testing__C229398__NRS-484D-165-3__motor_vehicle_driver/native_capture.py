"""Original 20 Hz parked-lamp capture with explicit source and camera joins.

The Native caller owns the world and supplies four independently acquired camera
images for each world frame. Image bytes and source documents live in the attempt,
outside this returned worker package. No photometric or legal verdict is made.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from parked_lamps import ASSIGNMENT, CASES, FEET, FIXED_SITE_FIELDS, construct, require, validate_site

NAMES = ("front", "rear", "left", "right")
COUNT = 900
HZ = 20


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _write_new(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
    return {"path": path.name, "sha256": _sha(data)}


def read_site(path, case_key):
    """Reject a changed independent site document before contacting Native."""
    raw = Path(path).read_bytes()
    site = json.loads(raw)
    require(site.get("case_id") == ASSIGNMENT + "__" + case_key, "site case mismatch")
    source_path = Path(site.get("site_source_path", ""))
    require(source_path.is_file(), "independent site document missing")
    source_data = source_path.read_bytes()
    require(_sha(source_data) == site.get("site_source_sha256"), "independent site document changed")
    evidence = json.loads(source_data)
    for key in FIXED_SITE_FIELDS:
        require(evidence.get(key) == site.get(key), "fixed site evidence differs: " + key)
    for key in ("case_id", "time_qualifies", "highway_public_use_source", "shoulder_boundary_source", "traveled_boundary_source",
                "traffic_direction_source", "vehicle_class_source", "reference_time_source",
                "visibility_station_source", "lamp_installation_source", "lighting_assessment_source",
                "lighting_assessment"):
        require(evidence.get(key) == site.get(key), "site evidence differs: " + key)
    require(isinstance(site.get("installed_lamp_positions"), list) and site["installed_lamp_positions"],
            "lamp installation positions missing")
    require(site["installed_lamp_positions"] == evidence.get("installed_lamp_positions"),
            "lamp installation positions differ from source")
    require(site.get("camera_transforms") == evidence.get("camera_transforms") and
            isinstance(site.get("camera_transforms"), dict) and set(site["camera_transforms"]) == set(NAMES),
            "camera station transforms differ from source")
    validate_site(site, case_key, site["map_sha256"])
    return site, raw, source_data


def capture(world, site_path, case_key, output_dir, camera_reader, *, frames=COUNT):
    """Capture a whole original interval; camera_reader(native_frame) returns four images.

    Each image entry has source_sensor, frame, and nonempty bytes. The caller must
    acquire camera callbacks from four actual Native sensors. This function does
    not accept a command echo as a camera frame or write a success packet after a
    failed join. It always destroys its spawned vehicle.
    """
    require(case_key in CASES and frames == COUNT, "exact 900-frame case required")
    site, site_raw, source_raw = read_site(site_path, case_key)
    root = Path(output_dir)
    require(root.is_dir(), "capture output directory missing")
    require(not any(root.iterdir()), "capture output must be empty")
    built = construct(world, site, case_key, site["map_sha256"])
    vehicle = built["actor"]
    rows, camera_map = [], []
    camera_sensors = None
    first_time = None
    first_frame = None
    try:
        for tick in range(frames):
            native_frame = world.tick()
            snapshot = world.get_snapshot()
            require(type(native_frame) is int and snapshot.frame == native_frame, "Native frame/snapshot mismatch")
            if first_frame is None:
                first_frame = native_frame
                first_time = float(snapshot.timestamp.elapsed_seconds)
            require(native_frame == first_frame + tick, "Native frame gap")
            relative = float(snapshot.timestamp.elapsed_seconds) - first_time
            require(math.isfinite(relative) and abs(relative - tick / HZ) <= .003, "Native 20 Hz time join failed")
            require(vehicle.is_alive, "parked vehicle destroyed during capture")
            control = vehicle.get_control()
            require(control.hand_brake is True, "Native parking brake readback missing")
            velocity = vehicle.get_velocity()
            speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
            require(speed <= .25, "parked vehicle moving")
            position = vehicle.get_transform().location
            require(all(math.isfinite(value) for value in (position.x, position.y, position.z)),
                    "Native vehicle position invalid")
            lamp_bits = int(vehicle.get_light_state())
            require(lamp_bits == built["requested_lamp_mask"], "Native lamp readback changed")
            observed = camera_reader(native_frame)
            require(isinstance(observed, dict) and set(observed) == set(NAMES), "four camera images missing")
            sensors = {name: observed[name].get("source_sensor") for name in NAMES}
            require(all(isinstance(value, str) and value for value in sensors.values()) and
                    len(set(sensors.values())) == len(NAMES), "four distinct camera sensors required")
            if camera_sensors is None:
                camera_sensors = sensors
            require(sensors == camera_sensors, "original camera sensor identity changed")
            source_frames = {}
            for name in NAMES:
                image = observed[name]
                require(isinstance(image, dict) and type(image.get("frame")) is int and image["frame"] == native_frame,
                        name + " original camera frame mismatch")
                require(image.get("source_sensor") and isinstance(image.get("bytes"), bytes) and image["bytes"],
                        name + " original camera bytes missing")
                source_frames[name] = {"native_frame": native_frame, "sensor": image["source_sensor"],
                                       "sha256": _sha(image["bytes"])}
                _write_new(root / "cameras" / name / (f"{tick:04d}.png"), image["bytes"])
            camera_map.append({"frame_index": tick, "native_frame": native_frame, "sources": source_frames})
            # Visual judgments remain unknown until an independent original-pixel review.
            unknown_lamp = lambda name: {"station_m": FEET["lamps"], "source_camera": name,
                                         "color_assessment": "unknown", "visibility_assessment": "unknown"}
            rows.append({"frame_index": tick, "native_frame": native_frame, "time_s": tick / HZ,
                         "map_sha256": site["map_sha256"], "vehicle_alive": True,
                         "vehicle_role": "motor_vehicle_driver", "placement": CASES[case_key]["placement"],
                         "attendance": CASES[case_key]["attendance"],
                         "curb_boundary_visible": None,
                         "curb_boundary_source": site["shoulder_boundary_source"],
                         "traffic_side": site["traffic_side"],
                         "time_qualifies": site["time_qualifies"],
                         "lighting_assessment": site["lighting_assessment"],
                         "parking_brake": True, "speed_mps": speed,
                         "position_m": [position.x, position.y, position.z],
                         "front_lamp_state": CASES[case_key]["lamps"],
                         "rear_lamp_state": CASES[case_key]["lamps"],
                         "native_lamp_state_bits": lamp_bits,
                         "front_lamp_observation": unknown_lamp("front"),
                         "rear_lamp_observation": unknown_lamp("rear"),
                         "revelation_observation": {"station_m": FEET["revelation"],
                                                    "source_camera": "front", "assessment": "unknown"},
                         "installed_lamp_positions": site["installed_lamp_positions"]})
        history = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows).encode()
        mapping = (json.dumps({"frames": camera_map}, sort_keys=True) + "\n").encode()
        cameras = {}
        for name in NAMES:
            index = {"camera": name, "fps": HZ, "frames": [
                {"frame_index": item["frame_index"], "native_frame": item["native_frame"],
                 "path": f"cameras/{name}/{item['frame_index']:04d}.png",
                 "sha256": item["sources"][name]["sha256"]} for item in camera_map]}
            index_ref = _write_new(root / (name + "-camera-index.json"),
                                   (json.dumps(index, sort_keys=True) + "\n").encode())
            cameras[name] = {"path": index_ref["path"], "sha256": index_ref["sha256"],
                             "source_sensor": camera_map[0]["sources"][name]["sensor"],
                             "fps": HZ, "frames": frames, "source_format": "original_png_index"}
        history_ref = _write_new(root / "original_history.jsonl", history)
        map_ref = _write_new(root / "original_frame_map.json", mapping)
        site_ref = _write_new(root / "site_packet.json", site_raw)
        _write_new(root / "site_source.json", source_raw)
        packet = {"case_id": ASSIGNMENT + "__" + case_key, "source_type": "original_native_capture",
                  "map_sha256": site["map_sha256"], "site_source_sha256": _sha(source_raw),
                  "site_packet_sha256": site_ref["sha256"], "fps": HZ, "frame_count": frames,
                  "original_history_path": history_ref["path"], "original_history_sha256": history_ref["sha256"],
                  "original_frame_map_path": map_ref["path"], "original_frame_map_sha256": map_ref["sha256"],
                  "cameras": cameras, "camera_image_format": "original_png",
                  "camera_frames_per_view": frames,
                  "native_first_frame": first_frame, "native_last_frame": first_frame + frames - 1,
                  "physical_visibility_status": "unreviewed", "legal_verdict": None}
        _write_new(root / "capture-packet.json", (json.dumps(packet, indent=2, sort_keys=True) + "\n").encode())
        return packet
    finally:
        vehicle.destroy()
