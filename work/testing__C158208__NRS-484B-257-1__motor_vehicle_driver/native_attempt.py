"""CARLA-lazy owner for one original nearest-view acquisition attempt.

An operator adapter supplies actual actor creation, readback and camera bytes.
This module binds their timeline to the sealed saved sources and restores the
original world before any saved-only processing is authorized.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from camera_sources import audit_camera_sources, write_camera_sources
from source_tick_capture import TickCapture, validate_geometry, write_capture_identity
from yield_control import KINDS, control
from through_traffic_control import control as control_through, validate_plan as validate_through_plan
from branch_site_preflight import validate_site_branch


ASSIGNMENT = "testing__C158208__NRS-484B-257-1__motor_vehicle_driver"
REVIEW_SOURCES = ("native_map", "yield_sign", "stop_line_survey",
                  "crosswalk_survey", "sidewalk_survey", "through_highway_survey",
                  "control_survey", "nearest_view_survey")


def verify_review_sources(site: dict, site_path: Path, *, diagnostic_fixture: bool) -> dict:
    """Reopen every original survey source before trusting a reviewed site."""
    if diagnostic_fixture:
        if site.get("diagnostic_fixture") is not True:
            raise ValueError("diagnostic mode requires explicit fixture provenance")
        return {}
    if site.get("source_provenance") != "native_operator_review":
        raise ValueError("original Native operator review provenance required")
    bindings = site.get("source_bindings")
    if not isinstance(bindings, dict) or set(bindings) != set(REVIEW_SOURCES):
        raise ValueError("complete original Native site source bindings required")
    hashes = {}
    for name in REVIEW_SOURCES:
        source = bindings[name]
        if not isinstance(source, dict):
            raise ValueError(f"{name} source binding missing")
        relative = source.get("path")
        if not isinstance(relative, str) or Path(relative).name != relative or not relative:
            raise ValueError(f"{name} original source must be an adjacent file")
        path = site_path.parent / relative
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != source.get("sha256"):
            raise ValueError(f"{name} original source hash differs")
        hashes[name] = digest
    if hashes["native_map"] != site.get("map_opendrive_sha256"):
        raise ValueError("original map source differs from reviewed map hash")
    return hashes


def run_native_attempt(client, carla_adapter, restore_api, *, case_id: str,
                       construction: Path, reviewed_site_packet: Path,
                       attempt: Path, diagnostic_fixture: bool = False) -> dict:
    """Acquire one exact case, then destroy actors and verify world restore.

    The adapter must implement ``configure(world, site)``, ``spawn(world, site)``,
    ``observe(world, actors, frame)`` and ``apply_control(actors, command)``.
    ``observe`` returns ``raw_tick`` and ``cameras`` from the just-ticked world.
    Only an explicit diagnostic call may use three frames; original mode uses
    all 900 frames. No method may synthesize source observations.
    """
    if case_id not in {ASSIGNMENT + "__" + kind for kind in KINDS}:
        raise ValueError("unknown exact nearest-view case")
    construction = Path(construction)
    if not construction.is_file() or not construction.read_bytes():
        raise ValueError("exact construction file required")
    reviewed_site_packet = Path(reviewed_site_packet)
    site_bytes = reviewed_site_packet.read_bytes()
    site = json.loads(site_bytes)
    if site.get("review_status") != "reviewed" or site.get("cell_id") != "C158208":
        raise ValueError("reviewed C158208 Native site required")
    geometry = site.get("capture_geometry")
    validate_geometry(geometry)
    kind = case_id.removeprefix(ASSIGNMENT + "__")
    viewpoint_station = (site.get("ego_view_station_m") if kind.startswith("nearest_view")
                         else site.get("stopping_reference_station_m"))
    if (isinstance(viewpoint_station, bool) or
            not isinstance(viewpoint_station, (int, float)) or
            not math.isfinite(viewpoint_station)):
        raise ValueError("reviewed finite viewpoint station required")
    context = site.get("reviewed_context")
    if not isinstance(context, dict):
        raise ValueError("reviewed sign and control context required")
    if diagnostic_fixture and not all(context.get(key) is True for key in (
            "yield_sign_governs_approach", "no_marked_stop_line", "no_near_side_crosswalk",
            "no_sidewalk_derived_crosswalk", "through_highway_confirmed", "no_officer_control",
            "no_signal_control", "viewpoint_reviewed")):
        raise ValueError("reviewed sign, nearest-view and control context required")
    if not diagnostic_fixture:
        validate_site_branch(site, case_id)
    verify_review_sources(site, reviewed_site_packet,
                          diagnostic_fixture=diagnostic_fixture)
    motion_plan = site.get("native_scene", {}).get("through_vehicle", {}).get("motion_plan")
    if not diagnostic_fixture:
        validate_through_plan(motion_plan)
    world = client.get_world()
    actual_map = world.get_map().to_opendrive().encode()
    if hashlib.sha256(actual_map).hexdigest() != site.get("map_opendrive_sha256"):
        raise ValueError("reviewed site does not match loaded Native map")
    saved = restore_api.snapshot(client)
    owned = []
    primary_error = None
    cleanup_errors = []
    frames = []
    result = None
    try:
        carla_adapter.configure(world, site)
        owned = list(carla_adapter.spawn(world, site))
        if not owned:
            raise ValueError("Native scene spawned no owned actors")
        writer = TickCapture(Path(attempt), geometry, context)
        first_tick_time = None
        for _ in range(3 if diagnostic_fixture else 900):
            frame = world.tick()
            snapshot = world.get_snapshot()
            if frame != snapshot.frame:
                raise ValueError("Native world tick/snapshot frame differs")
            observation = carla_adapter.observe(world, owned, frame)
            raw = observation["raw_tick"]
            if first_tick_time is None:
                first_tick_time = raw["time_s"]
            if raw.get("frame") != frame or abs(raw.get("time_s", float("inf")) -
                                                 snapshot.timestamp.elapsed_seconds) > .001:
                raise ValueError("Native original tick readback differs from world snapshot")
            derived = writer.append(raw)
            camera = observation["cameras"]
            frames.append({"frame": frame, "time_s": raw["time_s"], "cameras": camera})
            command = control(case_id.removeprefix(ASSIGNMENT + "__"), {
                "ego_speed_mps": derived["ego_speed_mps"],
                "distance_to_view_point_m": viewpoint_station - derived["ego_front_station_m"],
                "through_vehicle_in_conflict_interval":
                    derived["through_vehicle_within_intersection"],
                "yield_sign_governs_approach": raw["sign_present"],
                "viewpoint_source_verified": context.get("viewpoint_reviewed", True),
            })
            if motion_plan is not None:
                velocity = raw["through_vehicle"].get("velocity_xy_mps")
                if not isinstance(velocity, list) or len(velocity) != 2:
                    raise ValueError("original through-vehicle velocity source missing")
                command["through_control"] = control_through(
                    motion_plan, raw["time_s"] - first_tick_time,
                    math.hypot(velocity[0], velocity[1]))
            carla_adapter.apply_control(owned, command)
        writer.close()
        write_capture_identity(Path(attempt), case_id, construction,
                               Path(reviewed_site_packet), actual_map,
                               diagnostic_fixture=diagnostic_fixture)
        write_camera_sources(Path(attempt), frames,
                             diagnostic_fixture=diagnostic_fixture)
        camera_audit = audit_camera_sources(Path(attempt),
                                            diagnostic_fixture=diagnostic_fixture)
        result = {"format": "c158208-native-owner-release-v1", "case_id": case_id,
                  "source_kind": "synthetic_fixture" if diagnostic_fixture else "original_capture",
                  "frame_count": len(frames), "camera_audit": camera_audit,
                  "capture_identity_sha256": hashlib.sha256(
                      (Path(attempt) / "capture-identity.json").read_bytes()).hexdigest(),
                  "physical_acceptance": False, "legal_status": "unresolved"}
    except BaseException as exc:
        primary_error = exc
    finally:
        for actor in reversed(owned):
            try:
                carla_adapter.destroy(actor)
            except BaseException as exc:
                cleanup_errors.append(f"actor destruction: {exc}")
        try:
            restored = restore_api.restore(client, saved)
            if restored.get("restored") is not True:
                cleanup_errors.append("world restore lacked readback")
        except BaseException as exc:
            cleanup_errors.append(f"world restore: {exc}")
    if cleanup_errors:
        raise RuntimeError("Native owner release failed: " + "; ".join(cleanup_errors)) from primary_error
    if primary_error is not None:
        raise primary_error
    result["world_restore"] = restored
    (Path(attempt) / "native-owner-release.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result
