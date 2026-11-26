"""Source-gated original hose attempt acquisition through a Native adapter.

The adapter owns CARLA world/session and sensor calls. This module owns the
exact 900-tick source, camera, geometry, custody and cleanup contract.
"""

import hashlib
import json
from pathlib import Path

from fire_hose_delivery import body_over_hose_frames, construct_hose


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCE_ROLES = ("private_way", "hose", "incident", "official", "consent", "vehicle")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def capture(adapter, config, reviewed, packet_path, source_root, output_dir,
            *, diagnostic=False, frame_count=900):
    """Capture joined original rows and camera packets, then seal on success.

    Required adapter methods: provenance, snapshot_settings, set_synchronous,
    hose_transform, spawn_ego, set_route, start_cameras, tick, observe,
    camera_packets, stop_cameras, destroy, restore_settings. A diagnostic fake may request fewer ticks, but
    original acquisition always uses the 900-tick profile.
    """
    if not diagnostic and (adapter.provenance() != "original_native" or frame_count != 900):
        raise ValueError("900-tick original Native provenance required")
    out = Path(output_dir)
    if out.exists():
        raise ValueError("attempt output already exists")
    source_root = Path(source_root).resolve()
    packet_path = Path(packet_path).resolve()
    reviewed_bytes = packet_path.read_bytes()
    settings = adapter.snapshot_settings()
    owned = []
    cameras_started = False
    try:
        adapter.set_synchronous(0.05)
        hose = construct_hose(adapter.world, reviewed["hose"]["blueprint_id"],
                              adapter.hose_transform(reviewed))
        owned.append(hose)
        ego = adapter.spawn_ego(reviewed["vehicle"], reviewed["private_way"])
        if ego is None or not getattr(ego, "id", None):
            raise ValueError("original ego vehicle spawn/readback missing")
        owned.append(ego)
        adapter.set_route(ego, reviewed["private_way"]["ego_route_xy"],
                          config["case"]["planned_hose_crossing"])
        cameras_started = True
        adapter.start_cameras(VIEWS)
        out.mkdir(parents=True)
        frames = []
        cameras = {view: [] for view in VIEWS}
        first_frame = first_time = None
        for index in range(frame_count):
            snapshot = adapter.tick()
            frame, time_s = snapshot.get("frame"), snapshot.get("time_s")
            if type(frame) is not int or type(time_s) not in (int, float):
                raise ValueError("original frame or time missing")
            if first_frame is None:
                first_frame, first_time = frame, time_s
            if frame != first_frame + index or abs(time_s - first_time - index / 20) > 0.005:
                raise ValueError("original 20 Hz frame continuity failed")
            observation = adapter.observe(snapshot, hose)
            if not isinstance(observation, dict) or any(
                    key not in observation for key in ("ego_xy", "ego_body_corners_xy", "ego_actor_id")):
                raise ValueError("original ego body observation missing")
            if observation["ego_actor_id"] != ego.id:
                raise ValueError("original ego actor readback differs")
            row = {"frame": frame, "elapsed_seconds": index / 20,
                   "ego_xy": observation["ego_xy"],
                   "ego_body_corners_xy": observation["ego_body_corners_xy"],
                   "ego_actor_id": observation["ego_actor_id"],
                   "hose_actor_id": hose.id}
            frames.append(row)
            source_packets = adapter.camera_packets(snapshot)
            if not isinstance(source_packets, dict) or set(source_packets) != set(VIEWS):
                raise ValueError("four original camera packets missing")
            for view in VIEWS:
                packet = source_packets[view]
                if packet.get("frame") != frame or abs(packet.get("time_s", -1) - time_s) > 0.005:
                    raise ValueError("camera original frame/time join failed")
                expected_dimensions = config.get("camera_dimensions", {}).get(view)
                if expected_dimensions != ([1920, 1080] if view == "overview" else [1280, 720]):
                    raise ValueError("camera capability profile differs")
                if [packet.get("width"), packet.get("height")] != expected_dimensions:
                    raise ValueError("original camera dimensions differ")
                if not packet.get("sensor_id") or not isinstance(packet.get("png"), bytes) or not packet["png"].startswith(PNG_SIGNATURE):
                    raise ValueError("original camera sensor/PNG missing")
                relative = f"cameras/{view}/{index:04d}.png"
                target = out / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(packet["png"])
                cameras[view].append({"frame": frame, "time_s": time_s,
                                      "sensor_id": packet["sensor_id"],
                                      "path": relative, "sha256": sha(packet["png"])})
        frame_path = out / "frames.jsonl"
        frame_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in frames))
        write_json(out / "camera-index.json", cameras)
        if packet_path.read_bytes() != reviewed_bytes:
            raise ValueError("reviewed original packet changed during capture")
        (out / "reviewed-packet.json").write_bytes(reviewed_bytes)
        saved = {"case_id": config["selected_case_id"],
                 "native": {"result_sha256": "pending", "source_path": "frames.jsonl",
                            "source_sha256": sha(frame_path.read_bytes()), "frames": frames}}
        role_to_saved = {"private_way": "road", "hose": "hose", "incident": "incident",
                         "official": "command_official", "consent": "consent", "vehicle": "vehicle"}
        for role in SOURCE_ROLES:
            ref = reviewed[role]
            payload = (source_root / ref["path"]).read_bytes()
            if sha(payload) != ref["sha256"]:
                raise ValueError(role + " reviewed source changed during copy")
            relative = f"original-context/{role}.json"
            target = out / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            saved[role_to_saved[role]] = {"source_path": relative, "sha256": ref["sha256"],
                                          **{key: value for key, value in ref.items()
                                             if key not in ("path", "sha256")}}
        saved["road"]["private_way_owner"] = reviewed["private_way"]["owner"]
        hits = body_over_hose_frames(saved, config["selected_case_id"],
                                     expected_frames=frame_count)
        if bool(hits) != config["case"]["planned_hose_crossing"]:
            raise ValueError("actual original body passage differs from exact case")
        seal = {"format": "c197786-native-attempt-v1", "case_id": config["selected_case_id"],
                "diagnostic_fixture": bool(diagnostic), "frame_count": frame_count,
                "rate_hz": 20, "views": list(VIEWS),
                "reviewed_packet_sha256": sha(reviewed_bytes),
                "frames_sha256": sha(frame_path.read_bytes()),
                "camera_index_sha256": sha((out / "camera-index.json").read_bytes()),
                "body_contact_frames": hits, "physical_completion": "unreviewed",
                "legal_judgment": None}
        write_json(out / "seal.json", seal)
        saved["native"]["result_sha256"] = sha((out / "seal.json").read_bytes())
        write_json(out / "saved-packet.json", saved)
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
