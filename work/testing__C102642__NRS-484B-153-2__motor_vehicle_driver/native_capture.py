"""Native acquisition protocol for the five exact door-interaction cases.

The adapter owns CARLA objects and must return original observations. This
module never substitutes a planned action for an observed driver act.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from site_contract import CASE_ACTIONS, read_packet, validate_site
from delivery_measure import measure


CAMERAS = ("front", "rear", "left", "right")
RATE_HZ = 20
FRAME_COUNT = 900


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
    if output.exists() and any(output.iterdir()):
        raise ValueError("output directory must be empty")
    output.mkdir(parents=True, exist_ok=True)
    frames = []
    try:
        adapter.configure_site(packet, site)
        parked = adapter.spawn_parked(packet)
        passing = adapter.spawn_passing(packet, site["clearance_variant"])
        driver = adapter.spawn_driver(packet)
        adapter.attach_cameras(parked, CAMERAS)
        if not all((parked, passing, driver)) or len({parked, passing, driver}) != 3:
            raise ValueError("three distinct original actors are required")
        for index in range(FRAME_COUNT):
            native_id, sim_time_s = adapter.tick()
            if type(native_id) is not int or (frames and native_id != frames[-1]["frame_id"] + 1):
                raise ValueError("Native frame ID gap")
            if abs(float(sim_time_s) - index / RATE_HZ) > 1e-4:
                raise ValueError("Native simulation clock drift")
            if index == RATE_HZ * 10:
                adapter.command_act(driver, parked, site["selected_act"],
                                    site["selected_door_side"])
            observed = adapter.observe(native_id, driver, parked, passing)
            if not isinstance(observed, dict):
                raise ValueError("original actor observation is missing")
            observed = dict(observed)
            observed.update(frame_id=native_id, sim_time_s=sim_time_s,
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
                     "parked_vehicle_id": str(parked),
                     "driver_id": str(driver),
                     "passing_vehicle_id": str(passing),
                     "traffic_route_id": packet.get("traffic_route_id", packet["lane_id"]),
                     "camera_contract_id": "four-camera-20hz-900f"},
                 "parked_center_xy": packet["parked_center_xy"],
                 "parked_heading_xy": packet["parked_heading_xy"],
                 "frames": frames}
        if adapter.map_sha256() != packet["map_sha256"]:
            raise ValueError("loaded Native map changed during acquisition")
        observed_measurement = measure(trace, expected_case_id=case_id,
                                       expected_act=site["selected_act"],
                                       expected_side=site["selected_door_side"])
        if observed_measurement["act_on_closest_side"] != (CASE_ACTIONS[key][1] == "near"):
            raise ValueError("observed act side differs from selected passing-side relation")
        payload = (json.dumps(trace, sort_keys=True, separators=(",", ":")) + "\n").encode()
        (output / "native-trace.json").write_bytes(payload)
        return {"case_id": case_id, "original_trace_sha256": hashlib.sha256(payload).hexdigest(),
                "frame_count": len(frames), "camera_frame_count": len(frames) * len(CAMERAS),
                "survey_sha256": survey_sha256,
                "physical_feasibility": "unverified_until_review"}
    finally:
        adapter.cleanup()
