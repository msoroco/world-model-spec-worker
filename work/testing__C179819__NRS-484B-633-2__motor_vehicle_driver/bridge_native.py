"""Native construction seam for a reviewed elevated highway structure.

The CARLA adapter must read back mapped structure and sign geometry. This
module never substitutes a sign prop for evidence of Department authorization.
"""

from __future__ import annotations

from bridge_observations import validate_site


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")

ADAPTER_METHODS = (
    "loaded_map_sha256", "snapshot_settings", "configure_sync", "readback_sync",
    "restore_settings", "readback_restored", "read_structure_ends",
    "spawn_vehicle", "read_vehicle_class", "set_crossing_route",
    "set_target_speed_mps", "spawn_sign", "read_sign_station_and_face",
    "spawn_cameras", "tick_capture", "destroy", "actor_id",
)


def require_adapter(adapter):
    absent = [name for name in ADAPTER_METHODS if not callable(getattr(adapter, name, None))]
    if absent:
        raise ValueError("Native elevated-highway adapter methods missing: " + ", ".join(absent))


def construct(adapter, dossier, case, owned=None):
    """Configure one exact case; all structure, vehicle and sign facts read back."""
    require_adapter(adapter)
    site = validate_site(dossier, expected_case=case["case_id"])
    if adapter.loaded_map_sha256() != dossier["map_opendrive_sha256"]:
        raise ValueError("loaded original OpenDRIVE differs from reviewed site")
    mapped = adapter.read_structure_ends(dossier["structure_id"])
    if mapped != (site["end_a_station_m"], site["end_b_station_m"]):
        raise ValueError("mapped original elevated-structure ends differ")
    direction = case["travel_direction_request"]
    if dossier["travel_direction"] != direction:
        raise ValueError("reviewed site and exact approach direction differ")
    if dossier["structure_kind"] != case["structure_kind_request"]:
        raise ValueError("reviewed structure kind differs from exact case")
    if owned is None:
        owned = []
    ego = adapter.spawn_vehicle("motor_vehicle", direction, dossier["structure_id"])
    owned.append(ego)
    if adapter.read_vehicle_class(ego) != "motor_vehicle":
        raise ValueError("conventional motor vehicle readback required")
    adapter.set_crossing_route(ego, direction, site["end_a_station_m"], site["end_b_station_m"])
    requested_mph = site["declared_maximum_mph"] + case["requested_speed_delta_from_declared_maximum_mph"]
    if requested_mph <= 0:
        raise ValueError("nonpositive requested crossing speed")
    adapter.set_target_speed_mps(ego, requested_mph / 2.2369362920544)
    signs = {}
    for end in ("end_a", "end_b"):
        sign_source = dossier["signs"][end]
        sign = adapter.spawn_sign(end, sign_source["station_m"], site["declared_maximum_mph"],
                                  sign_source["face_direction"])
        owned.append(sign)
        station, face = adapter.read_sign_station_and_face(sign)
        if station != sign_source["station_m"] or face != sign_source["face_direction"]:
            raise ValueError("original spawned sign station/face readback differs")
        signs[end] = sign
    cameras = adapter.spawn_cameras(ego, CAMERAS, dossier)
    if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS) or any(
            camera is None for camera in cameras.values()):
        raise ValueError("four synchronized original camera actors required")
    owned.extend(cameras[name] for name in CAMERAS)
    return {"ego": ego, "signs": signs, "cameras": cameras, "owned": owned,
            "requested_speed_mph": requested_mph,
            "sign_offsets_ft": site["sign_offsets_ft"]}


def destroy_owned(adapter, actors, original_settings):
    destroyed = []
    failures = []
    for actor in reversed(actors):
        try:
            adapter.destroy(actor)
            destroyed.append(adapter.actor_id(actor))
        except Exception as error:
            failures.append(str(error))
    try:
        adapter.restore_settings(original_settings)
        if adapter.readback_restored(original_settings) is not True:
            failures.append("original world settings not restored")
    except Exception as error:
        failures.append(str(error))
    if failures:
        raise ValueError("Native owner cleanup failed: " + "; ".join(failures))
    return destroyed
