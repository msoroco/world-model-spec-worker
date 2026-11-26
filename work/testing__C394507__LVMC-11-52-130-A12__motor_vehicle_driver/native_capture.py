"""Original Native crosswalk acquisition with exact source and frame readbacks."""

from __future__ import annotations

import copy
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import shutil
from zipfile import ZIP_STORED, ZipFile

from PIL import Image

import crosswalk_site as crossing

VIEWS = {"overview": (1920, 1080), "approach": (1280, 720),
         "reference_corner": (1280, 720), "driver_reference": (1280, 720)}
FRAMES = 900
FPS = 20


def digest(data):
    return hashlib.sha256(data).hexdigest()


def convex_hull(points):
    """Order the eight CARLA bounding-box vertices as a planar body polygon."""
    points = sorted(set((float(x), float(y)) for x, y in points))
    crossing.require(len(points) >= 3, "original body footprint degenerate")

    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    lower = []
    for point in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper = []
    for point in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return [list(point) for point in lower[:-1] + upper[:-1]]


def capture(world, operator, site, case_id, output, *, requested_clearance_m,
            camera_offset_m=0.0, diagnostic_frames=None, source_site_path=None):
    """Acquire source-sealed original readbacks; leave legal outcomes unresolved."""
    tag = case_id.removeprefix(crossing.ASSIGNMENT_ID + "__")
    controls = crossing.CASE_CONTROLS.get(tag)
    crossing.require(case_id.startswith(crossing.ASSIGNMENT_ID + "__") and
                     controls is not None, "unknown exact crossing case")
    crossing.require(abs(requested_clearance_m - controls[0]) < 1e-8,
                     "selected engineering clearance target changed")
    crossing.require(camera_offset_m in (0.0, 2.0),
                     "unsupported reviewed camera-position candidate")
    if diagnostic_frames is not None:
        crossing.require(getattr(operator, "diagnostic_test_only", False) is True and
                         type(diagnostic_frames) is int and 2 <= diagnostic_frames <= 20,
                         "short capture allowed only for a diagnostic operator")
    frame_count = FRAMES if diagnostic_frames is None else diagnostic_frames
    crossing.check_live_readback(operator, world, site)
    output = Path(output)
    crossing.require(not output.exists() or not any(output.iterdir()),
                     "original attempt output already populated")
    output.mkdir(parents=True, exist_ok=True)
    prior = copy.copy(world.get_settings())
    settings = copy.copy(prior)
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 1 / FPS
    vehicle = None
    sensors = []
    streams = {}
    rows = []
    pipeline_started = False
    try:
        world.apply_settings(settings)
        readback = world.get_settings()
        crossing.require(readback.synchronous_mode is True and
                         abs(readback.fixed_delta_seconds - .05) < 1e-9,
                         "original 20 Hz world setting readback failed")
        vehicle = crossing.construct(operator, site)
        crossing.require(getattr(vehicle, "is_alive", False) and
                         getattr(vehicle, "type_id", "").startswith("vehicle."),
                         "original motor vehicle actor unavailable")
        camera_callbacks, sensors = operator.cameras(world, vehicle, VIEWS,
                                                      camera_offset_m=camera_offset_m)
        crossing.require(set(camera_callbacks) == set(VIEWS),
                         "four original camera callbacks missing")
        if diagnostic_frames is None:
            operator.start_pipeline_capture(output, case_id)
            pipeline_started = True
        for view in VIEWS:
            streams[view] = ZipFile(output / (view + ".png.zip"), "x", compression=ZIP_STORED)
        start_time = previous_frame = None
        for index in range(frame_count):
            operator.control(vehicle, site, case_id)
            frame = world.tick()
            snapshot = world.get_snapshot()
            time = float(snapshot.timestamp.elapsed_seconds)
            crossing.require(type(frame) is int and snapshot.frame == frame and
                             (previous_frame is None or frame == previous_frame + 1),
                             "original Native frame identity gap")
            if start_time is None:
                start_time = time
            crossing.require(math.isfinite(time) and
                             abs(time - start_time - index / FPS) <= .005,
                             "original 20 Hz clock gap")
            previous_frame = frame
            observed = operator.observe(world, vehicle, frame, site)
            if pipeline_started:
                operator.capture_pipeline_tick(frame, round(index / FPS, 5))
            crossing.require(observed.get("source_frame_id") == frame and
                             str(observed.get("actor_id")) == str(vehicle.id) and
                             observed.get("ego_alive") is True,
                             "original actor readback mismatch")
            crossing.require(observed.get("road_id") == site.get("road_id") and
                             observed.get("lane_id") == site.get("lane_id"),
                             "original crosswalk approach lane changed")
            crossing.require(observed.get("crosswalk_marked") is site["crosswalk_marked"] and
                             observed.get("crossing_polygon_xy_m") == site["crossing_polygon_xy_m"],
                             "original marking or crossing extent changed")
            vertices = vehicle.bounding_box.get_world_vertices(vehicle.get_transform())
            body = [[float(vertex.x), float(vertex.y)] for vertex in vertices]
            crossing.require(len(body) == 8 and all(math.isfinite(value)
                                                     for point in body for value in point),
                             "original full vehicle-body vertices missing")
            speed = float(vehicle.get_velocity().length())
            transform = vehicle.get_transform()
            velocity = vehicle.get_velocity()
            position = transform.location
            crossing.require(math.isfinite(speed) and speed >= 0,
                             "original ego speed missing")
            row = {"frame": frame, "time_s": round(index / FPS, 5),
                   "ego_speed_mps": speed, "ego_body_polygon_xy_m": convex_hull(body),
                   "body_vertices_m": [[float(vertex.x), float(vertex.y), float(vertex.z)]
                                       for vertex in vertices],
                   "position_m": [float(position.x), float(position.y), float(position.z)],
                   "velocity_mps": [float(velocity.x), float(velocity.y), float(velocity.z)],
                   "heading_deg": float(transform.rotation.yaw),
                   "actor_id": str(vehicle.id), "vehicle_blueprint": vehicle.type_id,
                   "road_id": observed["road_id"], "lane_id": observed["lane_id"],
                   "activity_readback": observed.get("activity"),
                   "exception_readback": observed.get("exception_context"),
                   "camera_frames": {}}
            for view, dimensions in VIEWS.items():
                data = camera_callbacks[view](frame)
                crossing.require(type(data) is bytes and data,
                                 "original camera bytes missing: " + view)
                with Image.open(BytesIO(data)) as image:
                    image.load()
                    crossing.require(image.format == "PNG" and image.size == dimensions,
                                     "original camera dimensions differ: " + view)
                member = f"{frame:08d}.png"
                streams[view].writestr(member, data)
                row["camera_frames"][view] = {"member": member, "sha256": digest(data)}
            rows.append(row)
        crossing.require(digest(operator.map_bytes(world)) == site["map_sha256"],
                         "original map changed during capture")
        for stream in streams.values():
            stream.close()
        streams.clear()
        if pipeline_started:
            operator.close_pipeline_capture(confirmed=True)
            pipeline_started = False
        target_site = output / "original-site.json"
        if diagnostic_frames is None:
            crossing.require(source_site_path is not None,
                             "reviewed original site source path required")
            source_site_path = Path(source_site_path).resolve()
            with target_site.open("xb") as destination, source_site_path.open("rb") as source:
                shutil.copyfileobj(source, destination)
            crossing.require(json.loads(target_site.read_text()) == site,
                             "reviewed site content changed during capture")
            for record in site["source_records"].values():
                relative = Path(record["path"])
                source = source_site_path.parent / relative
                target = output / relative
                crossing.require(not target.exists(), "reviewed source output collision")
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as destination, source.open("rb") as original:
                    shutil.copyfileobj(original, destination)
                crossing.require(crossing.sha(target) == record["sha256"],
                                 "reviewed source changed during capture")
        else:
            target_site.write_text(json.dumps(site, sort_keys=True) + "\n")
        diagnostic = diagnostic_frames is not None
        packet = {"format": "crosswalk-native-history-v1",
                  "source_kind": "diagnostic_fixture" if diagnostic else "original_native",
                  "diagnostic_fixture": diagnostic,
                  "assignment_id": crossing.ASSIGNMENT_ID, "case_id": case_id,
                  "fps": FPS, "frame_count": frame_count, "samples": rows,
                  "site_sha256": digest((output / "original-site.json").read_bytes()),
                  "camera_archives": {view: {"path": view + ".png.zip",
                                             "sha256": crossing.sha(output / (view + ".png.zip")),
                                             "frame_count": frame_count, "dimensions": list(dimensions)}
                                      for view, dimensions in VIEWS.items()}}
        (output / "original-crosswalk-history.json").write_text(json.dumps(packet, sort_keys=True) + "\n")
        return {"case_id": case_id,
                "source_kind": "diagnostic_fixture" if diagnostic else "original_native",
                "history_sha256": crossing.sha(output / "original-crosswalk-history.json"),
                "camera_archives": packet["camera_archives"],
                "physical_acceptance_claimed": False,
                "legal_assessment": "unresolved"}
    finally:
        if pipeline_started:
            operator.close_pipeline_capture(confirmed=False)
        for stream in streams.values():
            stream.close()
        for sensor in reversed(sensors):
            try:
                if hasattr(sensor, "stop"):
                    sensor.stop()
            finally:
                sensor.destroy()
        if vehicle is not None and getattr(vehicle, "is_alive", False):
            vehicle.destroy()
        world.apply_settings(prior)
        restored = world.get_settings()
        crossing.require(restored.synchronous_mode == prior.synchronous_mode and
                         restored.fixed_delta_seconds == prior.fixed_delta_seconds,
                         "original world settings restoration unverified")
