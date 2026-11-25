"""Source-gated Native acquisition for the fixed C111329 crossing cases.

This module is imported only after a local CARLA operator explicitly launches
the selected case. It never treats a CPU fixture as a Native observation.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from carla_readback import CameraFrames, device_reader
from delivery_audit import CASES
from native_observation import CAMERAS, CAMERA_DIMENSIONS
from owned_capture import capture_owned
from reviewed_site import load_reviewed_site
from video_sources import encode_original_cameras


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read_review_document(review_path, name):
    review = json.loads(Path(review_path).read_text())
    ref = review["sources"][name]
    path = Path(ref["path"])
    if not path.is_absolute():
        path = Path(review_path).parent / path
    if not path.is_file() or _sha(path) != ref["sha256"]:
        raise ValueError("review source changed before Native launch: " + name)
    return json.loads(path.read_text())


def _device_actors(world, packet, inventory):
    """Join actual generated traffic lights by source pose and type."""
    rows = inventory.get("devices")
    if not isinstance(rows, list) or {row.get("device_id") for row in rows} != \
       {device["device_id"] for device in packet["devices"]}:
        raise ValueError("reviewed Native device inventory incomplete")
    actors = list(world.get_actors().filter("traffic.traffic_light*"))
    bound = {}
    for row in rows:
        pose = row.get("location_xyz_m")
        type_id = row.get("type_id")
        if not isinstance(pose, list) or len(pose) != 3 or \
           not isinstance(type_id, str) or not type_id.startswith("traffic.traffic_light"):
            raise ValueError("reviewed Native device pose or type missing")
        matches = []
        for actor in actors:
            p = actor.get_location()
            if actor.type_id == type_id and sum((float(a)-float(b))**2 for a,b in
                    zip((p.x,p.y,p.z), pose)) <= 0.25:
                matches.append(actor)
        if len(matches) != 1:
            raise ValueError("one original Native actor required for device " + row["device_id"])
        bound[row["device_id"]] = matches[0]
    if len({actor.id for actor in bound.values()}) != len(bound):
        raise ValueError("device inventory reused a Native actor")
    return bound


def _camera_sensors(world, carla, placement, bridge):
    rows = placement.get("cameras")
    if not isinstance(rows, dict) or set(rows) != set(CAMERAS):
        raise ValueError("four reviewed original camera placements required")
    sensors = {}
    try:
        for name in CAMERAS:
            row = rows[name]
            xyz = row.get("location_xyz_m")
            pyr = row.get("pitch_yaw_roll_deg")
            if not isinstance(xyz, list) or len(xyz) != 3 or \
               not isinstance(pyr, list) or len(pyr) != 3:
                raise ValueError("reviewed camera pose missing: " + name)
            width, height = CAMERA_DIMENSIONS[name]
            bp = world.get_blueprint_library().find("sensor.camera.rgb")
            bp.set_attribute("image_size_x", str(width))
            bp.set_attribute("image_size_y", str(height))
            bp.set_attribute("sensor_tick", "0.05")
            transform = carla.Transform(carla.Location(x=float(xyz[0]),
                y=float(xyz[1]), z=float(xyz[2])),
                carla.Rotation(pitch=float(pyr[0]), yaw=float(pyr[1]), roll=float(pyr[2])))
            sensor = world.try_spawn_actor(bp, transform)
            if sensor is None or sensor.type_id != "sensor.camera.rgb":
                raise RuntimeError("original camera spawn failed: " + name)
            sensors[name] = sensor
            sensor.listen(bridge.callback(name))
        return sensors
    except BaseException:
        _release_sensors(sensors)
        raise


def _release_sensors(sensors):
    for sensor in sensors.values():
        try:
            sensor.stop()
        finally:
            sensor.destroy()


def run_native(review_path, case_id, output_dir, *, host="127.0.0.1", port=2000,
               controller_speed_mps=1.2):
    """Acquire 900 original ticks, restore the prior world, and seal sources."""
    if case_id not in CASES:
        raise ValueError("unknown exact crossing case")
    output = Path(output_dir).resolve()
    if not output.is_dir() or any((output / name).exists() for name in
            ("original-site-observation.json", "trace.jsonl", "capture", "native-seal.json")):
        raise ValueError("fresh materialized Native attempt required")
    reviewed = load_reviewed_site(review_path, expected_case_id=case_id)
    if type(controller_speed_mps) not in (int, float) or not 0 < controller_speed_mps <= 3:
        raise ValueError("positive reviewed pedestrian control speed required")
    packet = dict(reviewed["packet"])
    packet["walker_speed_mps"] = float(controller_speed_mps)
    (output / "effective-site-packet.json").write_text(
        json.dumps(packet, sort_keys=True, indent=2) + "\n")
    inventory = _read_review_document(review_path, "device_inventory")
    placement = _read_review_document(review_path, "camera_placement")
    operation = _read_review_document(review_path, "device_operation")
    if operation.get("health_method") != "carla_is_frozen_readback" or \
       not isinstance(operation.get("inactive_device_id"), (str, type(None))):
        raise ValueError("reviewed original device operation method missing")
    expected_inactive = None if CASES[case_id][1] else packet["devices"][1]["device_id"]
    if operation["inactive_device_id"] != expected_inactive:
        raise ValueError("reviewed device operation differs from exact case")
    road_ref = json.loads(Path(review_path).read_text())["sources"]["opendrive"]
    road = Path(road_ref["path"])
    if not road.is_absolute():
        road = Path(review_path).parent / road
    if _sha(road) != road_ref["sha256"]:
        raise ValueError("reviewed OpenDRIVE changed before Native launch")
    # Runtime imports are delayed until after the output root is made explicit.
    if "SCENARIO_PIPELINE_OUTPUT_ROOT" not in os.environ:
        os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(output.parent / "pipeline-output")
    import carla
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot as snapshot_world, restore
    from walker_pipeline_capture import WalkerPipelineCapture

    client = carla.Client(host, int(port))
    client.set_timeout(30)
    before = snapshot_world(client)
    sensors = {}
    graph = frame_map = None
    restored = False
    failure = None
    receipt = None
    try:
        world = client.generate_opendrive_world(road.read_text())
        if len(world.get_map().get_topology()) < 2:
            raise ValueError("Native map topology lacks between-intersection route")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        settings.no_rendering_mode = False
        world.apply_settings(settings)
        devices = _device_actors(world, packet, inventory)
        if expected_inactive:
            devices[expected_inactive].freeze(True)
        if any(bool(actor.is_frozen()) != (device_id == expected_inactive)
               for device_id, actor in devices.items()):
            raise ValueError("original device operation readback differs")
        bridge = CameraFrames()
        sensors = _camera_sensors(world, carla, placement, bridge)
        read_device = device_reader(packet, devices,
            lambda device_id, actor: not bool(actor.is_frozen()))

        def on_spawn(walker):
            nonlocal graph, frame_map
            graph = WalkerPipelineCapture(client, walker, output, case_id)
            frame_map = FrameMap(output / "video_frames.jsonl")

            def after_tick(frame, time_s, observation):
                sampled = graph.capture(frame, time_s, {"frame": frame,
                    "time_s": time_s, "actor_id": walker.id})
                if sampled["frame"] != frame or abs(sampled["time_s"]-time_s) > 1e-6 or \
                   any(abs(a-b) > 1e-4 for a,b in zip(sampled["position_m"],
                                                       observation["walker_xyz_m"])):
                    raise ValueError("original graph and site observation frame join differs")
                frame_map.append(frame, time_s)
            return after_tick

        receipt = capture_owned(world, packet, case_id,
            output / "original-site-observation.json", read_device,
            bridge.readers(), carla_module=carla, ticks=900, on_spawn=on_spawn)
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
            _release_sensors(sensors)
        except BaseException as error:
            failure = failure or error
        try:
            restored = bool(restore(client, before).get("restored"))
        except BaseException as error:
            failure = failure or error
    if failure is not None or not restored or receipt is None:
        (output / "native-run-status.json").write_text(json.dumps({
            "phase": "failed", "errors": [repr(failure) if failure else "restoration not verified"],
            "restored": restored}, sort_keys=True, indent=2) + "\n")
        raise RuntimeError("original Native acquisition or restoration failed") from failure
    try:
        videos = encode_original_cameras(output / "original-site-observation.json")
    except BaseException as error:
        (output / "native-run-status.json").write_text(json.dumps({
            "phase": "failed", "errors": [repr(error)], "restored": True,
            "stage": "original camera encoding"}, sort_keys=True, indent=2) + "\n")
        raise
    seal = {"case_id": case_id, "observation_sha256": receipt["sha256"],
            "frame_count": receipt["frame_count"], "restored": True, "errors": [],
            "review_sha256": reviewed["review_sha256"],
            "source_sha256": reviewed["source_sha256"],
            "effective_site_packet_sha256": _sha(output / "effective-site-packet.json"),
            "trace_sha256": _sha(output / "trace.jsonl"),
            "video_frame_map_sha256": _sha(output / "video_frames.jsonl"),
            "video_sources_sha256": {name: row["sha256"] for name, row in videos.items()}}
    seal_path = output / "native-seal.json"
    seal_path.write_text(json.dumps(seal, sort_keys=True, indent=2) + "\n")
    provenance = {"kind": "original_native", "case_id": case_id,
            "observation_sha256": receipt["sha256"], "diagnostic_fixture": False,
            "seal_path": str(seal_path), "seal_sha256": _sha(seal_path),
            "original_observation": receipt, "physical_acceptance": False}
    (output / "native-provenance.json").write_text(
        json.dumps(provenance, sort_keys=True, indent=2) + "\n")
    (output / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "native", "diagnostic_fixture": False,
        "case_id": case_id, "review_sha256": reviewed["review_sha256"]},
        sort_keys=True, indent=2) + "\n")
    from worker_exchange.native_output import seal_capture
    seal_capture(output, frames=receipt["frame_count"],
        restoration={"restored": True}, errors=[],
        encoder_exit_codes={name: 0 for name in CAMERAS},
        context={"case_id": case_id, "review_sha256": reviewed["review_sha256"],
                 "legal_verdict_claimed": False})
    return provenance
