"""Native overtaken-driver acquisition prototype; no legal outcome is inferred.

The CARLA dependency is loaded only by ``run``.  Source cameras and actor
readbacks are retained for independent review; a scripted notice is recorded
as a construction stimulus, never as proof that the driver heard or saw it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

from overtaken_controller import CASES, apply as apply_subject, target as subject_target
from right_pass_survey import collect as collect_right_pass_survey


PREFIX = "heldout__C179789__NRS-484B-207-2__motor_vehicle_driver__"


def write_native_capture_receipt(output, case_id, events, *, observed):
    """Attest only a successful, closed acquisition from retained source bytes."""
    expected = ["capture_finished", "encoders_closed", "restoration_verified",
                "native_exit", "owner_released"]
    if events != expected:
        raise ValueError("Native capture lifecycle incomplete or out of order")
    output = Path(output)
    names = ["overtaken_source.jsonl", "video_frames.jsonl", "trace.jsonl"]
    if not observed:
        names += ["signal_command_original.jsonl", "signal_audio_envelope_original.jsonl"]
    sources = {}
    for name in names:
        path = output / name
        if not path.is_file() or not path.stat().st_size:
            raise ValueError("Native capture source missing: " + name)
        sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    path = output / "native-capture-receipt.json"
    with path.open("x") as stream:
        json.dump({"case_id": case_id, "actual_native_capture": True,
                   "source_sha256": sources, "events": events}, stream,
                  indent=2, allow_nan=False)
        stream.write("\n")
    return path


def observe_native_process_exit(output, case_id, returncode):
    """Called by the launcher only after its Native child has terminated."""
    output = Path(output)
    if returncode != 0:
        raise ValueError("Native child did not exit successfully")
    if (output / ".native-owner-lock").exists():
        raise ValueError("Native owner lock remains held")
    receipt_path = output / "native-capture-receipt.json"
    if not receipt_path.is_file():
        raise ValueError("Native child capture receipt missing")
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("case_id") != case_id or receipt.get("actual_native_capture") is not True or receipt.get("events") != [
        "capture_finished", "encoders_closed", "restoration_verified", "native_exit", "owner_released"
    ]:
        raise ValueError("Native child capture receipt differs")
    for name, digest in receipt.get("source_sha256", {}).items():
        source = output / name
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            raise ValueError("Native child source changed: " + name)
    if not receipt.get("source_sha256"):
        raise ValueError("Native child source inventory missing")
    path = output / "native-process-exit.json"
    with path.open("x") as stream:
        json.dump({"case_id": case_id, "event": "native_process_exit_observed",
                   "native_exit_code": returncode, "owner_lock_released": True,
                   "native_capture_receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest()},
                  stream, indent=2, allow_nan=False)
        stream.write("\n")
    return path


def launch(plan_path, case_id, output, host, port):
    """Parent observes process exit before it attests the child's capture."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(Path(__file__).resolve()), "--plan", str(Path(plan_path).resolve()),
               "--case-id", case_id, "--run", "--output-dir", str(output.resolve()),
               "--host", host, "--port", str(port)]
    completed = subprocess.run(command, check=False)
    return observe_native_process_exit(output, case_id, completed.returncode)


def check_plan(plan, case_id):
    if (plan.get("law_id"), plan.get("cell_id"), plan.get("actor")) != (
        "NRS-484B-207-2", "C179789", "motor_vehicle_driver"
    ):
        raise ValueError("Overtaken-driver frozen identity differs")
    cases = {case["case_id"]: case for case in plan.get("cases", [])}
    if case_id not in cases or not case_id.startswith(PREFIX):
        raise ValueError("Unselected overtaken-driver case")
    suffix = case_id[len(PREFIX):]
    if suffix not in CASES or cases[case_id].get("branch") != suffix:
        raise ValueError("Overtaken-driver controller binding differs")
    camera = plan.get("camera_plan", {})
    if camera.get("duration_s") != 8 or {c.get("view") for c in camera.get("coverage", [])} != {
        "overview", "approach", "reference_corner", "driver_reference"
    }:
        raise ValueError("Four-source camera plan differs")
    return suffix


