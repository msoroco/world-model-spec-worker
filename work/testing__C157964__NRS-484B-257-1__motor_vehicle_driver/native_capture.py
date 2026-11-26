"""Source-gated, adapter-injected original attempt producer for C157964.

The adapter owns CARLA-specific calls. Diagnostic adapters exercise lifecycle and
joins on CPU; only a separately reviewed Native run can supply physical evidence.
"""

import hashlib
import json
from pathlib import Path

from reviewed_site import SITE_ROLES, read_reviewed_site
from yield_view import construct, measure_original, require


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _row(snapshot, observation, site, case, packet_sha):
    require(isinstance(snapshot, dict) and isinstance(observation, dict),
            "original snapshot/observation missing")
    frame, time = snapshot.get("frame"), snapshot.get("time_s")
    require(type(frame) is int and type(time) in (int, float),
            "original frame/time missing")
    fields = (
        "ego_id", "through_id", "ego_speed_mps", "through_center_station_m",
        "through_min_vertex_station_m", "ego_leading_station_m",
        "through_phase", "ego_across_or_within", "officer_controls",
        "signal_controls", "stop_line_present", "near_crosswalk_present",
        "sight_observation", "body_vertices", "control_readback",
        "all_at_reference_observed",
    )
    require(all(key in observation for key in fields),
            "original participant, sight or control readback missing")
    control = observation["control_readback"]
    require(isinstance(control, dict) and
            control.get("officer_directing_traffic") is case.officer_controls and
            control.get("traffic_signal_controlling") is False and
            (not case.officer_controls or
             isinstance(control.get("officer_actor_id"), str) and
             bool(control["officer_actor_id"])),
            "observed governing-control readback differs")
    row = {"original_frame": frame, "time_s": time,
           **{key: observation[key] for key in fields},
           "source_sha256": packet_sha,
           "reference_source_sha256": site["nearest_view_location_source_sha256"]}
    groups = {
        "ego_motion": ("ego_id", "ego_speed_mps", "ego_leading_station_m"),
        "through_motion": ("through_id", "through_center_station_m",
                           "through_min_vertex_station_m", "through_phase"),
        "body_geometry": ("body_vertices", "ego_leading_station_m",
                          "through_min_vertex_station_m"),
        "reference": ("reference_source_sha256", "stop_line_present",
                      "near_crosswalk_present", "all_at_reference_observed"),
        "sight": ("sight_observation",),
        "control": ("officer_controls", "signal_controls", "control_readback"),
    }
    for name, keys in groups.items():
        row[name + "_sha256"] = _sha(_encoded({key: row[key] for key in keys}))
    return row


def capture(adapter, packet_path, source_root, output_dir, case, *, diagnostic=False):
    """Capture 900 joined ticks and four original camera streams.

    Adapter methods: snapshot_settings, set_synchronous, spawn_vehicle,
    set_yield_approach, set_through_phase, set_officer_control, start_cameras,
    tick, observe, camera_packets, stop_cameras, destroy, restore_settings.
    The output seal is written only after all source and measurement checks pass.
    """
    site, packet_sha = read_reviewed_site(packet_path, source_root, case)
    if not diagnostic:
        require(adapter.provenance() == "original_native",
                "original Native adapter provenance missing")
    out = Path(output_dir)
    require(not out.exists(), "attempt output already exists")
    settings = adapter.snapshot_settings()
    owned = ()
    cameras_started = False
    try:
        adapter.set_synchronous(0.05)
        built = construct(adapter, site, case)
        owned = built["owned"]
        adapter.start_cameras(owned, VIEWS, site["camera_dimensions"])
        cameras_started = True
        out.mkdir(parents=True)
        rows = []
        camera_index = {view: [] for view in VIEWS}
        first_frame = None
        first_time = None
        for i in range(900):
            snapshot = adapter.tick()
            row = _row(snapshot, adapter.observe(owned, snapshot), site, case, packet_sha)
            if first_frame is None:
                first_frame, first_time = row["original_frame"], row["time_s"]
            require(row["original_frame"] == first_frame + i and
                    abs(row["time_s"] - first_time - i / 20) <= .005,
                    "Native frame/time continuity failed")
            packets = adapter.camera_packets(snapshot)
            require(isinstance(packets, dict) and set(packets) == set(VIEWS),
                    "four original camera packets missing")
            for view in VIEWS:
                packet = packets[view]
                require(isinstance(packet, dict) and
                        packet.get("frame") == row["original_frame"] and
                        abs(packet.get("time_s", -1) - row["time_s"]) <= .005,
                        "camera frame/time join failed")
                expected = site["camera_dimensions"][view]
                require([packet.get("width"), packet.get("height")] == expected and
                        packet.get("sensor_id"), "camera dimension/sensor differs")
                payload = packet.get("png")
                require(isinstance(payload, bytes) and payload.startswith(PNG_SIGNATURE),
                        "original PNG packet missing")
                relative = f"cameras/{view}/{i:04d}.png"
                target = out / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
                camera_index[view].append({"frame": row["original_frame"],
                                           "time_s": row["time_s"],
                                           "sensor_id": packet["sensor_id"],
                                           "path": relative, "sha256": _sha(payload)})
            rows.append(row)
        measured = measure_original(rows, site, case)
        _write_json(out / "rows.json", rows)
        _write_json(out / "camera-index.json", camera_index)
        _write_json(out / "measurement.json", measured)
        final_site, final_packet_sha = read_reviewed_site(packet_path, source_root, case)
        require(final_packet_sha == packet_sha and final_site == site,
                "reviewed site changed during capture")
        source_bytes = Path(packet_path).read_bytes()
        (out / "reviewed-site-packet.json").write_bytes(source_bytes)
        references = json.loads(source_bytes)["sources"]
        source_index = {}
        for role in SITE_ROLES:
            ref = references[role]
            payload = (Path(source_root) / ref["path"]).read_bytes()
            require(_sha(payload) == ref["sha256"],
                    "reviewed source changed during copy: " + role)
            relative = f"reviewed-sources/{role}.source"
            target = out / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            source_index[role] = {"path": relative, "sha256": ref["sha256"]}
        _write_json(out / "reviewed-source-index.json", source_index)
        seal = {"format": "c157964-native-attempt-v1", "case_id": case.case_id,
                "diagnostic_fixture": bool(diagnostic), "frame_count": 900,
                "fps": 20, "views": list(VIEWS), "site_packet_sha256": packet_sha,
                "rows_sha256": _sha((out / "rows.json").read_bytes()),
                "camera_index_sha256": _sha((out / "camera-index.json").read_bytes()),
                "measurement_sha256": _sha((out / "measurement.json").read_bytes()),
                "reviewed_source_index_sha256": _sha((out / "reviewed-source-index.json").read_bytes()),
                "physical_completion": "unverified",
                "legal_judgment": None}
        _write_json(out / "seal.json", seal)
        return seal
    finally:
        try:
            if cameras_started:
                adapter.stop_cameras()
        finally:
            try:
                for actor in reversed(owned):
                    adapter.destroy(actor)
            finally:
                adapter.restore_settings(settings)
