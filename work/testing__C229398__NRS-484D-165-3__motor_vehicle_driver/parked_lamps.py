"""Source-gated parked-lamp construction and original-frame evidence checks.

No software threshold here decides whether a person is revealed or a lamp is
visible. The 1,000/500 foot distances are observation stations from the law.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT = "testing__C229398__NRS-484D-165-3__motor_vehicle_driver"
LAW = "NRS-484D-165-3"
FEET = {"revelation": 304.8, "lamps": 152.4}
FIXED_SITE_FIELDS = ("map_sha256", "map_name", "curb_waypoint_xyz", "road_id", "lane_id",
    "traffic_side", "highway_public_use_source", "shoulder_boundary_source",
    "traveled_boundary_source", "traffic_direction_source", "vehicle_class_source",
    "visibility_station_source", "lamp_installation_source",
    "shoulder_spawn_transform", "traveled_spawn_transform",
    "revelation_station_m", "front_lamp_station_m", "rear_lamp_station_m",
    "installed_lamp_positions", "camera_transforms")
CASES = {
    "dark_lamps_on": {"placement": "shoulder", "lighting": "insufficient", "lamps": "on", "attendance": "unattended"},
    "dark_lamps_off": {"placement": "shoulder", "lighting": "insufficient", "lamps": "off", "attendance": "unattended"},
    "dark_attended": {"placement": "shoulder", "lighting": "insufficient", "lamps": "on", "attendance": "attended"},
    "dark_traveled": {"placement": "traveled", "lighting": "insufficient", "lamps": "on", "attendance": "unattended"},
    "sufficient_light": {"placement": "shoulder", "lighting": "sufficient", "lamps": "off", "attendance": "unattended"},
    "outside_referenced_time": {"placement": "shoulder", "lighting": "sufficient", "lamps": "off", "attendance": "unattended"},
}


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fixed_site_signature(site):
    """Bind the controlled layout, traffic side, equipment and camera stations."""
    return hashlib.sha256(json.dumps({key: site.get(key) for key in FIXED_SITE_FIELDS},
                                     sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_site(site, case_key, expected_map_sha256):
    require(case_key in CASES, "unknown exact case")
    require(site.get("law_id") == LAW and site.get("cell_id") == "C229398", "site identity mismatch")
    require(len(expected_map_sha256) == 64 and site.get("map_sha256") == expected_map_sha256, "map seal mismatch")
    require(isinstance(site.get("site_source_sha256"), str) and len(site["site_source_sha256"]) == 64, "site source seal missing")
    for source in ("highway_public_use_source", "shoulder_boundary_source", "traveled_boundary_source",
                   "traffic_direction_source", "vehicle_class_source", "reference_time_source",
                   "visibility_station_source", "lamp_installation_source"):
        require(site.get(source), f"missing {source}")
    require(site.get("map_name") and site.get("curb_waypoint_xyz"), "curb site missing")
    xyz = site["curb_waypoint_xyz"]
    require(len(xyz) == 3 and all(isinstance(v, (int, float)) and math.isfinite(v) for v in xyz), "invalid curb position")
    require(site.get("traffic_side") in ("left", "right"), "traffic side missing")
    require(site.get("revelation_station_m") == FEET["revelation"], "1,000-foot station missing")
    require(site.get("front_lamp_station_m") == FEET["lamps"] and site.get("rear_lamp_station_m") == FEET["lamps"], "500-foot stations missing")
    require(site.get("time_qualifies") is (case_key != "outside_referenced_time"), "reference-time case mismatch")
    require(site.get("lighting_assessment") == CASES[case_key]["lighting"] and site.get("lighting_assessment_source"),
            "case lighting assessment source missing")
    return CASES[case_key]


def construct(world, site, case_key, expected_map_sha256, blueprint_id="vehicle.tesla.model3"):
    """Spawn a curbside vehicle, verify the Native map and read back lamp state.

    The caller retains actor/world ownership and runs capture/cleanup. A local
    source packet must resolve the referenced-time status before this call.
    """
    spec = validate_site(site, case_key, expected_map_sha256)
    require(world.get_map().name == site["map_name"], "Native map mismatch")
    import carla  # Native-only import
    waypoint = world.get_map().get_waypoint(carla.Location(*site["curb_waypoint_xyz"]), project_to_road=False)
    require(waypoint is not None and waypoint.road_id == site["road_id"] and waypoint.lane_id == site["lane_id"], "curb waypoint mismatch")
    spawn = site["shoulder_spawn_transform"] if spec["placement"] == "shoulder" else site["traveled_spawn_transform"]
    require(spawn.get("source") and len(spawn.get("xyz", [])) == 3 and len(spawn.get("rpy", [])) == 3, "placement transform source missing")
    transform = carla.Transform(carla.Location(*spawn["xyz"]), carla.Rotation(*spawn["rpy"]))
    blueprint = world.get_blueprint_library().find(blueprint_id)
    require(blueprint is not None, "vehicle blueprint unavailable")
    actor = world.try_spawn_actor(blueprint, transform)
    require(actor is not None, "vehicle spawn failed")
    actor.apply_control(carla.VehicleControl(hand_brake=True, brake=1.0))
    requested = carla.VehicleLightState.Position | carla.VehicleLightState.LowBeam if spec["lamps"] == "on" else carla.VehicleLightState.NONE
    actor.set_light_state(carla.VehicleLightState(requested))
    require(int(actor.get_light_state()) == int(requested), "Native lamp readback mismatch")
    return {"actor": actor, "case_id": f"{ASSIGNMENT}__{case_key}", "requested_lamp_mask": int(requested),
            "placement": spec["placement"], "attendance": spec["attendance"]}


def measure(site, case_key, expected_map_sha256, frames):
    """Seal 900 original 20 Hz samples; record observations without legal labels."""
    spec = validate_site(site, case_key, expected_map_sha256)
    require(len(frames) == 900, "900 original frames required")
    samples = []
    for index, frame in enumerate(frames):
        require(frame.get("frame_index") == index and abs(frame.get("time_s", -1) - index / 20) <= 0.002, "original 20 Hz join failed")
        require(frame.get("map_sha256") == expected_map_sha256 and frame.get("vehicle_alive") is True, "Native source or actor missing")
        require(frame.get("vehicle_role") == "motor_vehicle_driver", "actor role mismatch")
        require(frame.get("placement") == spec["placement"] and frame.get("attendance") == spec["attendance"], "fixed scene mismatch")
        require(frame.get("curb_boundary_source") == site["shoulder_boundary_source"] and frame.get("traffic_side") == site["traffic_side"], "curb or traffic-side source missing")
        require(frame.get("curb_boundary_visible") in (True, False, None), "curb visibility assessment invalid")
        require(frame.get("time_qualifies") is site["time_qualifies"], "referenced-time source mismatch")
        require(frame.get("lighting_assessment") == spec["lighting"], "lighting source mismatch")
        require(frame.get("parking_brake") is True and frame.get("speed_mps") is not None and 0 <= frame["speed_mps"] <= 0.25, "parked interval missing")
        require(frame.get("front_lamp_state") == spec["lamps"] and frame.get("rear_lamp_state") == spec["lamps"], "lamp state mismatch")
        for name in ("front", "rear"):
            lamp = frame.get(f"{name}_lamp_observation")
            require(isinstance(lamp, dict) and lamp.get("station_m") == FEET["lamps"] and lamp.get("source_camera") and lamp.get("color_assessment") in ("white", "amber", "red", "other", "unknown") and lamp.get("visibility_assessment") in ("visible", "not_visible", "unknown"), f"{name} lamp observation missing")
        revelation = frame.get("revelation_observation")
        require(isinstance(revelation, dict) and revelation.get("station_m") == FEET["revelation"] and revelation.get("source_camera") and revelation.get("assessment") in ("revealed", "not_revealed", "unknown"), "1,000-foot revelation source missing")
        lamps = frame.get("installed_lamp_positions")
        require(isinstance(lamps, list) and lamps and all(v.get("source") and v.get("side") in ("left", "right") for v in lamps), "lamp installation positions missing")
        if index % 20 == 0:
            samples.append({"frame_index": index, "time_s": frame["time_s"],
                            "revelation": revelation, "front": frame["front_lamp_observation"],
                            "rear": frame["rear_lamp_observation"]})
    return {"case_id": f"{ASSIGNMENT}__{case_key}", "map_sha256": expected_map_sha256,
            "site_source_sha256": site["site_source_sha256"],
            "fixed_site_signature": fixed_site_signature(site), "spec": spec,
            "time_qualifies": site["time_qualifies"], "original_frame_count": len(frames),
            "one_hz_original_samples": samples, "legal_status": "unresolved_photometric_and_referenced_time_review"}


def audit_comparison(reports, case_keys, changed_fields):
    require(len(reports) == len(case_keys) and len(reports) >= 2, "comparison member missing")
    require(all(k in CASES for k in case_keys), "unknown comparison case")
    expected = reports[0]
    for report, key in zip(reports, case_keys):
        require(report.get("case_id") == f"{ASSIGNMENT}__{key}", "comparison case mismatch")
        require(report.get("original_frame_count") == 900 and len(report.get("one_hz_original_samples", [])) == 45, "comparison evidence missing")
        require(report.get("map_sha256") == expected.get("map_sha256") and
                report.get("fixed_site_signature") == expected.get("fixed_site_signature"),
                "comparison fixed site changed")
        require(report.get("spec") == CASES[key], "comparison spec mismatch")
    require(set(changed_fields) <= set(CASES[case_keys[0]]) | {"time_qualifies"}, "unknown comparison variable")
    if not set(changed_fields) & {"lighting", "time_qualifies"}:
        require(all(report.get("site_source_sha256") == expected.get("site_source_sha256") for report in reports),
                "comparison site source changed without lighting/time difference")
    for field in set(CASES[case_keys[0]]) | {"time_qualifies"}:
        values = [r["time_qualifies"] for r in reports] if field == "time_qualifies" else [CASES[k][field] for k in case_keys]
        if field in changed_fields:
            require(len(set(values)) > 1, f"declared difference {field} absent")
        else:
            require(len(set(values)) == 1, f"undeclared difference {field}")
    return {"case_ids": [r["case_id"] for r in reports], "changed_fields": sorted(changed_fields),
            "legal_status": "unresolved"}


def audit_saved_capture(capture_dir, case_key, expected_map_sha256):
    """Independently join a sealed saved packet to its four camera receipts.

    This checks packet identity and source completeness. The pinned media
    decoder must separately decode actual videos before delivery readiness.
    """
    require(case_key in CASES, "unknown exact case")
    capture_dir = Path(capture_dir)
    packet_path = capture_dir / "capture-packet.json"
    require(packet_path.is_file(), "saved capture packet missing")
    packet = json.loads(packet_path.read_text())
    require(packet.get("case_id") == f"{ASSIGNMENT}__{case_key}", "saved case mismatch")
    require(packet.get("map_sha256") == expected_map_sha256, "saved map seal mismatch")
    require(packet.get("source_type") == "original_native_capture", "saved source type mismatch")
    require(packet.get("fps") == 20 and packet.get("frame_count") == 900, "saved 20 Hz duration mismatch")
    require(packet.get("site_source_sha256") and len(packet["site_source_sha256"]) == 64, "saved site source missing")
    cameras = packet.get("cameras")
    require(isinstance(cameras, dict) and set(cameras) == {"front", "rear", "left", "right"}, "four-camera set missing")
    camera_indices = {}
    for name, camera in cameras.items():
        require(camera.get("source_sensor") and camera.get("fps") == 20 and camera.get("frames") == 900, f"{name} camera receipt invalid")
        path = capture_dir / camera.get("path", "")
        require(path.is_file() and path.resolve().is_relative_to(capture_dir.resolve()), f"{name} camera source absent")
        require(camera.get("sha256") == digest(path), f"{name} camera seal mismatch")
        if camera.get("source_format") == "original_png_index":
            index = json.loads(path.read_text())
            camera_indices[name] = index
            require(index.get("camera") == name and index.get("fps") == 20 and len(index.get("frames", [])) == 900,
                    f"{name} original image index invalid")
            for tick, entry in enumerate(index["frames"]):
                require(entry.get("frame_index") == tick and type(entry.get("native_frame")) is int,
                        f"{name} original image frame gap")
                image_path = capture_dir / entry.get("path", "")
                require(image_path.is_file() and image_path.resolve().is_relative_to(capture_dir.resolve()),
                        f"{name} original image missing")
                require(entry.get("sha256") == digest(image_path), f"{name} original image changed")
    require(packet.get("original_frame_map_path") and packet.get("original_frame_map_sha256"), "original frame map absent")
    mapping = capture_dir / packet["original_frame_map_path"]
    require(mapping.is_file() and digest(mapping) == packet["original_frame_map_sha256"], "original frame map seal mismatch")
    require(mapping.resolve().is_relative_to(capture_dir.resolve()), "original frame map escaped capture")
    if packet.get("camera_image_format") == "original_png":
        frame_map = json.loads(mapping.read_text()).get("frames", [])
        require(len(frame_map) == 900, "original frame map count mismatch")
        first = frame_map[0].get("native_frame")
        for tick, entry in enumerate(frame_map):
            require(entry.get("frame_index") == tick and entry.get("native_frame") == first + tick,
                    "original Native camera frame gap")
            require(set(entry.get("sources", {})) == set(cameras), "original camera source set mismatch")
            for name in cameras:
                require(entry["sources"][name].get("native_frame") == first + tick,
                        name + " original camera frame mismatch")
                require(entry["sources"][name].get("sensor") == cameras[name]["source_sensor"],
                        name + " original camera sensor identity mismatch")
                require(entry["sources"][name].get("sha256") ==
                        camera_indices[name]["frames"][tick]["sha256"],
                        name + " original camera image hash join mismatch")
    return {"case_id": packet["case_id"], "capture_packet_sha256": digest(packet_path),
            "source_type": packet["source_type"], "camera_names": sorted(cameras),
            "physical_visibility_status": "unreviewed"}