def readback(subject, overtaker, waypoint, frame, time_s, *, notice_stimulus,
             visibility_relation=None):
    """Get finite original actor state; pass completion uses body corners."""
    from math import atan2

    def corners(actor):
        vertices = list(actor.bounding_box.get_world_vertices(actor.get_transform()))
        if len(vertices) != 8:
            raise ValueError("Native body vertices missing")
        lower = sorted(vertices, key=lambda v: v.z)[:4]
        cx = sum(v.x for v in lower) / 4
        cy = sum(v.y for v in lower) / 4
        lower.sort(key=lambda v: atan2(v.y-cy, v.x-cx))
        return [[float(v.x), float(v.y)] for v in lower]

    tangent = waypoint.transform.get_forward_vector()
    tx, ty = float(tangent.x), float(tangent.y)
    norm = math.hypot(tx, ty)
    if norm < 0.99 or norm > 1.01:
        raise ValueError("Native road tangent invalid")
    subject_corners, overtaker_corners = corners(subject), corners(overtaker)
    subject_long = [tx*x + ty*y for x, y in subject_corners]
    overtaker_long = [tx*x + ty*y for x, y in overtaker_corners]
    sx, sy = subject.get_transform().location.x, subject.get_transform().location.y
    wx, wy = waypoint.transform.location.x, waypoint.transform.location.y
    velocity = subject.get_velocity()
    speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
    offset = (sx-wx)*ty - (sy-wy)*tx
    values = [speed, offset, float(sx), float(sy), float(wx), float(wy), float(frame), float(time_s),
              *[q for pair in subject_corners+overtaker_corners for q in pair]]
    if not all(math.isfinite(v) for v in values):
        raise ValueError("Native actor readback nonfinite")
    if visibility_relation is not None and (
        visibility_relation.get("a") != subject.id or
        visibility_relation.get("b") != overtaker.id or
        type(visibility_relation.get("visible")) is not bool
    ):
        raise ValueError("Original visibility relation identities differ")
    return {
        "frame": frame, "time_s": time_s, "subject_id": str(subject.id),
        "overtaker_id": str(overtaker.id), "subject_corners": subject_corners,
        "overtaker_corners": overtaker_corners, "road_tangent_xy": [tx, ty],
        "road_waypoint_xy": [float(wx), float(wy)],
        "subject_pose_xy": [float(sx), float(sy)],
        "subject_speed_mps": speed, "subject_right_offset_m": offset,
        "body_pass_complete": min(overtaker_long) > max(subject_long),
        "notice_stimulus": notice_stimulus,
        "notice_observed": None if visibility_relation is None else visibility_relation["visible"],
        "visibility_relation": visibility_relation,
        "right_pass_permission_verified": None,
    }


def generated_signal_rows(overtaker_id, frame, time_s, requested):
    """Retain a commanded signal and its generated envelope, not hearing proof."""
    if type(frame) is not int or type(requested) is not bool or not math.isfinite(time_s):
        raise ValueError("Original signal frame or command invalid")
    common = {"frame": frame, "time_s": time_s,
              "overtaker_actor_id": str(overtaker_id)}
    return ({**common, "horn_command_requested": requested,
             "source_kind": "scenario_signal_command"},
            {**common, "generated_rms": 0.6 if requested else 0.0,
             "source_kind": "generated_signal_envelope",
             "acoustic_propagation_confirmed": None,
             "subjective_hearing_confirmed": None})


