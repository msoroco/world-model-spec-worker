"""Exact C158196 Native entrypoint. --check is CPU-only and never contacts CARLA."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from math import hypot
from pathlib import Path

from native_adapter import NativeAdapter, load_site
from native_controller import IntersectionController
from native_witness import build_case
from original_camera_recorder import OriginalCameraRecorder, PRODUCTION_PROFILE, VIEWS


def case_spec(root):
    config = json.loads((root / "config.json").read_text())
    cases = {item["case_id"]: item for item in json.loads(
        (root / "case-specs.json").read_text())["cases"]}
    selected = config.get("selected_case_id")
    if (selected not in cases or config.get("law_id") != "NRS-484B-257-2" or
            config.get("cell_id") != "C158196" or config.get("actor") != "motor_vehicle_driver" or
            config.get("rate_hz") != 20 or config.get("duration_s") != 45):
        raise ValueError("wrong exact C158196 delivery selection")
    case = cases[selected]
    if (case.get("control_context") not in
            {"stop_sign", "yield_sign", "signal_exception", "officer_exception"} or
            case.get("capture", {}).get("frames") != 900 or
            case["capture"].get("cameras") != list(VIEWS)):
        raise ValueError("exact Native case or four-camera plan differs")
    return config, case


def check(root=None):
    root = Path(root or Path(__file__).parent)
    _, case = case_spec(root)
    return {"case_id": case["case_id"], "offline_case_checked": True,
            "original_site_bundle_required_at_capture": True,
            "physical_acceptance_claimed": False}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def copy_reviewed_site(bundle, output):
    index = json.loads((bundle / "bundle-index.json").read_text())
    for name in ("bundle-index.json", "site.json", "devices.json", "routes.json"):
        source = bundle / name
        destination = output / name
        if not source.is_file() or destination.exists():
            raise ValueError("reviewed original site source absent or conflicts: " + name)
        shutil.copyfile(source, destination)
    return index


def install_cameras(world, ego, carla, site):
    sensors = {}
    try:
        for name in VIEWS:
            pose = site["camera_poses"][name]
            width, height = PRODUCTION_PROFILE[name]
            blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
            blueprint.set_attribute("image_size_x", str(width))
            blueprint.set_attribute("image_size_y", str(height))
            blueprint.set_attribute("fov", str(pose["fov_deg"]))
            transform = carla.Transform(carla.Location(x=pose["x"], y=pose["y"], z=pose["z"]),
                                        carla.Rotation(pitch=pose["pitch"], yaw=pose["yaw"],
                                                       roll=pose["roll"]))
            sensor = world.spawn_actor(blueprint, transform,
                attach_to=ego if name == "driver_reference" else None)
            if sensor is None:
                raise ValueError("original camera spawn failed: " + name)
            sensors[name] = sensor
        return sensors
    except BaseException:
        for sensor in reversed(list(sensors.values())):
            sensor.destroy()
        raise


def _body(actor):
    points = actor.bounding_box.get_world_vertices(actor.get_transform())
    if len(points) < 4:
        raise ValueError("original Native body vertices missing")
    x0, x1 = min(p.x for p in points), max(p.x for p in points)
    y0, y1 = min(p.y for p in points), max(p.y for p in points)
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def _sample(actor, counterpart=False):
    velocity = actor.get_velocity()
    row = {"body_vertices_xy": _body(actor),
           "speed_mps": hypot(velocity.x, velocity.y)}
    if counterpart:
        row["obligated_to_stop_or_yield"] = False
    else:
        control = actor.get_control()
        row["applied_controls"] = {name: getattr(control, name) for name in
                                   ("throttle", "brake", "steer")}
    return row


def run_native(output, host, port):
    # The local operator supplies an original site survey after reviewing the
    # actual Native map and devices. A missing survey fails before server use.
    root = Path(__file__).parent
    config, case = case_spec(root)
    bundle_value = os.environ.get("C158196_ORIGINAL_SITE_BUNDLE")
    if not bundle_value:
        raise ValueError("source-reviewed original C158196 site bundle required")
    bundle = Path(bundle_value).resolve()
    survey = load_site(bundle, case["case_id"], case["control_context"])
    scratch_root = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
    if ".runtime-work" not in scratch_root.parts:
        raise ValueError("camera scratch root must be under .runtime-work")
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import restore, snapshot

    output = Path(output).resolve()
    if not output.is_dir() or output != root:
        raise ValueError("capture must use fresh materialized exact attempt")
    copy_reviewed_site(bundle, output)
    survey = load_site(output, case["case_id"], case["control_context"])
    client = carla.Client(host, int(port))
    client.set_timeout(30)
    saved = snapshot(client)
    world = client.get_world()
    sensors = {}
    recorder = pipeline = frame_map = None
    adapter = NativeAdapter(world, carla, survey, case)
    phase = "initializing"
    failures = []
    restored = False
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        construction = build_case(adapter, case)
        ego = adapter.actors["ego"]
        other = adapter.actors["counterpart"]
        sensors = install_cameras(world, ego, carla, survey["site"])
        scratch = scratch_root / ("c158196-camera-" + output.name)
        scratch.mkdir(parents=True, exist_ok=False)
        recorder = OriginalCameraRecorder(sensors, scratch)
        pipeline = PipelineCapture(client, ego, output, case["case_id"])
        frame_map = FrameMap(output / "video_frames.jsonl")
        authority = world.get_actor(survey["devices"]["ego_control_actor_id"])
        def authority_reader():
            current = world.get_snapshot()
            observed = {"native_frame": current.frame,
                        "control_context": case["control_context"],
                        "ego_control_actor_id": authority.id,
                        "signal_controlling": survey["devices"].get("signal_controlling"),
                        "officer_controlling": survey["devices"].get("officer_controlling")}
            if case["control_context"] == "signal_exception":
                state = authority.get_state()
                observed["signal_state"] = getattr(state, "name", str(state).split(".")[-1]).lower()
                observed["signal_permission"] = observed["signal_state"] == "green"
            if case["control_context"] == "officer_exception":
                observed["officer_actor_visible"] = authority.is_alive
                # This source must be independently reviewed against original
                # pixels. A preauthored schedule alone cannot establish control.
                observed["officer_permission"] = False
            return observed
        def counterpart_reader():
            position = other.get_location()
            return {"native_frame": world.get_snapshot().frame,
                    "x": position.x, "y": position.y, "unobligated": True}
        controller = IntersectionController(counterpart_reader, authority_reader,
                                            config.get("native_throttle_scale", 1.0))
        packet = {"case_id": case["case_id"],
                  "control_context": case["control_context"],
                  "intersection_rectangle_xy": survey["site"]["intersection_rectangle_xy"],
                  "sources": {"native_world": "capture/native_map_facts.json",
                              "native_devices": "devices.json",
                              "native_ego": "trace.jsonl",
                              "native_counterpart": "original-history.json",
                              "camera_sync": "video_frames.jsonl"},
                  "construction_readback": construction, "frames": []}
        phase = "capturing"
        for index in range(900):
            adapter.step(controller)
            world.tick()
            current = world.get_snapshot()
            recorder.read(current)
            time_s = current.timestamp.elapsed_seconds
            pipeline.capture(current.frame, time_s)
            frame_map.append(current.frame, time_s)
            packet["frames"].append({"native_frame": current.frame,
                "camera_frame": index, "time_s": time_s,
                "control_context": case["control_context"],
                "authority": authority_reader(),
                "ego": _sample(ego), "counterpart": _sample(other, counterpart=True)})
        media = recorder.finish(output)
        samples = output / "source-frame-samples"
        samples.mkdir(exist_ok=False)
        sample_refs = {}
        for view in VIEWS:
            sample_refs[view] = {}
            for index in (0, 450, 899):
                source = scratch / view / f"{index:06d}.png"
                if not source.is_file():
                    raise ValueError("original camera PNG sample missing")
                relative = f"source-frame-samples/{view}-{index:06d}.png"
                shutil.copyfile(source, output / relative)
                sample_refs[view][str(index)] = {"path": relative,
                    "sha256": _sha(output / relative)}
        (output / "source-frame-samples.json").write_text(json.dumps({
            "case_id": case["case_id"], "samples": sample_refs}, sort_keys=True) + "\n")
        (output / "original-history.json").write_text(json.dumps(packet, sort_keys=True) + "\n")
        (output / "camera-media-refs.json").write_text(json.dumps(media, sort_keys=True) + "\n")
        names = ("original-history.json", "video_frames.jsonl", "site.json",
                 "devices.json", "routes.json", "source-frame-samples.json",
                 "camera-media-refs.json")
        (output / "acquisition.json").write_text(json.dumps({name: {
            "kind": "original_native", "sha256": _sha(output / name)} for name in names},
            sort_keys=True) + "\n")
        pipeline.close(); pipeline = None
        frame_map.close(); frame_map = None
        recorder.close(); recorder = None
        phase = "sealed"
    finally:
        for resource in (pipeline, frame_map, recorder):
            if resource is not None:
                try:
                    resource.close()
                except BaseException as exc:
                    failures.append(repr(exc))
        for sensor in reversed(list(sensors.values())):
            try:
                sensor.destroy()
            except BaseException as exc:
                failures.append(repr(exc))
        try:
            adapter.destroy()
        except BaseException as exc:
            failures.append(repr(exc))
        try:
            restoration = restore(client, saved)
            restored = True
        except BaseException as exc:
            failures.append(repr(exc))
            restoration = {"restored": False}
        if phase == "sealed" and restored and not failures:
            seal_capture(output, frames=900, restoration=restoration, errors=[],
                encoder_exit_codes={name: 0 for name in VIEWS},
                context={"original_site_sources": survey["index"]["sources"],
                         "source_frame_samples": "source-frame-samples.json"})
        else:
            (output / "native-run-status.json").write_text(json.dumps({
                "phase": phase, "errors": failures or ["Native capture did not reach sealed state"],
                "settings_restored": restored}, sort_keys=True) + "\n")
            if phase == "sealed":
                raise RuntimeError("Native cleanup or restoration failed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check(), sort_keys=True))
    else:
        if not args.output_dir:
            parser.error("--output-dir required")
        run_native(args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
