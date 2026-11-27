"""Source-shaped bus stationary-event measurement for LVMC 11.60.030(A)(1).

Stop duration, brake and driver-presence observations are retained separately.
This module does not equate a stationary interval with statutory standing or
parking and does not decide whether a place was legally designated.
"""
from math import isfinite
import hashlib
import json
from pathlib import Path
import re

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
ZONE_KINDS = ("bus_stop", "bus_stand", "route_origin", "route_destination",
              "passenger_loading_zone", "other_street")


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError("missing or nonfinite " + name)
    return float(value)


def measure(frames, context, *, source_kind):
    if source_kind not in ("original_native", "synthetic_native_sample"):
        raise ValueError("undeclared source kind")
    if len(frames) < 600:
        raise ValueError("capture shorter than 30 seconds at 20 Hz")
    if context.get("vehicle_class") not in ("route_bus_non_tour", "tour_bus"):
        raise ValueError("source-declared bus identity missing")
    if not context.get("route_id") or not context.get("street_id"):
        raise ValueError("assigned route or street identity missing")
    zone = context.get("zone")
    if not isinstance(zone, dict) or zone.get("kind") not in ZONE_KINDS or not zone.get("id"):
        raise ValueError("surveyed stationary location missing")
    if zone["kind"] != "other_street":
        source = zone.get("designation_source")
        if not isinstance(source, dict) or not source.get("path") or not re.fullmatch(r"[0-9a-f]{64}", source.get("sha256", "")):
            raise ValueError("location designation reference missing")
        if zone["kind"] in ("route_origin", "route_destination") and zone.get("route_id") != context["route_id"]:
            raise ValueError("endpoint designation does not bind assigned route")
    first_time = None
    previous_time = None
    stationary_frames = 0
    brake_applied_frames = 0
    driver_absent_frames = 0
    zone_occupied_frames = 0
    for i, frame in enumerate(frames):
        if frame.get("frame_id") != i:
            raise ValueError("nonconsecutive Native frame map")
        time = finite(frame.get("sim_time_s"), "frame time")
        if first_time is None:
            first_time = time
        if previous_time is not None and abs(time - previous_time - 0.05) > 1e-5:
            raise ValueError("20 Hz frame timing gap")
        previous_time = time
        cameras = frame.get("camera_frames")
        if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS) or any(cameras[name] != i for name in CAMERAS):
            raise ValueError("missing or mismatched four source-camera frames")
        speed = finite(frame.get("bus_speed_mps"), "bus speed")
        if speed < 0:
            raise ValueError("negative bus speed magnitude")
        brake = frame.get("parking_brake_applied")
        driver_present = frame.get("driver_present")
        if not isinstance(brake, bool) or not isinstance(driver_present, bool):
            raise ValueError("brake or driver-presence source missing")
        occupied = frame.get("occupied_zone_id")
        if not occupied:
            raise ValueError("original bus location readback missing")
        if occupied == zone["id"]:
            zone_occupied_frames += 1
        if speed <= 0.1:
            stationary_frames += 1
            brake_applied_frames += int(brake)
            driver_absent_frames += int(not driver_present)
    if previous_time - first_time + 0.05 < 30 - 1e-5:
        raise ValueError("capture shorter than 30 seconds")
    return {
        "format": "bus-standing-measurement-v1", "source_kind": source_kind,
        "frame_count": len(frames), "zone_kind_observed": zone["kind"],
        "zone_id": zone["id"], "route_id": context["route_id"],
        "stationary_frames": stationary_frames,
        "stationary_brake_applied_frames": brake_applied_frames,
        "stationary_driver_absent_frames": driver_absent_frames,
        "zone_occupied_frames": zone_occupied_frames,
        "designation_reference_present": zone["kind"] != "other_street",
        "standing_or_parking_judgment": "unresolved", "legal_judgment": "unresolved",
    }


def measure_saved(root, *, source_kind="original_native"):
    """Join original Native samples and four camera identities from saved bytes.

    A designation document is only provenance for later independent review. Its
    presence and hash never establish that a zone was officially designated.
    """
    root = Path(root)
    def read(name):
        path = root / name
        if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError("missing required source: " + str(name))
        return path.read_bytes()

    seal = None
    if source_kind == "original_native":
        provenance = json.loads(read("acquisition-provenance.json"))
        seal = json.loads(read("capture-seal.json"))
        if (provenance.get("provenance_kind") != "native" or
                provenance.get("diagnostic_fixture") is not False or
                seal.get("format") != "worker-sealed-capture" or
                seal.get("provenance_kind") != "native" or
                seal.get("diagnostic_fixture") is not False or
                seal.get("frames") != 600 or
                seal.get("restoration", {}).get("restored") is not True):
            raise ValueError("original Native acquisition seal missing or invalid")

    context = json.loads(read("bus-context.json"))
    zone = context.get("zone", {})
    reference = zone.get("designation_source")
    if zone.get("kind") != "other_street":
        if not isinstance(reference, dict) or not reference.get("path"):
            raise ValueError("location designation reference missing")
        relative = Path(reference["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("designation path escapes saved attempt")
        actual_hash = hashlib.sha256(read(relative)).hexdigest()
        if actual_hash != reference.get("sha256"):
            raise ValueError("designation reference hash differs from saved source")
    def lines(name):
        return [json.loads(line) for line in read(name).splitlines()]
    history = lines("bus-history.jsonl")
    maps = lines("video_frames.jsonl")
    camera_hashes = {name + ".mkv": hashlib.sha256(read(name + ".mkv")).hexdigest()
                     for name in CAMERAS}
    if seal is not None:
        for name in ("bus-context.json", "bus-history.jsonl", "video_frames.jsonl", *camera_hashes):
            if seal.get("sources", {}).get(name) != hashlib.sha256(read(name)).hexdigest():
                raise ValueError("saved source differs from sealed Native capture: " + name)
    if len(history) != len(maps):
        raise ValueError("Native history and camera frame map length differ")
    frames = []
    for index, (row, mapped) in enumerate(zip(history, maps)):
        if row.get("video_frame") != index or mapped.get("video_frame") != index:
            raise ValueError("Native history and camera frame map indices differ")
        native = row.get("native_frame")
        if mapped.get("native_frame") != native:
            raise ValueError("Native history and camera frame identities differ")
        camera_native = mapped.get("camera_native_frames")
        frames.append({
            "frame_id": index, "sim_time_s": row.get("time_s"),
            "camera_frames": {name: index for name in CAMERAS}
            if isinstance(camera_native, dict) and
            set(camera_native) == set(CAMERAS) and
            all(camera_native[name] == native for name in CAMERAS)
            else camera_native,
            "bus_speed_mps": row.get("bus_speed_mps"),
            "parking_brake_applied": row.get("parking_brake_applied"),
            "driver_present": row.get("driver_present"),
            "occupied_zone_id": row.get("occupied_zone_id"),
        })
    result = measure(frames, context, source_kind=source_kind)
    result["source_sha256"] = {
        name: hashlib.sha256(read(name)).hexdigest()
        for name in ("bus-context.json", "bus-history.jsonl", "video_frames.jsonl")
    }
    result["source_sha256"].update(camera_hashes)
    if reference:
        result["source_sha256"][reference["path"]] = reference["sha256"]
    result["designation_authority_verified"] = False
    result["route_assignment_verified"] = context.get("route_assignment_verified") is True
    result["vehicle_class_verified"] = context.get("vehicle_class_verified") is True
    result["driver_presence_verified"] = context.get("driver_presence_verified") is True
    return result
