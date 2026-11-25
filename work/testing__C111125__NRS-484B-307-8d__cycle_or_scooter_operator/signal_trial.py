"""Source-gated construction and saved Native measurements for the bicycle straight branch.

This module is CARLA-lazy. Requested phase changes are never treated as observed
signal states. An original attempt must retain the device and detector readbacks.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


class SourceError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SourceError(message)


def _source(ref: dict, root: Path) -> bytes:
    _require(isinstance(ref, dict) and ref.get("path") and ref.get("sha256"), "missing source reference")
    path = (root / ref["path"]).resolve()
    _require(path.is_relative_to(root.resolve()) and path.is_file(), "missing source file")
    raw = path.read_bytes()
    _require(hashlib.sha256(raw).hexdigest() == ref["sha256"], "source hash mismatch")
    return raw


def construct_plan(site: dict, root: Path, case_suffix: str) -> dict:
    """Check map/device/detector authority before proposing a Native actor/route.

    The site packet is produced from map and device inspection, not an authored
    legal assertion. Spawn is deferred to an owner-controlled CARLA adapter.
    """
    source_packets = {}
    for key in ("map_ref", "device_ref", "detector_ref", "blueprint_ref"):
        try:
            source_packets[key] = json.loads(_source(site.get(key), root))
        except json.JSONDecodeError as exc:
            raise SourceError("site source JSON invalid: " + key) from exc
        _require(isinstance(source_packets[key], dict), "site source object missing: " + key)
    _require(site.get("cell_id") == "C111125", "wrong cell")
    _require(site.get("maneuver") == "straight", "wrong maneuver")
    _require(site.get("device_kind") == "official_traffic_control_device", "unverified device")
    _require(site.get("ego_blueprint_class") == "bicycle", "ego is not sourced bicycle")
    _require(site.get("detector_controls_subject_signal") is True, "detector/device link not sourced")
    map_source = source_packets["map_ref"]
    device_source = source_packets["device_ref"]
    detector_source = source_packets["detector_ref"]
    blueprint_source = source_packets["blueprint_ref"]
    _require(all(isinstance(site.get(key), str) and site[key] for key in
                 ("device_id", "detector_id", "ego_blueprint_id", "rider_model_id")),
             "original device, detector, bicycle or rider identity missing")
    _require(all(map_source.get(key) == site.get(key) for key in
                 ("cell_id", "approach_lane_id", "cross_lane_id", "stop_boundary_station_m", "entry_station_m")),
             "site map geometry lacks original source binding")
    _require(device_source.get("device_id") == site.get("device_id") and
             device_source.get("device_kind") == site.get("device_kind") and
             device_source.get("detector_id") == site.get("detector_id"),
             "official device lacks original source binding")
    _require(detector_source.get("detector_id") == site.get("detector_id") and
             detector_source.get("controls_device_id") == site.get("device_id") and
             detector_source.get("zone_lane_id") == site.get("approach_lane_id"),
             "detector/device causal link lacks original source binding")
    _require(blueprint_source.get("ego_blueprint_id") == site.get("ego_blueprint_id") and
             blueprint_source.get("ego_blueprint_class") == site.get("ego_blueprint_class") and
             blueprint_source.get("rider_model_id") == site.get("rider_model_id") and
             isinstance(site.get("rider_model_id"), str) and site["rider_model_id"],
             "bicycle and rider lack original source binding")
    _require(site.get("approach_lane_id") != site.get("cross_lane_id"), "cross approach not separated")
    _require(site.get("stop_boundary_station_m") is not None, "stop boundary missing")
    _require(site.get("entry_station_m") is not None, "entry boundary missing")
    _require(float(site["stop_boundary_station_m"]) < float(site["entry_station_m"]), "boundary order invalid")
    variants = {
        "two_cycles_failed_detection": (2, True, True, "yield"),
        "one_cycle": (1, True, True, "yield"),
        "signal_changes": (2, False, True, "yield"),
        "no_prior_stop": (2, True, False, "yield"),
        "fails_to_yield": (2, True, True, "enter_conflict"),
    }
    _require(case_suffix in variants, "unknown exact case")
    cycles, suppress, stop, yield_policy = variants[case_suffix]
    return {
        "case_suffix": case_suffix,
        "cell_id": "C111125",
        "blueprint_class": "bicycle",
        "map_sha256": site["map_ref"]["sha256"],
        "device_sha256": site["device_ref"]["sha256"],
        "detector_sha256": site["detector_ref"]["sha256"],
        "blueprint_sha256": site["blueprint_ref"]["sha256"],
        "approach_lane_id": site["approach_lane_id"],
        "cross_lane_id": site["cross_lane_id"],
        "stop_boundary_station_m": float(site["stop_boundary_station_m"]),
        "entry_station_m": float(site["entry_station_m"]),
        "requested_full_cycles": cycles,
        "requested_detector_suppression": suppress,
        "requested_prior_stop": stop,
        "requested_yield_policy": yield_policy,
        "source_packet": site,
    }


def spawn_case(world, site: dict, root: Path, case_suffix: str, transform,
               apply_device_policy):
    """Spawn a sourced bicycle and configure the detector/device link.

    ``world`` and ``apply_device_policy`` are injected CARLA adapters. The
    latter must install a per-frame detector readback policy and return its
    source-bound configuration receipt. Failed setup destroys the owned actor.
    """
    plan = construct_plan(site, root, case_suffix)
    blueprint_id = site.get("ego_blueprint_id")
    _require(isinstance(blueprint_id, str) and blueprint_id, "bicycle blueprint ID missing")
    library = world.get_blueprint_library()
    blueprint = library.find(blueprint_id)
    _require(blueprint is not None and blueprint.id == blueprint_id, "bicycle blueprint unavailable")
    actor = world.try_spawn_actor(blueprint, transform)
    _require(actor is not None, "bicycle spawn failed")
    try:
        _require(actor.type_id == blueprint_id, "spawned actor blueprint differs")
        receipt = apply_device_policy(plan, site)
        _require(isinstance(receipt, dict) and receipt.get("detector_sha256") == plan["detector_sha256"], "detector policy receipt missing")
        _require(receipt.get("device_sha256") == plan["device_sha256"], "device policy receipt missing")
        return actor, {"plan": plan, "policy_receipt": receipt,
                       "observed_actor_id": actor.id, "observed_blueprint_id": actor.type_id}
    except Exception:
        actor.destroy()
        raise


def control_step(plan: dict, observed: dict) -> dict:
    """Request stop or straight travel from current readback, without verdicts."""
    for key in ("subject_signal", "cross_signal", "detector_occupied", "detector_output",
                "ego_station_m", "directed_participant_conflict", "complete_device_cycles"):
        _require(key in observed, "live readback missing: " + key)
    _require(observed["complete_device_cycles"] >= 0, "invalid cycle count")
    suffix = plan["case_suffix"]
    if suffix == "one_cycle":
        proceed = observed["complete_device_cycles"] >= 1
    else:
        proceed = observed["complete_device_cycles"] >= 2
    if suffix == "signal_changes":
        proceed = proceed and observed["subject_signal"] == "green"
    else:
        proceed = proceed and observed["subject_signal"] == "red"
    if suffix != "fails_to_yield" and observed["directed_participant_conflict"]:
        proceed = False
    target = "straight_route" if proceed else ("creep_before_boundary" if suffix == "no_prior_stop" else "hold_before_boundary")
    return {"target": target,
            "requested_motion": proceed, "observed_frame": observed.get("frame"),
            "requested_detector_suppression": plan["requested_detector_suppression"]}


def _complete_cycles(states: list[str]) -> int:
    """Count complete observed green, yellow, red rotations, not phase requests."""
    collapsed = [s for i, s in enumerate(states) if i == 0 or s != states[i - 1]]
    count = 0
    for i in range(len(collapsed) - 2):
        if collapsed[i:i + 3] == ["green", "yellow", "red"]:
            count += 1
    return count


def _cycle_window(states: list[str]) -> tuple[int, int] | None:
    """First observed green onset through the last completed red return."""
    transitions = [(i, state) for i, state in enumerate(states)
                   if i == 0 or state != states[i - 1]]
    completed = []
    for i in range(len(transitions) - 2):
        if [item[1] for item in transitions[i:i + 3]] == ["green", "yellow", "red"]:
            completed.append((transitions[i][0], transitions[i + 2][0]))
    return (completed[0][0], completed[-1][1]) if completed else None


def measure_attempt(packet: dict, root: Path, plan: dict) -> dict:
    """Measure original 20 Hz readbacks; preserve uncertainty for later review."""
    sources = {}
    for key in ("native_trace_ref", "device_trace_ref", "detector_trace_ref", "geometry_ref"):
        try:
            sources[key] = json.loads(_source(packet.get(key), root))
        except json.JSONDecodeError as exc:
            raise SourceError("source JSON invalid: " + key) from exc
    _require(packet.get("case_suffix") == plan["case_suffix"], "wrong case trace")
    _require(packet.get("blueprint_class") == "bicycle", "observed actor class missing")
    _require(packet.get("device_sha256") == plan["device_sha256"], "device authority changed")
    _require(packet.get("map_sha256") == plan["map_sha256"], "map authority changed")
    frames = packet.get("frames")
    _require(isinstance(frames, list) and len(frames) >= 2, "original frames missing")
    _require(sources["native_trace_ref"].get("frames") == frames, "joined frames differ from original Native trace")
    _require(sources["native_trace_ref"].get("blueprint_class") == packet["blueprint_class"], "actor class differs from original Native trace")
    _require(sources["geometry_ref"].get("stop_boundary_station_m") == plan["stop_boundary_station_m"] and
             sources["geometry_ref"].get("entry_station_m") == plan["entry_station_m"], "original geometry differs")
    device_rows = sources["device_trace_ref"].get("frames")
    detector_rows = sources["detector_trace_ref"].get("frames")
    _require(isinstance(device_rows, list) and isinstance(detector_rows, list) and
             len(device_rows) == len(frames) and len(detector_rows) == len(frames), "device/detector frame coverage missing")
    for f, device, detector in zip(frames, device_rows, detector_rows):
        _require(device == {"frame": f.get("frame"), "subject_signal": f.get("subject_signal"),
                            "cross_signal": f.get("cross_signal")} and
                 detector == {"frame": f.get("frame"), "occupied": f.get("detector_occupied"),
                              "output": f.get("detector_output")}, "original source streams disagree")
    _require(isinstance(frames[0]["frame"], int) and not isinstance(frames[0]["frame"], bool) and frames[0]["frame"] >= 0,
             "invalid first frame")
    _require([f.get("frame") for f in frames] == list(range(frames[0]["frame"], frames[0]["frame"] + len(frames))), "frame discontinuity")
    _require(all(isinstance(f.get("timestamp_s"), (int, float)) and
                 not isinstance(f["timestamp_s"], bool) and math.isfinite(f["timestamp_s"])
                 for f in frames), "finite timestamps missing")
    _require(all(0.049 <= frames[i + 1]["timestamp_s"] - frames[i]["timestamp_s"] <= 0.051 for i in range(len(frames) - 1)), "not 20 Hz")
    needed = ("subject_signal", "cross_signal", "detector_occupied", "detector_output", "ego_speed_mps", "ego_station_m", "directed_participant_conflict")
    _require(all(all(k in f for k in needed) for f in frames), "required original readback missing")
    _require(all(f["subject_signal"] in ("red", "yellow", "green", "unknown") and
                 f["cross_signal"] in ("red", "yellow", "green", "unknown") for f in frames),
             "invalid original signal")
    _require(all(type(f["detector_occupied"]) is bool and type(f["detector_output"]) is bool and
                 type(f["directed_participant_conflict"]) is bool for f in frames),
             "invalid original detector or participant state")
    _require(all(isinstance(f["ego_speed_mps"], (int, float)) and
                 not isinstance(f["ego_speed_mps"], bool) and math.isfinite(f["ego_speed_mps"]) and
                 f["ego_speed_mps"] >= 0 and isinstance(f["ego_station_m"], (int, float)) and
                 not isinstance(f["ego_station_m"], bool) and math.isfinite(f["ego_station_m"])
                 for f in frames), "invalid original bicycle motion")
    entry = next((i for i, f in enumerate(frames) if f["ego_station_m"] >= plan["entry_station_m"]), None)
    _require(entry is not None, "no observed straight entry")
    _require(all(frames[i]["ego_station_m"] <= frames[i + 1]["ego_station_m"] for i in range(len(frames) - 1)), "route not straight/monotone")
    prior = frames[:entry]
    stop = any(f["ego_station_m"] < plan["stop_boundary_station_m"] and f["ego_speed_mps"] <= 0.05 for f in prior)
    held_red = all(f["subject_signal"] == "red" for f in frames[:entry + 1])
    occupied = any(f["detector_occupied"] is True for f in prior)
    cycles = _complete_cycles([f["cross_signal"] for f in prior])
    cycle_window = _cycle_window([f["cross_signal"] for f in prior])
    occupied_through_cycles = (cycle_window is not None and
                               all(f["detector_occupied"] is True
                                   for f in prior[cycle_window[0]:cycle_window[1] + 1]))
    failed_output = occupied_through_cycles and all(
        f["detector_output"] is False for f in prior[cycle_window[0]:cycle_window[1] + 1])
    conflict_at_entry = frames[entry]["directed_participant_conflict"] is True
    return {
        "case_suffix": plan["case_suffix"],
        "source_sha256": {k: packet[k]["sha256"] for k in ("native_trace_ref", "device_trace_ref", "detector_trace_ref", "geometry_ref")},
        "map_sha256": plan["map_sha256"], "device_sha256": plan["device_sha256"],
        "detector_sha256": plan["detector_sha256"], "blueprint_sha256": plan["blueprint_sha256"],
        "duration_frames": len(frames), "entry_frame": frames[entry]["frame"],
        "prior_stop_observed": stop, "red_held_to_entry": held_red,
        "detector_occupancy_observed": occupied, "detector_failure_observed": failed_output,
        "detector_occupied_through_completed_cycles": occupied_through_cycles,
        "completed_cycle_window_frames": None if cycle_window is None else
            [prior[cycle_window[0]]["frame"], prior[cycle_window[1]]["frame"]],
        "complete_device_cycles_before_entry": cycles,
        "conflict_at_entry": conflict_at_entry,
        "straight_route_observed": True,
        "physical_acceptance": False, "legal_verdict": None,
    }
