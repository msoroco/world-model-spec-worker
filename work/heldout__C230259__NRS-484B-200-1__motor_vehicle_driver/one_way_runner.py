"""CARLA-lazy posted one-way left-half capture and original sign readback."""

import argparse
import json
from math import hypot
from pathlib import Path

from right_half_cameras import CAMERAS, LosslessSourceSink, RightHalfCameraCapture
from right_half_route import control_step
from right_half_one_way import (OneWayRoadRecorder, same_direction_left,
                                select_one_way_route, one_way_targets,
                                spawn_one_way_sign)
from right_half_measurement import EXCEPTIONS

PREFIX = "heldout__C230259__NRS-484B-200-1__motor_vehicle_driver__"


def check_config(config):
    case = config.get("selected_case_id")
    if case != PREFIX + "one_way_left":
        raise ValueError("C230259 one-way runner supports only exact one-way-left case")
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "NRS-484B-200-1", "C230259", "motor_vehicle_driver"):
        raise ValueError("C230259 one-way identity differs")
    if (config.get("rate_hz"), config.get("frames"), config.get("duration_s")) != (20, 80, 4):
        raise ValueError("C230259 one-way case requires 80 original frames at 20 Hz")
    if config.get("case", {}).get("case_id") != case:
        raise ValueError("C230259 recording description selects another case")
    cameras = config.get("cameras", [])
    if [item.get("name") for item in cameras] != list(CAMERAS):
        raise ValueError("Four named C230259 source cameras required")
    for item in cameras:
        profile = CAMERAS[item["name"]]
        if (item.get("width"), item.get("height"), item.get("fov_deg")) != (
                *profile[2], profile[3]):
            raise ValueError("C230259 source camera profile differs")
    if not isinstance(config["case"].get("recording_description"), dict):
        raise ValueError("Missing exact right-half recording description")
    return "left"


def run(output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture

    output = Path(output_dir)
    config = json.loads((output / "config.json").read_text())
    side = check_config(config)
    client = carla.Client(host, port)
    client.set_timeout(30.)
    world = client.get_world()
    original_settings = world.get_settings()
    actors, sinks, frames = [], {}, []
    cameras = pipeline = recorder = frame_map = None
    complete = False
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        route = select_one_way_route(world.get_map())
        targets = one_way_targets(route)
        sign = spawn_one_way_sign(world, carla, route[0])
        actors.append(sign)
        blueprint = world.get_blueprint_library().find("vehicle.tesla.model3")
        point = same_direction_left(route[0]).transform.location
        base = route[0].transform
        ego_transform = carla.Transform(
            carla.Location(x=point.x, y=point.y, z=base.location.z), base.rotation)
        ego = world.try_spawn_actor(blueprint, ego_transform)
        if ego is None:
            raise ValueError("C230259 one-way ego spawn failed")
        actors.append(ego)
        lead = world.try_spawn_actor(blueprint, route[8].transform)
        if lead is None:
            raise ValueError("C230259 same-direction lead spawn failed")
        actors.append(lead)
        for name in CAMERAS:
            sinks[name] = LosslessSourceSink(output, name)
        cameras = RightHalfCameraCapture(world, carla, ego, sinks)
        pipeline = PipelineCapture(client, ego, output, config["selected_case_id"],
                                   required_observations=config.get("required_atoms", []))
        recorder = OneWayRoadRecorder(output, sign)
        frame_map = FrameMap(output / "video_frames.jsonl")
        context_path = output / "road_exception_context.json"
        if context_path.exists():
            raise ValueError("Retain prior right-half exception context")
        context = {key: {"value": None, "source_ref": None} for key in EXCEPTIONS}
        context["road_exception_context"] = {"source": "original Native road and controls",
                                             "review_status": "undecided"}
        context["one_way_setup"] = {
            "lane_ids": [route[0].lane_id, same_direction_left(route[0]).lane_id],
            "sign_actor_id": sign.id, "official_designation": "undecided",
            "posting_authority": "undecided", "subject_path": "left_half"}
        context_path.write_text(json.dumps(context) + "\n")
        target_index = 1
        start_time = None
        for _ in range(config["frames"]):
            transform = ego.get_transform()
            position = transform.location
            target = targets["targets_xy_m"]
            while (target_index < len(target) - 1 and
                   hypot(position.x - target[target_index][0],
                         position.y - target[target_index][1]) < 1.5):
                target_index += 1
            forward = transform.get_forward_vector()
            velocity = ego.get_velocity()
            command = control_step((position.x, position.y), (forward.x, forward.y),
                                   (velocity.x, velocity.y), target[target_index])
            ego.apply_control(carla.VehicleControl(**command))
            lead.apply_control(carla.VehicleControl(throttle=.18))
            frame = world.tick()
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError("C230259 Native snapshot frame differs")
            if start_time is None:
                start_time = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds - start_time
            cameras.wait_for_frame(frame)
            pipeline.capture(frame, time_s)
            # Hold the selected right-lane reference route while the subject
            # drives the adjacent same-direction left lane.
            current = ego.get_transform().location
            reference = min(route, key=lambda item: hypot(
                item.transform.location.x-current.x,
                item.transform.location.y-current.y))
            recorder.append(ego, reference, frame, time_s)
            frame_map.append(frame, time_s)
            frames.append(frame)
        cameras.verify(frames)
        complete = True
    finally:
        if frame_map is not None:
            frame_map.close()
        if recorder is not None:
            recorder.close()
        if pipeline is not None:
            pipeline.close(confirmed=complete)
        if cameras is not None:
            cameras.close()
        for sink in sinks.values():
            sink.close()
        for actor in reversed(actors):
            actor.destroy()
        world.apply_settings(original_settings)
        restored = (world.get_settings().synchronous_mode == original_settings.synchronous_mode and
                    world.get_settings().fixed_delta_seconds == original_settings.fixed_delta_seconds)
        if not restored:
            raise ValueError("C230259 Native world restoration differs")
    if not complete or len(frames) != config["frames"]:
        raise ValueError("C230259 one-way capture incomplete")
    (output / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "native", "diagnostic_fixture": False,
        "original_frames": len(frames)}) + "\n")
    seal_capture(output, frames=len(frames), restoration={"restored": True}, errors=[],
                 encoder_exit_codes={name: 0 for name in CAMERAS},
                 context={"native_map_name": world.get_map().name,
                          "road_id": route[0].road_id,
                          "reference_lane_id": route[0].lane_id,
                          "subject_body_side_request": side,
                          "lead_actor_id": lead.id,
                          "one_way_sign_actor_id": sign.id,
                          "one_way_designation_verified": False})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        check_config(json.loads((Path(args.output_dir or ".") / "config.json").read_text()))
    else:
        if not args.output_dir:
            parser.error("--output-dir required for Native capture")
        run(args.output_dir, args.host, args.port)
