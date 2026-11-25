"""Acquire two original vehicles and four cameras with world restoration."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from carla_roundabout_readback import CameraFrames, body_vertices
from capture_roundabout import CAMERAS, CAMERA_DIMENSIONS, capture
from native_roundabout import TimedRoute, spawn
from reviewed_roundabout import load_reviewed
from roundabout_video_sources import encode_original_cameras


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _transform(carla, row):
    return carla.Transform(carla.Location(x=float(row["x"]), y=float(row["y"]),
                                         z=float(row.get("z", 0))),
                           carla.Rotation(yaw=float(row.get("yaw", 0))))


def _cameras(world, carla, placement, bridge):
    sensors = {}
    try:
        for name in CAMERAS:
            row = placement["cameras"][name]
            xyz = row["location_xyz_m"]
            pyr = row["pitch_yaw_roll_deg"]
            width, height = CAMERA_DIMENSIONS[name]
            bp = world.get_blueprint_library().find("sensor.camera.rgb")
            bp.set_attribute("image_size_x", str(width))
            bp.set_attribute("image_size_y", str(height))
            bp.set_attribute("sensor_tick", "0.05")
            pose = carla.Transform(carla.Location(x=float(xyz[0]), y=float(xyz[1]),
                                                 z=float(xyz[2])),
                                   carla.Rotation(pitch=float(pyr[0]), yaw=float(pyr[1]),
                                                  roll=float(pyr[2])))
            sensor = world.try_spawn_actor(bp, pose)
            if sensor is None or sensor.type_id != "sensor.camera.rgb":
                raise RuntimeError("original camera spawn failed: " + name)
            sensors[name] = sensor
            sensor.listen(bridge.callback(name))
        return sensors
    except BaseException:
        _release(sensors)
        raise


def _release(actors):
    for actor in actors.values():
        try:
            if hasattr(actor, "stop"):
                actor.stop()
        finally:
            actor.destroy()


def run_native(review_path, case_id, output_dir, *, host="127.0.0.1", port=2000,
               throttle=.35):
    """Capture one source-checked 45-second attempt; never decide the law."""
    reviewed = load_reviewed(review_path, case_id)
    output = Path(output_dir).resolve()
    if not output.is_dir() or any((output / name).exists() for name in
            ("original-map.json", "original-trace.jsonl", "original-receipt.json",
             "native-seal.json")):
        raise ValueError("fresh materialized Native attempt required")
    if "SCENARIO_PIPELINE_OUTPUT_ROOT" not in os.environ:
        raise ValueError("SCENARIO_PIPELINE_OUTPUT_ROOT required before runtime import")
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot as snapshot_world, restore

    client = carla.Client(host, int(port))
    client.set_timeout(30)
    before = snapshot_world(client)
    sensors = {}
    actors = {}
    graph = frame_map = None
    failure = None
    receipt = None
    restored = False
    try:
        packet = reviewed["packet"]
        road = reviewed["sources"]["opendrive"].read_text()
        world = client.generate_opendrive_world(road)
        if world.get_map().name != packet["map_name"] or (
                _sha(reviewed["sources"]["opendrive"]) != packet["map_sha256"]):
            raise ValueError("live original map differs from reviewed source")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.no_rendering_mode = False
        world.apply_settings(settings)
        ego, opponent = spawn(world, packet, lambda row: _transform(carla, row))
        actors = {"ego": ego, "opponent": opponent}
        bridge = CameraFrames()
        sensors = _cameras(world, carla, reviewed["placement"], bridge)
        graph = PipelineCapture(client, ego, output, case_id)
        frame_map = FrameMap(output / "video_frames.jsonl")
        ego_control = TimedRoute(packet["ego_route"], packet["ego_release_tick"],
                                 carla.VehicleControl, throttle=throttle)
        other_control = TimedRoute(packet["opponent_points"],
                                   packet["opponent_release_tick"],
                                   carla.VehicleControl, throttle=throttle)
        source_packet = output / "original-map.json"
        source_packet.write_bytes(reviewed["sources"]["construction_packet"].read_bytes())
        def after_tick(frame, time_s, row):
            sampled = graph.capture(frame, time_s, {"opponent_actor_id": opponent.id})
            if sampled["frame"] != frame or abs(sampled["time_s"] - time_s) > 1e-6:
                raise ValueError("original graph and vehicle frame join differs")
            frame_map.append(frame, time_s)
        receipt = capture(world, ego, opponent,
            source_packet,
            _sha(reviewed["sources"]["construction_packet"]), case_id,
            output, ego_control, other_control, body_vertices,
            lambda actor: actor.apply_control(carla.VehicleControl(throttle=0,
                steer=0, brake=1)), ticks=900, camera_readers=bridge.readers(),
            after_tick=after_tick)
    except BaseException as error:
        failure = error
    finally:
        for resource in (frame_map, graph):
            if resource is not None:
                try:
                    if resource is graph:
                        resource.close(confirmed=failure is None)
                    else:
                        resource.close()
                except BaseException as error:
                    failure = failure or error
        try:
            _release(sensors)
        except BaseException as error:
            failure = failure or error
        try:
            _release(actors)
        except BaseException as error:
            failure = failure or error
        try:
            restored = bool(restore(client, before).get("restored"))
        except BaseException as error:
            failure = failure or error
    if failure is not None or not restored or receipt is None:
        (output / "native-run-status.json").write_text(json.dumps({
            "phase": "failed", "error": repr(failure), "restored": restored},
            sort_keys=True, indent=2) + "\n")
        raise RuntimeError("original roundabout acquisition or restoration failed") from failure
    videos = encode_original_cameras(receipt["receipt"], receipt["trace"])
    seal = {"case_id": case_id, "review_sha256": reviewed["review_sha256"],
            "map_packet_sha256": _sha(reviewed["sources"]["construction_packet"]),
            "trace_sha256": receipt["trace_sha256"],
            "source_receipt_sha256": receipt["receipt_sha256"],
            "video_sources_sha256": {name: row["sha256"] for name, row in videos.items()},
            "restored": True, "frame_count": 900, "physical_acceptance": False}
    (output / "native-seal.json").write_text(json.dumps(seal, sort_keys=True,
        indent=2) + "\n")
    from worker_exchange.native_output import seal_capture
    seal_capture(output, frames=900, restoration={"restored": True}, errors=[],
        encoder_exit_codes={name: 0 for name in CAMERAS},
        context={"case_id": case_id, "review_sha256": reviewed["review_sha256"],
                 "legal_verdict_claimed": False})
    return seal
