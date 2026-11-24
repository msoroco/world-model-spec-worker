"""CPU measurement of bus stop/load evidence for LVMC 11.60.030(A)(2).

This is a source-join and physical-event checker. It does not determine
whether a location was legally designated or whether an emergency existed.
"""
from math import isfinite
import re

CAMERAS = ("front", "rear", "left", "right")
ZONE_KINDS = ("bus_stop", "bus_stand", "passenger_loading_zone", "route_origin", "route_destination", "other_street")


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError("missing or nonfinite " + name)
    return float(value)


def measure(frames, context, *, source_kind):
    if source_kind not in ("original_native", "synthetic_native_sample"):
        raise ValueError("undeclared source kind")
    if len(frames) < 600:
        raise ValueError("capture shorter than 30 seconds at 20 Hz")
    if context.get("vehicle_class") != "route_bus_non_tour":
        raise ValueError("non-tour route-bus identity missing")
    if not context.get("route_id") or not context.get("street_id"):
        raise ValueError("route or street identity missing")
    zone = context.get("zone")
    if not isinstance(zone, dict) or zone.get("kind") not in ZONE_KINDS or not zone.get("id"):
        raise ValueError("surveyed loading location missing")
    if zone["kind"] != "other_street":
        designation = zone.get("designation_source")
        if not isinstance(designation, dict) or not designation.get("path") or not re.fullmatch(r"[0-9a-f]{64}", designation.get("sha256", "")):
            raise ValueError("location designation authority missing")
        if zone["kind"] in ("route_origin", "route_destination") and zone.get("route_id") != context["route_id"]:
            raise ValueError("endpoint designation does not bind assigned route")
    if "emergency_source" not in context:
        raise ValueError("emergency context missing")
    previous_time = None
    first_time = None
    stopped_frames = 0
    loading_frames = 0
    observed_boarding = 0
    for i, frame in enumerate(frames):
        if frame.get("frame_id") != i:
            raise ValueError("nonconsecutive original frame map")
        time = finite(frame.get("sim_time_s"), "frame time")
        if first_time is None:
            first_time = time
        if previous_time is not None and abs(time - previous_time - 0.05) > 1e-5:
            raise ValueError("20 Hz frame timing gap")
        previous_time = time
        cameras = frame.get("camera_frames")
        if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS) or any(cameras[k] != i for k in CAMERAS):
            raise ValueError("missing or mismatched four source-camera frames")
        speed = finite(frame.get("bus_speed_mps"), "bus speed")
        if speed < 0:
            raise ValueError("negative bus speed magnitude")
        stopped = speed <= 0.1
        door_open = frame.get("passenger_door_open")
        if not isinstance(door_open, bool):
            raise ValueError("passenger-door source missing")
        boardings = frame.get("boardings")
        if not isinstance(boardings, int) or isinstance(boardings, bool) or boardings < 0:
            raise ValueError("passenger exchange source missing")
        occupied = frame.get("occupied_zone_id")
        if not occupied:
            raise ValueError("bus location readback missing")
        if stopped:
            stopped_frames += 1
        if stopped and door_open and occupied == zone["id"]:
            loading_frames += 1
            observed_boarding += boardings
    if previous_time - first_time + 0.05 < 30 - 1e-5:
        raise ValueError("capture shorter than 30 seconds")
    return {
        "format": "bus-loading-measurement-v1", "source_kind": source_kind,
        "frame_count": len(frames), "zone_kind_observed": zone["kind"],
        "zone_id": zone["id"], "route_id": context["route_id"],
        "stopped_frames": stopped_frames, "door_open_stopped_zone_frames": loading_frames,
        "observed_boardings": observed_boarding,
        "designation_reference_present": zone["kind"] != "other_street",
        "emergency_judgment": "unresolved", "legal_judgment": "unresolved",
    }
