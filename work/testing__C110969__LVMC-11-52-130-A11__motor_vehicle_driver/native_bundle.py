"""One-tick Native source writer for C110969 pose, cameras and context.

The caller owns the CARLA world, actor/sensors, reviewed local transform,
resource restoration and physical review. This module is lazy about CARLA.
"""

import hashlib
import json
from pathlib import Path

from intersection_geometry import Box
from native_map import bind
from original_capture import capture_pose
from saved_delivery import CAMERAS


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _binding(path, root):
    path = Path(path)
    return {"path": str(path.relative_to(root)), "sha256": _sha(path)}


def _write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True)
        stream.write("\n")


def _write_rows(path, rows):
    with path.open("x", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True) + "\n")


def capture_bundle(world, ego, output_dir, *, map_packet_path, case_id,
                   attempt_id, recording_id, world_to_local, read_camera,
                   read_context, acquisition_kind="diagnostic_fixture",
                   native_capture=None):
    """Capture exact 45 s at 20 Hz; read_camera(name, world_frame) yields PNG.

    read_context(world_frame) must report original participant/direction sources.
    The receipt preserves source bytes; it does not judge necessity or pixels.
    """
    if not attempt_id or not recording_id:
        raise ValueError("Attempt and recording identity required")
    if acquisition_kind not in ("diagnostic_fixture", "original_native"):
        raise ValueError("Unknown acquisition kind")
    bound = bind(world, map_packet_path, case_id)
    packet = json.loads(Path(map_packet_path).read_text(encoding="utf-8"))
    bounds = packet["intersection_boundary_local_m"]
    boundary = Box(*(float(bounds[k]) for k in ("west", "south", "east", "north")))
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise ValueError("Attempt directory already exists")
    output_dir.mkdir(parents=True)
    source_copy = output_dir / "map-source.json"
    source_copy.write_bytes(Path(map_packet_path).read_bytes())
    # Retain the exact loaded OpenDRIVE bytes used by the map binding.  A later
    # converter must never reconstruct road geometry from a packet hash alone.
    road_path = output_dir / "road.xodr"
    road_path.write_bytes(world.get_map().to_opendrive().encode("utf-8"))
    if _sha(road_path) != bound["opendrive_sha256"]:
        raise ValueError("Loaded OpenDRIVE changed after reviewed map binding")
    map_geometry = output_dir / "map-geometry.json"
    _write_json(map_geometry, {"map_id": packet["map_name"],
                               "geometry_provenance": packet["geometry_provenance"],
                               "opendrive_sha256": bound["opendrive_sha256"],
                               "map_source_sha256": _sha(source_copy),
                               "intersection_boundary_local_m": bounds})
    frame_rows = []
    context_rows = []
    camera_rows = {name: [] for name in CAMERAS}
    for name in CAMERAS:
        (output_dir / "cameras" / name).mkdir(parents=True)

    def observe(frame, world_frame, sample):
        if acquisition_kind == "original_native":
            if native_capture is None:
                raise ValueError("Original Native attempt requires same-tick PipelineCapture")
            captured = native_capture.capture(world_frame, sample["time_s"])
            if captured["frame"] != world_frame or abs(captured["time_s"] - sample["time_s"]) > 1e-9:
                raise ValueError("Native graph and original pose frame join differs")
        frame_rows.append({"frame": frame, "world_frame": world_frame,
                           "time_s": sample["time_s"]})
        context = read_context(world_frame)
        if not isinstance(context, dict) or context.get("world_frame") != world_frame or \
                not isinstance(context.get("participants"), list) or \
                not isinstance(context.get("directions"), dict):
            raise ValueError("Original context callback missing source fields")
        context_rows.append({"frame": frame, **context})
        for name in CAMERAS:
            image_frame, image_bytes = read_camera(name, world_frame)
            if image_frame != world_frame or not isinstance(image_bytes, bytes) or \
                    not image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("Camera frame drift or non-PNG original source: " + name)
            image_path = output_dir / "cameras" / name / f"{frame:06d}.png"
            image_path.write_bytes(image_bytes)
            camera_rows[name].append({
                "frame": frame, "world_frame": world_frame, "camera": name,
                "original_frame_path": str(image_path.relative_to(output_dir)),
                "original_frame_sha256": _sha(image_path)})

    pose_path = output_dir / "pose.jsonl"
    capture_pose(world, ego, pose_path, boundary=boundary,
                 approach=packet["approach"],
                 target_gap_m=bound["requested_gap_ft"] * 0.3048,
                 vehicle_length_m=packet["vehicle_length_m"],
                 world_to_local=world_to_local, frame_observer=observe)
    frame_map = output_dir / "frame-map.jsonl"
    _write_rows(frame_map, frame_rows)
    context_path = output_dir / "context.jsonl"
    _write_rows(context_path, context_rows)
    camera_bindings = {}
    for name in CAMERAS:
        camera_path = output_dir / (name + "-camera.jsonl")
        _write_rows(camera_path, camera_rows[name])
        camera_bindings[name] = _binding(camera_path, output_dir)
    measurement_path = output_dir / "measurement.json"
    _write_json(measurement_path, {
        "actor_id": str(ego.id),
        "vehicle_length_m": packet["vehicle_length_m"],
        "vehicle_width_m": packet["vehicle_width_m"],
        "map_source": _binding(map_geometry, output_dir),
        "pose_source": _binding(pose_path, output_dir)})
    attempt_path = output_dir / "attempt.json"
    _write_json(attempt_path, {
        "case_id": case_id, "attempt_id": attempt_id,
        "recording_id": recording_id, "acquisition_kind": acquisition_kind,
        "requested_front_body_gap_ft": bound["requested_gap_ft"],
        "map_packet": _binding(source_copy, output_dir),
        "road_source": _binding(road_path, output_dir),
        "measurement_packet": _binding(measurement_path, output_dir),
        "frame_map": _binding(frame_map, output_dir),
        "context": _binding(context_path, output_dir),
        "cameras": camera_bindings})
    return {"attempt_path": str(attempt_path), "attempt_sha256": _sha(attempt_path),
            "frame_count": 900, "physical_acceptance_claimed": False}
