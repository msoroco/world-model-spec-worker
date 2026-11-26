"""Acquire a reviewed yield approach; never infer legal or physical acceptance."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

from carla_yield_readback import CameraFrames, body_vertices
from capture_yield import capture
from yield_source import CAMERAS, DIMENSIONS, sha
from yield_video_sources import encode_original_cameras


def _transform(carla, row):
    return carla.Transform(carla.Location(x=float(row["x"]), y=float(row["y"]),
                                         z=float(row.get("z", 0))),
                           carla.Rotation(yaw=float(row.get("yaw", 0))))


def _release(actors):
    for actor in actors.values():
        try:
            if hasattr(actor, "stop"):
                actor.stop()
        finally:
            actor.destroy()


class YieldControl:
    """Bounded waypoint control with a source-selected stopping target."""

    def __init__(self, site, case_id, vehicle_control, *, throttle=.3):
        if not 0 < throttle <= .5:
            raise ValueError("bounded engineering throttle required")
        self.route = site["ego_route"]
        self.factory = vehicle_control
        self.throttle = float(throttle)
        self.index = 1
        self.hold = 0
        self.no_stop = case_id.endswith("no_safety_stop_required")
        if case_id.endswith("fallback_earlier_obscured_stop"):
            self.target = site.get("earlier_obscured_stop_position")
            if not isinstance(self.target, list) or len(self.target) != 2:
                raise ValueError("source-positioned earlier obscured stop required")
        else:
            from yield_site import select_stop_reference
            # The caller stores a byte-identical reviewed site source path.
            self.target = None

    def set_reference(self, reference):
        if self.target is None:
            self.target = reference["reference_position"]

    def __call__(self, actor, tick):
        if type(tick) is not int or tick < 0 or self.target is None:
            raise ValueError("original control target missing")
        pose = actor.get_transform()
        x, y = float(pose.location.x), float(pose.location.y)
        if not all(math.isfinite(v) for v in (x, y)):
            raise ValueError("original ego pose nonfinite")
        if not self.no_stop and math.dist((x, y), self.target) <= 1.5:
            self.hold += 1
            actor.apply_control(self.factory(throttle=0, steer=0, brake=1))
            return
        if self.index >= len(self.route):
            actor.apply_control(self.factory(throttle=0, steer=0, brake=1))
            return
        target = self.route[self.index]
        if math.dist((x, y), (target["x"], target["y"])) < .8:
            self.index += 1
            if self.index >= len(self.route):
                actor.apply_control(self.factory(throttle=0, steer=0, brake=1))
                return
            target = self.route[self.index]
        yaw = math.radians(float(pose.rotation.yaw))
        direction = math.atan2(target["y"] - y, target["x"] - x)
        error = (direction - yaw + math.pi) % (2 * math.pi) - math.pi
        distance = max(.8, math.dist((x, y), (target["x"], target["y"])))
        steer = max(-1., min(1., math.atan(2.7 * 2 * math.sin(error) / distance) / .65))
        actor.apply_control(self.factory(throttle=self.throttle, steer=steer, brake=0))


def _cameras(world, carla, placement, bridge):
    sensors = {}
    try:
        for name in CAMERAS:
            row = placement["cameras"][name]
            xyz, pyr = row["location_xyz_m"], row["pitch_yaw_roll_deg"]
            width, height = DIMENSIONS[name]
            bp = world.get_blueprint_library().find("sensor.camera.rgb")
            for key, value in (("image_size_x", width), ("image_size_y", height), ("sensor_tick", .05)):
                bp.set_attribute(key, str(value))
            pose = carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                carla.Rotation(pitch=pyr[0], yaw=pyr[1], roll=pyr[2]))
            sensor = world.try_spawn_actor(bp, pose)
            if sensor is None or sensor.type_id != "sensor.camera.rgb":
                raise RuntimeError("original yield camera spawn failed: " + name)
            sensors[name] = sensor
            sensor.listen(bridge.callback(name))
        return sensors
    except BaseException:
        _release(sensors)
        raise


def run_native(reviewed, case_id, output_dir, *, host="127.0.0.1", port=2000, throttle=.3):
    output = Path(output_dir).resolve()
    if not output.is_dir() or any((output / name).exists() for name in
            ("original-yield-site.json", "original-yield-trace.jsonl", "original-yield-receipt.json", "native-seal.json")):
        raise ValueError("fresh materialized original Native attempt required")
    if "SCENARIO_PIPELINE_OUTPUT_ROOT" not in os.environ:
        raise ValueError("SCENARIO_PIPELINE_OUTPUT_ROOT required before runtime import")
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot as snapshot_world, restore

    client = carla.Client(host, int(port))
    client.set_timeout(30)
    before = snapshot_world(client)
    sensors, actors = {}, {}
    graph = frame_map = None
    failure = receipt = None
    restored = False
    try:
        site = reviewed["site"]
        world = client.generate_opendrive_world(reviewed["sources"]["opendrive"].read_text())
        if world.get_map().name != site["map_name"] or sha(reviewed["sources"]["opendrive"]) != site["map_sha256"]:
            raise ValueError("live original map differs from reviewed yield source")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.no_rendering_mode = False
        world.apply_settings(settings)
        bp = world.get_blueprint_library().find(site["ego_blueprint"])
        ego = world.try_spawn_actor(bp, _transform(carla, site["ego_spawn"]))
        if ego is None or not ego.type_id.startswith("vehicle."):
            raise RuntimeError("source-selected motor vehicle failed to spawn")
        actors["ego"] = ego
        sign_spec = site["yield_sign_actor_spec"]
        bp = world.get_blueprint_library().find(sign_spec["blueprint"])
        sign = world.try_spawn_actor(bp, _transform(carla, sign_spec["transform"]))
        if sign is None or not sign.is_alive:
            raise RuntimeError("original yield-sign actor failed to spawn")
        actors["yield_sign"] = sign
        for index, spec in enumerate(site.get("occluder_actor_specs", [])):
            bp = world.get_blueprint_library().find(spec["blueprint"])
            occluder = world.try_spawn_actor(bp, _transform(carla, spec["transform"]))
            if occluder is None or not occluder.is_alive:
                raise RuntimeError("original blind-approach occluder failed to spawn")
            vertices = occluder.bounding_box.get_world_vertices(occluder.get_transform())
            actual = [min(vertex.x for vertex in vertices), min(vertex.y for vertex in vertices),
                      max(vertex.x for vertex in vertices), max(vertex.y for vertex in vertices)]
            if any(abs(a - b) > 1 for a, b in zip(actual, spec["expected_rectangle_xy_m"])):
                raise RuntimeError("original occluder physical readback differs from reviewed geometry")
            actors["occluder_" + str(index)] = occluder
        bridge = CameraFrames()
        sensors = _cameras(world, carla, reviewed["placement"], bridge)
        graph = PipelineCapture(client, ego, output, case_id)
        frame_map = FrameMap(output / "video_frames.jsonl")
        source = output / "original-yield-site.json"
        source.write_bytes(reviewed["sources"]["site_packet"].read_bytes())
        control = YieldControl(site, case_id, carla.VehicleControl, throttle=throttle)
        control.set_reference(reviewed["reference"])

        def after_tick(frame, time_s, row):
            sampled = graph.capture(frame, time_s, {"original_yield_source_sha256": sha(source)})
            if sampled["frame"] != frame or abs(sampled["time_s"] - time_s) > 1e-6:
                raise ValueError("original graph and yield vehicle frame join differs")
            frame_map.append(frame, time_s)

        receipt = capture(world, ego, source, sha(source), case_id, output, control,
            body_vertices, lambda actor: actor.apply_control(carla.VehicleControl(brake=1)),
            camera_readers=bridge.readers(), after_tick=after_tick,
            control_readback=lambda frame: {"yield_sign_id": site["yield_sign_id"],
                "control": "yield_sign", "live_actor_id": sign.id,
                "live_actor_type": sign.type_id, "source_frame_id": frame})
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
        for group in (sensors, actors):
            try:
                _release(group)
            except BaseException as error:
                failure = failure or error
        try:
            restored = bool(restore(client, before).get("restored"))
        except BaseException as error:
            failure = failure or error
    if failure is not None or not restored or receipt is None:
        (output / "native-run-status.json").write_text(json.dumps({
            "phase": "failed", "error": repr(failure), "restored": restored}, sort_keys=True) + "\n")
        raise RuntimeError("original yield acquisition or restoration failed") from failure
    videos = encode_original_cameras(receipt["receipt"], receipt["trace"])
    seal_capture(output, frames=900, restoration={"restored": True}, errors=[],
        encoder_exit_codes={name: 0 for name in CAMERAS},
        context={"case_id": case_id, "review_sha256": reviewed["review_sha256"],
                 "legal_verdict_claimed": False})
    seal = {"case_id": case_id, "review_sha256": reviewed["review_sha256"],
            "site_sha256": sha(output / "original-yield-site.json"),
            "trace_sha256": receipt["trace_sha256"], "source_receipt_sha256": receipt["receipt_sha256"],
            "video_sources_sha256": {name: row["sha256"] for name, row in videos.items()},
            "restored": True, "frame_count": 900, "physical_acceptance": False}
    (output / "native-seal.json").write_text(json.dumps(seal, sort_keys=True) + "\n")
    return seal
