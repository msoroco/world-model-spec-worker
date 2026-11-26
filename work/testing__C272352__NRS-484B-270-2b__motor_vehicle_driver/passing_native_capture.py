"""Original-frame Native acquisition for one source-sealed passing attempt.

The Native adapter is supplied locally. CPU fixtures exercise the protocol but
cannot claim that a real road, actor classification or safe pass was observed.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from passing_controller import Sample, command
from passing_scene import construct


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
FRAME_COUNT = 900


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def capture(adapter, packet_path, case, destination, *, synthetic=False,
            frame_count=FRAME_COUNT):
    destination = Path(destination)
    if destination.exists():
        raise ValueError("Native attempt destination already exists")
    if not synthetic and frame_count != FRAME_COUNT:
        raise ValueError("full original 900-frame capture required")
    if not synthetic and getattr(adapter, "native_attested", False) is not True:
        raise ValueError("attested original Native adapter required")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="original-pass-", dir=destination.parent))
    owned = []
    try:
        scene = construct(adapter, packet_path, case, synthetic=synthetic)
        owned = scene["owned"]
        map_ref = next(ref for ref in scene["survey"]["source_refs"]
                       if ref["role"] == "map")
        context_path = stage / "original-context.json"
        write(context_path, {"case_id": case["case_id"],
                             "highway_source": scene["survey"]["public_highway_source"],
                             "lane_count_same_direction": 1,
                             "centerline_y": scene["survey"]["centerline_y"],
                             "right_side_y": scene["survey"]["right_side_y"],
                             "vehicle_id": str(adapter.actor_id(scene["ego"])),
                             "bicycle_id": str(adapter.actor_id(scene["control"])),
                             "bicycle_kind": scene["survey"]["control_kind"],
                             "map_sha256": map_ref["sha256"],
                             "centerline_source": scene["survey"]["centerline_source"],
                             "zone_source": scene["survey"]["zone_source"],
                             "opposing_traffic_source": scene["survey"]["opposing_traffic_source"],
                             "exception_213_217_source": scene["survey"]["exception_213_217_source"],
                             "reviewed_packet_sha256": sha(packet_path)})
        camera_dirs = {name: stage / ("frames-" + name) for name in CAMERAS}
        for folder in camera_dirs.values():
            folder.mkdir()
        trace = []
        joined = []
        prior = None
        for index in range(frame_count):
            observed = adapter.observe_pass(scene)
            if not isinstance(observed, Sample):
                raise ValueError("original source-bound body/traffic sample required")
            intent = command(case, observed)
            adapter.apply_pass_control(scene["ego"], intent)
            snapshot = adapter.tick(scene)
            frame, time_s = snapshot.get("frame"), snapshot.get("time_s")
            if type(frame) is not int or type(time_s) not in (int, float) or \
                    frame != observed.original_frame + 1:
                raise ValueError("Native motion/frame join failed")
            if prior is not None and (frame != prior[0] + 1 or
                                      abs(time_s - prior[1] - .05) > .002):
                raise ValueError("original 20 Hz frame join failed")
            prior = frame, time_s
            row = adapter.read_pass_row(scene, frame)
            required = {"vehicle_box", "bicycle_box", "vehicle_speed_mps",
                        "bicycle_speed_mps", "vehicle_source", "bicycle_source",
                        "lane_source"}
            if row.get("origin") != "native_world_snapshot" or \
                    row.get("frame") != frame or row.get("time_s") != time_s or \
                    required - row.keys():
                raise ValueError("original body/source readback missing")
            row = dict(row)
            row["control_intent"] = intent
            cameras = adapter.read_cameras(scene, frame)
            if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS):
                raise ValueError("four original cameras required")
            hashes = {}
            for name in CAMERAS:
                image = cameras[name]
                raw = image.get("png")
                if image.get("frame") != frame or image.get("time_s") != time_s or \
                        not isinstance(raw, bytes) or not raw.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("original camera pixel/frame join failed: " + name)
                (camera_dirs[name] / f"{index:04d}.png").write_bytes(raw)
                hashes[name] = hashlib.sha256(raw).hexdigest()
            trace.append(row)
            joined.append({"frame": frame, "time_s": time_s,
                           "camera_png_sha256": hashes})
        trace_path = stage / "original-trace.jsonl"
        trace_path.write_text("".join(json.dumps(x, sort_keys=True) + "\n" for x in trace), encoding="utf-8")
        camera_map_path = stage / "camera-frame-map.jsonl"
        camera_map_path.write_text("".join(json.dumps(x, sort_keys=True) + "\n"
                                           for x in joined), encoding="utf-8")
        from worker_exchange.native_output import FrameMap
        with FrameMap(stage / "video_frames.jsonl") as canonical:
            for item in joined:
                canonical.append(item["frame"], item["time_s"],
                                 camera_png_sha256=item["camera_png_sha256"])
        def corners(box):
            return [[box[0], box[2], 0.0], [box[0], box[3], 0.0],
                    [box[1], box[2], 0.0], [box[1], box[3], 0.0]]
        (stage / "trace.jsonl").write_text("".join(json.dumps({
            "frame": row["frame"], "time_s": row["time_s"],
            "position_m": [(row["vehicle_box"][0] + row["vehicle_box"][1]) / 2,
                           (row["vehicle_box"][2] + row["vehicle_box"][3]) / 2],
            "vehicle_vertices_m": corners(row["vehicle_box"]),
            "bicycle_vertices_m": corners(row["bicycle_box"]),
            "vehicle_box": row["vehicle_box"], "bicycle_box": row["bicycle_box"]
        }, sort_keys=True) + "\n" for row in trace), encoding="utf-8")
        videos = {}
        for name, folder in camera_dirs.items():
            video = stage / (name + ".mkv")
            subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-framerate", "20",
                            "-i", str(folder / "%04d.png"), "-frames:v", str(frame_count),
                            "-c:v", "ffv1", str(video)], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            videos[name] = {"path": video.name, "sha256": sha(video),
                            "frame_count": frame_count}
            shutil.rmtree(folder)
        receipt = {"case_id": case["case_id"],
                   "source_kind": "synthetic_diagnostic_fixture" if synthetic else "original_native_capture",
                   "diagnostic_fixture": synthetic, "fps": 20, "frame_count": frame_count,
                   "context_sha256": sha(context_path),
                   "trace_sha256": sha(trace_path),
                   "frame_map_sha256": sha(camera_map_path),
                   "canonical_frame_map_sha256": sha(stage / "video_frames.jsonl"),
                   "canonical_trace_sha256": sha(stage / "trace.jsonl"),
                   "reviewed_packet_sha256": sha(packet_path), "cameras": videos,
                   "physical_acceptance": False, "legal_verdict": None}
        write(stage / "original-source-receipt.json", receipt)
        os.replace(stage, destination)
        return receipt
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    finally:
        try:
            adapter.brake()
        finally:
            try:
                for actor in reversed(owned):
                    adapter.destroy(actor)
            finally:
                adapter.restore()
