"""Lazy CARLA acquisition for a separately reviewed cycle-lane site.

The worker CPU tests never import CARLA or contact a simulator. This adapter
records original frames; its output still needs independent physical review.
"""
from __future__ import annotations

import hashlib
import json
import math
import queue
import shutil
import subprocess
from pathlib import Path

from cycle_lane_native import VIEWS, control
from cycle_lane_original import _intersects
from cycle_lane_site import _polygon


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hull(points):
    unique = sorted(set((float(x), float(y)) for x, y in points))
    if len(unique) < 3:
        raise ValueError("Native vehicle body polygon degenerate")
    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    lower = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return _polygon([list(point) for point in lower[:-1] + upper[:-1]])


class NativeAdapter:
    def __init__(self, host: str, port: int, output: Path, sources: dict,
                 hashes: dict, plan: dict):
        import carla
        self.carla = carla
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.sources, self.hashes, self.plan = sources, hashes, plan
        self.site = json.loads(sources["site"].read_text())
        xodr = self.site.get("highway_xodr", {})
        road = sources["site"].parent / xodr.get("path", "")
        if (not xodr.get("path") or not road.resolve().is_relative_to(sources["site"].parent.resolve()) or
                road.suffix.lower() != ".xodr" or not road.is_file() or
                _sha(road) != xodr.get("sha256")):
            raise ValueError("reviewed OpenDRIVE highway hash required")
        self.client = carla.Client(host, port)
        self.client.set_timeout(30.0)
        self.world = self.client.generate_opendrive_world(road.read_text())
        if self.world.get_map().name != plan["map_id"]:
            raise ValueError("Native map differs from reviewed source map")
        self.old_settings = self.world.get_settings()
        self.owned = []
        self.sensors = {}
        self.closed = False
        self.recorder_started = False
        self.road = road
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        self.world.apply_settings(settings)
        self.client.start_recorder(str(self.output / "carla_recorder.log"))
        self.recorder_started = True

    def _vehicle(self):
        bp = self.world.get_blueprint_library().find(self.plan["vehicle_blueprint_id"])
        if bp is None:
            raise ValueError("reviewed vehicle blueprint absent in Native world")
        first, second = self.plan["route"][:2]
        yaw = math.degrees(math.atan2(second[1] - first[1], second[0] - first[0]))
        waypoint = self.world.get_map().get_waypoint(self.carla.Location(x=first[0], y=first[1]),
                                                      project_to_road=False)
        if waypoint is None:
            raise ValueError("reviewed source route start absent in Native map")
        pose = self.carla.Transform(self.carla.Location(x=first[0], y=first[1],
                                                        z=waypoint.transform.location.z + 0.5),
                                    self.carla.Rotation(yaw=yaw))
        actor = self.world.try_spawn_actor(bp, pose)
        if actor is None:
            raise ValueError("reviewed source route vehicle spawn failed")
        self.owned.append(actor)
        self.spawned_actor_id = actor.id
        return actor

    def _cameras(self, ego):
        poses = {"overview": (-7.0, 0.0, 3.0, -12.0),
                 "approach": (2.0, 0.0, 1.7, 0.0),
                 "reference_corner": (-3.0, 2.5, 2.3, -8.0),
                 "driver_reference": (0.1, 0.0, 1.55, 0.0)}
        for name in VIEWS:
            bp = self.world.get_blueprint_library().find("sensor.camera.rgb")
            if bp is None:
                raise ValueError("Native RGB camera blueprint absent")
            bp.set_attribute("image_size_x", "1920" if name == "overview" else "1280")
            bp.set_attribute("image_size_y", "1080" if name == "overview" else "720")
            bp.set_attribute("sensor_tick", "0.05")
            x, y, z, pitch = poses[name]
            pose = self.carla.Transform(self.carla.Location(x=x, y=y, z=z),
                                        self.carla.Rotation(pitch=pitch))
            sensor = self.world.spawn_actor(bp, pose, attach_to=ego)
            self.owned.append(sensor)
            frames = queue.Queue(maxsize=4)
            sensor.listen(frames.put)
            self.sensors[name] = frames

    def execute(self, config: dict):
        ego = self._vehicle()
        self._cameras(ego)
        site = self.site
        intersection = _polygon(site["intersection_polygon"])
        lane = _polygon(site["cycle_lane_polygon"])
        history = []
        trace = (self.output / "trace.jsonl").open("x", encoding="utf-8")
        frame_map = (self.output / "video_frames.jsonl").open("x", encoding="utf-8")
        evidence_path = self.output / "capture/evidence.jsonl"
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence = evidence_path.open("x", encoding="utf-8")
        native_path = self.output / "capture/native/frames.jsonl"
        native_path.parent.mkdir(parents=True, exist_ok=True)
        native_index = native_path.open("x", encoding="utf-8")
        try:
            for index in range(900):
                transform = ego.get_transform()
                position = transform.location
                velocity = ego.get_velocity()
                speed = math.hypot(velocity.x, velocity.y)
                command = control((position.x, position.y), math.radians(transform.rotation.yaw),
                                  speed, self.plan["route"])
                ego.apply_control(self.carla.VehicleControl(
                    throttle=command["throttle"], steer=command["steer"], brake=command["brake"]))
                frame = self.world.tick()
                for name, frames in self.sensors.items():
                    image = frames.get(timeout=20)
                    if image.frame != frame:
                        raise ValueError("four-camera original frame join failed")
                    folder = self.output / "capture" / name
                    folder.mkdir(parents=True, exist_ok=True)
                    image.save_to_disk(str(folder / f"{index:06d}.png"))
                transform = ego.get_transform()
                position = transform.location
                velocity = ego.get_velocity()
                vertices = ego.bounding_box.get_world_vertices(transform)
                body = _hull((v.x, v.y) for v in vertices)
                time_s = index / 20
                history.append({"frame": frame, "time_s": time_s, "ego_actor_id": ego.id,
                                "ego_body_polygon": [list(v) for v in body],
                                "ego_body_in_intersection": _intersects(body, intersection),
                                "ego_body_in_designated_cycle_lane": _intersects(body, lane)})
                speed = math.hypot(velocity.x, velocity.y)
                trace.write(json.dumps({"frame": frame, "time_s": time_s,
                                        "position_m": [position.x, position.y, position.z],
                                        "speed_mps": speed,
                                        "velocity_mps": [velocity.x, velocity.y, velocity.z],
                                        "heading_deg": transform.rotation.yaw,
                                        "control": command}) + "\n")
                frame_map.write(json.dumps({"video_frame": index, "carla_frame": frame,
                                            "native_frame": frame, "time_s": time_s}) + "\n")
                observed = {"frame": frame, "time_s": time_s, "participants": [],
                            "map_context": {"declared_public_way_road_ids": []}}
                evidence.write(json.dumps({"original_frame": frame, "replay_frame": frame,
                    "actor_id": ego.id, "recording_time_s": time_s,
                    "replay_simulation_time_s": time_s, "world": {"weather": {}},
                    "ego": {"position_m": [position.x, position.y, position.z],
                            "heading_deg": transform.rotation.yaw, "speed_mps": speed,
                            "speed_provenance": "original_native_readback",
                            "body_vertices_m": [[v.x, v.y, v.z] for v in vertices]},
                    "original_observations": observed}) + "\n")
                graph_rel = f"graphs/base/{index:08d}.adapter.json"
                graph = self.output / "capture/native" / graph_rel
                graph.parent.mkdir(parents=True, exist_ok=True)
                graph.write_text(json.dumps({"path": "capture/native/" + graph_rel,
                    "attributes": {"frame": frame, "time_s": time_s,
                                   "observed_evidence": observed},
                    "nodes": [], "edges": []}) + "\n", encoding="utf-8")
                native_index.write(json.dumps({"frame": frame, "simulation_time": time_s,
                                               "adapter_graph": graph_rel}) + "\n")
        finally:
            trace.close()
            frame_map.close()
            evidence.close()
            native_index.close()
        (self.output / "history.json").write_text(json.dumps(history) + "\n")
        (self.output / "capture/manifest.json").write_text(json.dumps({
            "status": "draft", "acquisition": "original_native",
            "case_id": config["selected_case_id"], "frames": 900,
            "extraction_confirmed": True, "complete_driving_lanes": False,
            "sources": {"road.xodr": _sha(self.road),
                        "trace.jsonl": _sha(self.output / "trace.jsonl")}}) + "\n")
        cameras = {}
        for view in VIEWS:
            folder = self.output / "capture" / view
            video = self.output / (view + ".mkv")
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                            "-framerate", "20", "-start_number", "0", "-i",
                            str(folder / "%06d.png"), "-frames:v", "900", "-c:v", "ffv1",
                            "-pix_fmt", "bgr0", str(video)], check=True, timeout=600)
            cameras[view] = {"path": video.name, "sha256": _sha(video)}
        refs = {}
        for name, path in self.sources.items():
            target = self.output / (name + ".json")
            shutil.copy2(path, target)
            refs[name] = {"path": target.name, "sha256": _sha(target)}
        shutil.copy2(self.sources["site"], self.output / "site-source.json")
        shutil.copy2(self.sources["subsection_3"], self.output / "subsection_3-source.json")
        shutil.copy2(self.road, self.output / "road.xodr")
        seal = {"format": "cycle-lane-native-attempt-v1", "source_kind": "original_native",
                "diagnostic_fixture": False, "case_id": config["selected_case_id"],
                "spawned_actor_id": self.spawned_actor_id,
                "vehicle_blueprint_id": self.plan["vehicle_blueprint_id"],
                "site": refs["site"], "subsection_3": refs["subsection_3"],
                "vehicle": refs["vehicle"], "route_candidate_id": config["route_candidate_id"],
                "history": {"path": "history.json", "sha256": _sha(self.output / "history.json")},
                "cameras": cameras, "capture_profile": self.plan["capture_profile"]}
        (self.output / "attempt-source.json").write_text(json.dumps(seal, indent=2) + "\n")

    def close(self):
        if self.closed:
            return
        errors = []
        for actor in reversed(self.owned):
            try:
                if hasattr(actor, "stop"):
                    actor.stop()
                actor.destroy()
            except Exception as error:
                errors.append(repr(error))
        if self.recorder_started:
            try:
                self.client.stop_recorder()
                details = self.client.show_recorder_file_info(
                    str(self.output / "carla_recorder.log"), False)
                (self.output / "capture/recorder_info.txt").write_text(details)
            except Exception as error:
                errors.append(repr(error))
        try:
            self.world.apply_settings(self.old_settings)
            restored = self.world.get_settings()
            self.restoration_verified = (not errors and
                restored.synchronous_mode == self.old_settings.synchronous_mode and
                restored.fixed_delta_seconds == self.old_settings.fixed_delta_seconds)
        except Exception as error:
            errors.append(repr(error))
            self.restoration_verified = False
        self.closed = True
        if not self.restoration_verified:
            raise ValueError("Native restoration not verified: " + repr(errors))
