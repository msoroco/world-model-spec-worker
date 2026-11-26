"""Native acquisition protocol for the five exact door-interaction cases.

The adapter owns CARLA objects and must return original observations. This
module never substitutes a planned action for an observed driver act.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from site_contract import CASE_ACTIONS, read_packet, validate_site
from delivery_measure import measure


CAMERAS = ("front", "rear", "left", "right")
RATE_HZ = 20
FRAME_COUNT = 900


def actor_id(actor) -> str:
    """Use a Native actor's stable ID, never its Python object rendering."""
    value = getattr(actor, "id", actor)
    if type(value) not in (int, str) or not str(value):
        raise ValueError("original actor ID is missing")
    return str(value)


def capture(adapter, *, survey_path: Path, survey_sha256: str,
            case_id: str, output: Path) -> dict:
    """Capture one exact case through a source-reporting CARLA adapter.

    Adapter methods: map_sha256(), configure_site(packet, site),
    spawn_parked(packet), spawn_passing(packet, variant),
    spawn_driver(packet), attach_cameras(parked, CAMERAS),
    command_act(driver, parked, act, side), tick(), observe(frame_id,
    driver, parked, passing), camera_frame(view, frame_id), and cleanup().
    ``observe`` must read original Native state, including act envelope and
    moving-body vertices. The four camera callbacks must return bytes.
    """
    key = case_id.rsplit("__", 1)[-1]
    if key not in CASE_ACTIONS or case_id != Path(__file__).resolve().parent.name + "__" + key:
        raise ValueError("case ID does not name one of the exact actions")
    packet = read_packet(survey_path, survey_sha256)
    site = validate_site(packet, key)
    if adapter.map_sha256() != packet["map_sha256"]:
        raise ValueError("loaded Native map differs from surveyed source")
    # The runtime materializes runner.py, config.json and construction.json in
    # this directory before launching Native. Only prior acquisition products
    # are collisions; rejecting all existing files makes live capture impossible.
    if (output / "native-trace.json").exists() or (output / "cameras").exists():
        raise ValueError("output already contains a Native acquisition")
    output.mkdir(parents=True, exist_ok=True)
    frames = []
    first_native_time_s = None
    try:
        adapter.configure_site(packet, site)
        parked = adapter.spawn_parked(packet)
        passing = adapter.spawn_passing(packet, site["clearance_variant"])
        driver = adapter.spawn_driver(packet)
        adapter.attach_cameras(parked, CAMERAS)
        if not all((parked, passing, driver)):
            raise ValueError("three original actors are required")
        if len({actor_id(parked), actor_id(passing), actor_id(driver)}) != 3:
            raise ValueError("Native participant IDs collide")
        if actor_id(driver) != str(packet["driver_actor_id"]):
            raise ValueError("selected Native driver differs from surveyed driver")
        for index in range(FRAME_COUNT):
            native_id, sim_time_s = adapter.tick()
            if type(native_id) is not int or (frames and native_id != frames[-1]["frame_id"] + 1):
                raise ValueError("Native frame ID gap")
            if type(sim_time_s) not in (int, float) or not math.isfinite(sim_time_s):
                raise ValueError("Native simulation clock invalid")
            if first_native_time_s is None:
                first_native_time_s = float(sim_time_s)
            episode_time_s = float(sim_time_s) - first_native_time_s
            if abs(episode_time_s - index / RATE_HZ) > 1e-4:
                raise ValueError("Native simulation clock drift")
            if index == RATE_HZ * 10:
                adapter.command_act(driver, parked, site["selected_act"],
                                    site["selected_door_side"])
            observed = adapter.observe(native_id, driver, parked, passing)
            if not isinstance(observed, dict):
                raise ValueError("original actor observation is missing")
            if site["requested_engineering_clearance_m"] is not None and not (
                    isinstance(observed.get("act_envelope_xy"), list) and
                    isinstance(observed.get("passing_body_xy"), list)):
                raise ValueError("original door and passing-body outlines are required for clearance sweep")
            observed = dict(observed)
            observed.update(frame_id=native_id, sim_time_s=episode_time_s,
                            native_elapsed_time_s=float(sim_time_s),
                            camera_frames={view: native_id for view in CAMERAS},
                            camera_sha256={})
            for view in CAMERAS:
                image = adapter.camera_frame(view, native_id)
                if not isinstance(image, bytes) or not image:
                    raise ValueError("original camera callback missing: " + view)
                observed["camera_sha256"][view] = hashlib.sha256(image).hexdigest()
                location = output / "cameras" / view / f"{native_id:06d}.png"
                location.parent.mkdir(parents=True, exist_ok=True)
                location.write_bytes(image)
            frames.append(observed)
        trace = {"source_kind": "native_original", "case_id": case_id,
                 "sample_rate_hz": RATE_HZ,
                 "fixed_context": {
                     "map_sha256": packet["map_sha256"],
                     "survey_sha256": survey_sha256,
                     "loading_site_id": packet["loading_site_id"],
                     "parked_vehicle_id": actor_id(parked),
                     "driver_id": actor_id(driver),
                     "passing_vehicle_id": actor_id(passing),
                     "traffic_route_id": packet.get("traffic_route_id", packet["lane_id"]),
                     "camera_contract_id": "four-camera-20hz-900f",
                     "requested_engineering_clearance_m": site["requested_engineering_clearance_m"]},
                 "parked_center_xy": packet["parked_center_xy"],
                 "parked_heading_xy": packet["parked_heading_xy"],
                 "frames": frames}
        if adapter.map_sha256() != packet["map_sha256"]:
            raise ValueError("loaded Native map changed during acquisition")
        observed_measurement = measure(trace, expected_case_id=case_id,
                                       expected_act=site["selected_act"],
                                       expected_side=site["selected_door_side"])
        if site["requested_engineering_clearance_m"] is not None and not math.isfinite(
                observed_measurement["minimum_body_gap_m"]):
            raise ValueError("original Native clearance measurement is required")
        if observed_measurement["act_on_closest_side"] != (CASE_ACTIONS[key][1] == "near"):
            raise ValueError("observed act side differs from selected passing-side relation")
        payload = (json.dumps(trace, sort_keys=True, separators=(",", ":")) + "\n").encode()
        (output / "native-trace.json").write_bytes(payload)
        (output / "door-source.json").write_text(json.dumps({
            "case_id": case_id,
            "selected_act": site["selected_act"],
            "selected_side": site["selected_door_side"],
            "source_trace_sha256": hashlib.sha256(payload).hexdigest(),
            "survey_sha256": survey_sha256,
            "site_survey": packet,
            "source_kind": "source_bound_native_door_observation",
            "diagnostic_fixture": False}, sort_keys=True, separators=(",", ":")) + "\n")
        return {"case_id": case_id, "original_trace_sha256": hashlib.sha256(payload).hexdigest(),
                "frame_count": len(frames), "camera_frame_count": len(frames) * len(CAMERAS),
                "survey_sha256": survey_sha256,
                "physical_feasibility": "unverified_until_review"}
    finally:
        adapter.cleanup()
