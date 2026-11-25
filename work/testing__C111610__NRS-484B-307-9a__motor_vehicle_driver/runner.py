"""Source-gated Native red-plus-green-arrow capture entrypoint.

The reviewed adapter reads original heads, participants and cameras after each
world tick. Its source hash and site packet are required before CARLA connects.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from native_capture import OriginalVideo, capture
from native_turn import case_command, construct_native, verify_site


HERE = Path(__file__).resolve().parent
ASSIGNMENT = "testing__C111610__NRS-484B-307-9a__motor_vehicle_driver"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
DIMENSIONS = {"overview": [1920, 1080], "approach": [1280, 720],
              "reference_corner": [1280, 720], "driver_reference": [1280, 720]}


def _read_ref(root, ref):
    if not isinstance(ref, dict) or not isinstance(ref.get("path"), str):
        raise ValueError("reviewed adapter source reference missing")
    path = (root / ref["path"]).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("reviewed adapter source path invalid")
    if hashlib.sha256(path.read_bytes()).hexdigest() != ref.get("sha256"):
        raise ValueError("reviewed adapter source hash mismatch")
    return path


def check(root=HERE):
    root = Path(root).resolve()
    config = json.loads((root / "config.json").read_text())
    suffix = config["case_suffix"]
    cameras = config.get("cameras", [])
    names = [camera.get("name") for camera in cameras if isinstance(camera, dict)]
    if (config.get("assignment_id") != ASSIGNMENT or
            config.get("selected_case_id") != ASSIGNMENT + "__" + suffix or
            config.get("law_id") != "NRS-484B-307-9a" or
            config.get("cell_id") != "C111610" or
            config.get("actor") != "motor_vehicle_driver" or
            (config.get("rate_hz"), config.get("frame_count")) != (20, 600) or
            tuple(names) != CAMERAS or
            any([camera.get("width"), camera.get("height")] != DIMENSIONS[camera["name"]]
                for camera in cameras)):
        raise ValueError("exact red-plus-arrow case configuration differs")
    profile = json.loads((root / "camera_profile.json").read_text())
    if (profile.get("fps") != 20 or profile.get("duration_frames") != 600 or
            profile.get("cameras") != list(CAMERAS) or
            profile.get("dimensions") != DIMENSIONS):
        raise ValueError("exact red-plus-arrow camera profile differs")
    case_command(suffix, suffix in ("yield_pedestrian", "continue_pedestrian"))
    plan = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(plan).hexdigest() != config.get("plan_sha256"):
        raise ValueError("exact red-plus-arrow plan hash changed")
    if config["selected_case_id"] not in {row["case_id"] for row in json.loads(plan)["cases"]}:
        raise ValueError("exact red-plus-arrow case missing from plan")
    return config


def load_reviewed_adapter(site, source_root):
    source_root = Path(source_root).resolve()
    path = _read_ref(source_root, site.get("adapter_source"))
    if path.suffix != ".py":
        raise ValueError("reviewed adapter source must be Python")
    spec = importlib.util.spec_from_file_location("c111610_9a_reviewed_adapter", path)
    if spec is None or spec.loader is None:
        raise ValueError("reviewed adapter cannot load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "bind", None)):
        raise ValueError("reviewed adapter bind() missing")
    return module


class OriginalAdapter:
    def __init__(self, world, site, site_raw, module, module_ref, command,
                 actors):
        self.world = world
        self.site_sha256 = hashlib.sha256(site_raw).hexdigest()
        self.module_ref = module_ref
        self.state = module.bind(world, site, command, actors)
        for name in ("command", "read", "close"):
            if not callable(getattr(self.state, name, None)):
                raise ValueError("reviewed adapter state lacks " + name)
        self.index = 0

    def source_attestation(self):
        return {"native_origin": True, "site_sha256": self.site_sha256,
                "source_ref": self.module_ref["path"],
                "adapter_sha256": self.module_ref["sha256"]}

    def tick(self):
        self.state.command(self.index)
        native_frame = self.world.tick()
        original = self.state.read(native_frame, self.index)
        if (original.get("native_frame") != native_frame or
                original.get("telemetry", {}).get("frame") != self.index or
                any(original.get("cameras", {}).get(name, {}).get("frame") != native_frame
                    for name in CAMERAS)):
            raise ValueError("reviewed adapter same-tick source mismatch")
        self.index += 1
        return original

    def close(self):
        self.state.close()


def run_native(root, output, source_root, *, host="localhost", port=2000):
    root, output, source_root = map(lambda value: Path(value).resolve(),
                                    (root, output, source_root))
    config = check(root)
    site_path = source_root / "site.json"
    if not site_path.is_file():
        raise ValueError("reviewed original C111610 red-arrow site packet missing")
    site_raw = site_path.read_bytes()
    site = json.loads(site_raw)
    if (site.get("source_kind") != "original_native_site_review" or
            site.get("case_id") != config["selected_case_id"]):
        raise ValueError("reviewed original site provenance or case differs")
    verify_site(site, source_root)
    module = load_reviewed_adapter(site, source_root)
    profile_path = root / "camera_profile.json"
    if not profile_path.is_file():
        raise ValueError("exact four-camera profile missing")
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    client = carla.Client(host, int(port))
    client.set_timeout(30.0)
    world = client.get_world()
    settings = world.get_settings()
    previous = (settings.synchronous_mode, settings.fixed_delta_seconds)
    adapter = None
    actors = {}
    pipeline = video = frame_map = None
    body_history = None
    codes = {}
    frames = 0
    restored = False
    try:
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        command = case_command(config["case_suffix"],
                               config["case_suffix"] in ("yield_pedestrian", "continue_pedestrian"))
        spawned = construct_native(site, source_root, world,
                                   world.get_blueprint_library(), carla,
                                   config["case_suffix"], site["spawn_plan"])
        actors = spawned["actors"]
        if spawned["command"] != command:
            raise ValueError("reviewed original construction command differs")
        adapter = OriginalAdapter(world, site, site_raw, module,
                                  site["adapter_source"], command, actors)
        output.mkdir(parents=True, exist_ok=True)
        if any((output / name).exists() for name in ("capture", "trace.jsonl",
                                                    "video_frames.jsonl", "body_history.jsonl")):
            raise ValueError("original acquisition already exists")
        (output / "acquisition-provenance.json").write_text(json.dumps({
            "provenance_kind": "native", "diagnostic_fixture": False,
            "physical_acceptance_claimed": False,
            "method": "reviewed original CARLA site and live same-tick acquisition"}, indent=2) + "\n")
        pipeline = PipelineCapture(client, actors["ego"], output,
                                   config["selected_case_id"])
        frame_map = FrameMap(output / "video_frames.jsonl")
        video = OriginalVideo(output, json.loads(profile_path.read_text()))
        body_history = (output / "body_history.jsonl").open("x", buffering=1)

        def on_frame(index, original):
            nonlocal frames
            native_frame = original["native_frame"]
            time_s = original["native_elapsed_s"]
            pipeline.capture(native_frame, time_s)
            frame_map.append(native_frame, time_s)
            video.append(original["cameras"])
            ego = actors["ego"]
            vertices = ego.bounding_box.get_world_vertices(ego.get_transform())
            body_history.write(json.dumps({"frame": native_frame, "time_s": time_s,
                "body_vertices_m": [[p.x, p.y, p.z] for p in vertices],
                "heading_deg": ego.get_transform().rotation.yaw,
                "source": "original live CARLA actor bounding box and transform"}) + "\n")
            frames = index + 1

        capture(adapter, site_path, profile_path, output,
                config["case_suffix"], on_frame=on_frame)
        pipeline.close(); pipeline = None
        frame_map.close(); frame_map = None
        codes = video.close(); video = None
        body_history.close(); body_history = None
    finally:
        try:
            for resource in (pipeline, frame_map, video, body_history):
                if resource is not None:
                    resource.close()
            if adapter is not None: adapter.close()
        finally:
            try:
                for actor in reversed(tuple(actors.values())):
                    actor.destroy()
            finally:
                settings.synchronous_mode, settings.fixed_delta_seconds = previous
                world.apply_settings(settings)
                restored = world.get_settings()
                if (restored.synchronous_mode, restored.fixed_delta_seconds) != previous:
                    raise ValueError("original world settings restoration readback differs")
                restored = True
    if frames != 600 or not restored or set(codes) != set(CAMERAS):
        raise ValueError("original acquisition incomplete or restoration unverified")
    return seal_capture(output, frames=frames,
                        restoration={"restored": True,
                                     "settings_readback": "synchronous mode and fixed delta restored"},
                        errors=[], encoder_exit_codes=codes,
                        context={"red_arrow_site_sha256": hashlib.sha256(site_raw).hexdigest(),
                                 "case_id": config["selected_case_id"]})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(check()["selected_case_id"])
        return
    if args.output_dir is None:
        raise ValueError("original output directory required")
    site_root = Path(os.environ.get("C111610_9A_SITE_ROOT", str(HERE)))
    run_native(HERE, args.output_dir, site_root, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