def write_right_pass_survey(output, map_name, waypoint, frame, time_s, vehicle_ids):
    """Retain original roadway facts, leaving permission for separate review."""
    path = Path(output) / "right_pass_road_survey.json"
    survey = collect_right_pass_survey(map_name, waypoint, frame, time_s, vehicle_ids)
    with path.open("x") as stream:
        json.dump(survey, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return path


def run(plan, case_id, output, host="127.0.0.1", port=2000):
    """Acquire four original streams and frame-joined actor readbacks."""
    suffix = check_plan(plan, case_id)
    import carla
    from pipeline_capture import PipelineCapture
    from original_observations import visible_relation
    from worker_exchange.native_output import FrameMap
    from overtake_camera import CAMERAS, LosslessSourceSink, OvertakeCameraCapture
    from overtake_route import select_overtake_route, steer_speed_control

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    source_path = output / "overtaken_source.jsonl"
    if source_path.exists() or (output / "trace.jsonl").exists():
        raise ValueError("Retain prior Native acquisition")
    client = carla.Client(host, port)
    client.set_timeout(30.)
    world = client.get_world()
    original = world.get_settings()
    actors, sinks = [], {}
    pipeline = frame_map = cameras = source = signal_commands = signal_envelope = None
    events = []
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        route = select_overtake_route(world.get_map())
        right_pass = suffix == "right_pass_permitted_no_right_yield"
        subject_lane = route["left" if right_pass else "right"]
        overtaker_lane = route["right" if right_pass else "left"]
        blueprint = world.get_blueprint_library().find("vehicle.tesla.model3")
        subject = world.try_spawn_actor(blueprint, subject_lane[8].transform)
        if subject is None:
            raise ValueError("Native overtaken subject spawn failed")
        actors.append(subject)
        overtaker = world.try_spawn_actor(blueprint, overtaker_lane[0].transform)
        if overtaker is None:
            raise ValueError("Native overtaker spawn failed")
        actors.append(overtaker)
        for name in CAMERAS:
            sinks[name] = LosslessSourceSink(output, name)
        cameras = OvertakeCameraCapture(world, carla, subject, sinks)
        pipeline = PipelineCapture(client, subject, output, case_id,
                                   required_observations=[row["term"] for row in plan.get("observations", [])])
        frame_map = FrameMap(output / "video_frames.jsonl")
        source = source_path.open("x")
        observed_case = suffix == "observed_gives_way_holds_speed"
        if not observed_case:
            signal_commands = (output / "signal_command_original.jsonl").open("x")
            signal_envelope = (output / "signal_audio_envelope_original.jsonl").open("x")
        frames = []
        start = None
        for index in range(160):
            notice_stimulus = index >= 24 and not observed_case
            transform = subject.get_transform()
            location = transform.location
            waypoint = world.get_map().get_waypoint(location)
            if waypoint is None or waypoint.is_junction:
                raise ValueError("Native subject road waypoint unavailable")
            previous_visibility = visible_relation(world, subject, overtaker) if observed_case else None
            previous = readback(subject, overtaker, waypoint, index, index*.05,
                                notice_stimulus=notice_stimulus,
                                visibility_relation=previous_visibility)
            active_notice = previous["notice_observed"] if observed_case else notice_stimulus
            notice_kind = CASES[suffix][0] if active_notice else None
            plan_target = subject_target(
                suffix, notice_kind=notice_kind,
                notice_source=("original subject-to-overtaker collision rays" if observed_case
                               else "original generated signal command") if active_notice else None,
                pass_complete=previous["body_pass_complete"])
            apply_subject(subject, carla.VehicleControl, plan_target,
                          right_offset_m=previous["subject_right_offset_m"],
                          speed_mps=previous["subject_speed_mps"])
            destination = overtaker_lane[min(8 + index // 4, len(overtaker_lane)-1)].transform.location
            other_transform = overtaker.get_transform()
            other_location = other_transform.location
            heading = other_transform.get_forward_vector()
            velocity = overtaker.get_velocity()
            controls = steer_speed_control([other_location.x, other_location.y],
                                           [heading.x, heading.y], [velocity.x, velocity.y],
                                           [destination.x, destination.y], target_speed_mps=8)
            overtaker.apply_control(carla.VehicleControl(**controls))
            frame = world.tick()
            cameras.wait_for_frame(frame)
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError("Native frame/snapshot mismatch")
            if start is None:
                start = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds-start
            trace = pipeline.capture(frame, time_s)
            if trace.get("frame") != frame or trace.get("time_s") != time_s:
                raise ValueError("Native trace/frame mismatch")
            row = readback(subject, overtaker, waypoint, frame, time_s,
                           notice_stimulus=notice_stimulus,
                           visibility_relation=visible_relation(world, subject, overtaker)
                           if observed_case else None)
            if right_pass and index == 0:
                current_waypoint = world.get_map().get_waypoint(subject.get_transform().location)
                if current_waypoint is None:
                    raise ValueError("Original right-pass road waypoint unavailable")
                vehicle_ids = sorted(actor.id for actor in world.get_actors().filter("vehicle.*"))
                if subject.id not in vehicle_ids or overtaker.id not in vehicle_ids:
                    raise ValueError("Right-pass participant inventory incomplete")
                write_right_pass_survey(output, world.get_map().name, current_waypoint,
                                        frame, time_s, vehicle_ids)
            source.write(json.dumps(row, allow_nan=False)+"\n")
            source.flush()
            if signal_commands is not None:
                command_row, envelope_row = generated_signal_rows(
                    overtaker.id, frame, time_s, notice_stimulus)
                signal_commands.write(json.dumps(command_row, allow_nan=False)+"\n")
                signal_envelope.write(json.dumps(envelope_row, allow_nan=False)+"\n")
                signal_commands.flush()
                signal_envelope.flush()
            frame_map.append(frame, time_s)
            frames.append(frame)
        cameras.verify(frames)
        events.append("capture_finished")
        (output / "construction-observation.json").write_text(json.dumps({
            "case_id": case_id, "frames": frames,
            "notice_observed": None, "right_pass_permission_verified": None,
            "delivery_ready": False}, indent=2)+"\n")
    finally:
        if signal_commands is not None:
            signal_commands.close()
        if signal_envelope is not None:
            signal_envelope.close()
        if source is not None:
            source.close()
        if frame_map is not None:
            frame_map.close()
        if pipeline is not None:
            pipeline.close(confirmed=False)
        if cameras is not None:
            cameras.close()
        for sink in sinks.values():
            sink.close()
        if events == ["capture_finished"]:
            events.append("encoders_closed")
        for actor in reversed(actors):
            actor.destroy()
        world.apply_settings(original)
        restored = world.get_settings()
        if (restored.synchronous_mode != original.synchronous_mode or
                restored.fixed_delta_seconds != original.fixed_delta_seconds):
            raise ValueError("Native world settings restore failed")
        if events == ["capture_finished", "encoders_closed"]:
            events.append("restoration_verified")
    return events


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", default="case-plan.json")
    parser.add_argument("--case-id")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--launch", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    plan = json.loads(Path(args.plan).read_text())
    config_path = Path(args.config)
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    case_id = args.case_id or config.get("selected_case_id")
    check_plan(plan, case_id)
    if args.launch:
        if not args.output_dir:
            raise ValueError("Native output directory required")
        launch(args.plan, case_id, args.output_dir, args.host, args.port)
        return
    if args.run or not args.check:
        if not args.output_dir:
            raise ValueError("Native output directory required")
        output = Path(args.output_dir)
        output.mkdir(parents=True, exist_ok=True)
        owner = output / ".native-owner-lock"
        with owner.open("x") as stream:
            stream.write(case_id + "\n")
        try:
            events = run(plan, case_id, output, args.host, args.port)
            events.append("native_exit")
        finally:
            owner.unlink()
        events.append("owner_released")
        write_native_capture_receipt(output, case_id, events,
                                     observed=case_id.endswith("__observed_gives_way_holds_speed"))


if __name__ == "__main__":
    main()
