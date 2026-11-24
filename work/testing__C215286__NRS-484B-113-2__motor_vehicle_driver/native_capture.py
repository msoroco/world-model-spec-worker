"""Acquire original reverse motion and crossing geometry at 20 Hz.

The caller owns the Native world, actor and cameras. This code records originals
only; physical completion and pixels are checked independently after capture.
"""

import hashlib
import json
import math
from pathlib import Path

from crosswalk_delivery import construct, control_step, measure
from site_packet import check_world, read, VIEWS


HZ = 20


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _hull(points):
    points = sorted(set((float(p.x), float(p.y)) for p in points))
    if len(points) < 3:
        raise ValueError("original body footprint has fewer than three vertices")

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]
    if len(hull) < 3:
        raise ValueError("original body footprint is degenerate")
    return hull


def _write_once(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
    return _sha(data)


def capture(world, carla, site_path, case_id, output_dir, camera_reader, *, frames=900):
    """Capture a full source-joined interval from an injected Native world."""
    if frames != 900:
        raise ValueError("exact 45 second original interval required")
    packet, packet_raw, source_raw = read(site_path, case_id)
    check_world(world, packet)
    root = Path(output_dir)
    if not root.is_dir() or any(root.iterdir()):
        raise ValueError("fresh empty capture directory required")
    spawn = packet["spawn_transform"]
    transform = carla.Transform(carla.Location(*spawn["xyz"]), carla.Rotation(*spawn["rpy"]))
    built = construct(world, packet, transform)
    ego = built["ego"]
    rows, mapping, cameras = [], [], {name: [] for name in VIEWS}
    first_native = None
    first_time = None
    camera_sensor_ids = None
    previous_position = None
    try:
        for index in range(frames):
            ego_transform = ego.get_transform()
            destination = packet["reverse_route_xy"][-1]
            location = ego_transform.location
            remaining = math.hypot(location.x - destination[0], location.y - destination[1])
            # The same route-endpoint controller applies to all three cases.
            control_step(ego, reverse=True, hold=remaining <= .25,
                         control_factory=carla.VehicleControl)
            native_frame = world.tick()
            snapshot = world.get_snapshot()
            if type(native_frame) is not int or snapshot.frame != native_frame:
                raise ValueError("original world frame/snapshot mismatch")
            now = float(snapshot.timestamp.elapsed_seconds)
            if first_native is None:
                first_native, first_time = native_frame, now
            if native_frame != first_native + index or abs(now - first_time - index / HZ) > .003:
                raise ValueError("original 20 Hz time/frame join failed")
            current = ego.get_transform()
            position = (float(current.location.x), float(current.location.y))
            heading = float(current.rotation.yaw)
            if not math.isfinite(heading):
                raise ValueError("original heading readback invalid")
            if previous_position is not None and math.dist(position, previous_position) > 2:
                raise ValueError("implausible one-frame reverse displacement")
            previous_position = position
            velocity = ego.get_velocity()
            forward = current.get_forward_vector()
            vertices = ego.bounding_box.get_world_vertices(current)
            body = _hull(vertices)
            body_xyz = [[float(p.x), float(p.y), float(p.z)] for p in vertices]
            control = ego.get_control()
            if type(control.reverse) is not bool:
                raise ValueError("original reverse gear readback missing")
            observation = camera_reader(native_frame)
            if not isinstance(observation, dict) or set(observation) != set(VIEWS):
                raise ValueError("four original camera frames required")
            sensor_ids = {view: str(observation[view].get("source_sensor", "")) for view in VIEWS}
            if any(not value for value in sensor_ids.values()) or len(set(sensor_ids.values())) != len(VIEWS):
                raise ValueError("four distinct original camera sensors required")
            if camera_sensor_ids is None:
                camera_sensor_ids = sensor_ids
            if sensor_ids != camera_sensor_ids:
                raise ValueError("original camera sensor identity changed")
            camera_refs = {}
            for view in VIEWS:
                image = observation[view]
                if (type(image.get("frame")) is not int or image["frame"] != native_frame
                        or not image.get("source_sensor") or not isinstance(image.get("bytes"), bytes)
                        or not image["bytes"]):
                    raise ValueError("original camera source/frame mismatch: " + view)
                relative = f"cameras/{view}/{index:04d}.png"
                digest = _write_once(root / relative, image["bytes"])
                camera_refs[view] = {"path": relative, "sha256": digest,
                                     "source_sensor": str(image["source_sensor"])}
                cameras[view].append(camera_refs[view])
            mapping.append({"video_frame": index, "carla_frame": native_frame,
                            "native_frame": native_frame, "time_s": index / HZ,
                            "camera_sources": camera_refs})
            rows.append({"frame": index, "time_s": index / HZ,
                         "native_frame": native_frame, "vehicle_actor_id": int(ego.id),
                         "body_polygon_xy": body,
                         "crosswalk_polygon_xy": packet["crosswalk_polygon_xy"],
                         "velocity_xy": [float(velocity.x), float(velocity.y)],
                         "forward_xy": [float(forward.x), float(forward.y)],
                         "reverse_gear": control.reverse,
                         "position_xy": position, "heading_deg": heading,
                         "body_vertices_m": body_xyz,
                         "velocity_mps": [float(velocity.x), float(velocity.y), float(velocity.z)]})
        # Require actual reverse motion, but never infer a legal or physical target.
        measured = measure(rows, source_id=case_id + ":native:" + str(first_native),
                           map_sha256=packet["map_sha256"],
                           crosswalk_source=packet["crosswalk_source"],
                           vehicle_actor_id=int(ego.id))
        # A source edited while capture was running cannot silently acquire the
        # authority of the site review made before the first Native tick.
        _, final_packet_raw, final_source_raw = read(site_path, case_id)
        if final_packet_raw != packet_raw or final_source_raw != source_raw:
            raise ValueError("reviewed original site bytes changed during capture")
        frame_bytes = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows).encode()
        frame_sha = _write_once(root / "channels/reverse-body-crosswalk.jsonl", frame_bytes)
        _write_once(root / "video_frames.jsonl",
                    "".join(json.dumps(row, sort_keys=True) + "\n" for row in mapping).encode())
        _write_once(root / "original-site-packet.json", packet_raw)
        _write_once(root / "original-site-source.json", source_raw)
        context = {"source_id": measured["source_id"], "map_packet": packet,
                   "vehicle_actor_id": int(ego.id), "frames_sha256": frame_sha,
                   "original_site_packet_sha256": _sha(packet_raw),
                   "original_site_source_sha256": _sha(source_raw)}
        _write_once(root / "reviewed-crosswalk-source.json",
                    (json.dumps(context, indent=2, sort_keys=True) + "\n").encode())
        return {"case_id": case_id, "frame_count": frames,
                "native_first_frame": first_native,
                "native_last_frame": first_native + frames - 1,
                "source_hashes": {"site_packet": _sha(packet_raw),
                                  "site_source": _sha(source_raw),
                                  "reverse_frames": frame_sha},
                "camera_frames_per_view": {view: len(cameras[view]) for view in VIEWS},
                "physical_relation_status": "unreviewed",
                "legal_judgment": "unresolved"}
    finally:
        built["cleanup"]()
