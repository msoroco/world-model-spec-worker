"""Source-gated two-actor Native capture contract for a supplied CARLA adapter."""
from __future__ import annotations

import hashlib
import json
import math
import shutil
from pathlib import Path

from entry_timing import measure

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def capture(adapter, config, site, site_path, site_sha256, output):
    """Capture observed footprints and four synchronized views, then release owner."""
    output = Path(output).resolve()
    if not (output / "construction.json").is_file() or (output / "original-attempt").exists():
        raise ValueError("materialized unused exact attempt required")
    original = output / "original-attempt"
    original.mkdir()
    shutil.copy2(site_path, original / "site.json")
    if sha(original / "site.json") != site_sha256:
        raise ValueError("reviewed site changed during capture")
    case = config["selected_case_id"]
    actors = {}
    rows, traces, video_rows = [], [], []
    restored = False
    try:
        adapter.setup(config, site)
        actors = adapter.spawn_pair(site, config)
        if set(actors) != {"ego", "other"}:
            raise ValueError("two reviewed highway participants required")
        cameras = adapter.attach_cameras(actors, config["cameras"])
        if set(cameras) != set(VIEWS):
            raise ValueError("four original cameras required")
        first_frame = None
        for index in range(900):
            adapter.apply_timing_control(actors, site, config.get("control", {}), index)
            sample = adapter.tick_and_read(actors, cameras)
            frame, time_s = sample.get("frame"), sample.get("time_s")
            if first_frame is None:
                first_frame = frame
            if type(frame) is not int or frame != first_frame + index or type(time_s) not in (int, float) or \
                    not math.isfinite(time_s) or abs(time_s - index / 20) > .005:
                raise ValueError("original 20 Hz frame/time gap")
            participants = {}
            for who in ("ego", "other"):
                actor = sample.get(who)
                if not isinstance(actor, dict) or actor.get("id") != site[who + "_actor_id"] or \
                        actor.get("road_id") != site[who + "_road_id"] or \
                        not isinstance(actor.get("body_corners_xy_m"), list):
                    raise ValueError("original actor/highway footprint source missing")
                participants[who] = actor
            images = sample.get("camera_png", {})
            if set(images) != set(VIEWS) or any(
                    not isinstance(images[name], bytes) or
                    not images[name].startswith(b"\x89PNG\r\n\x1a\n") for name in VIEWS):
                raise ValueError("synchronized original image pixels missing")
            trace, video = sample.get("trace"), sample.get("video_frame")
            if not isinstance(trace, dict) or not isinstance(video, dict) or \
                    trace.get("frame") != frame or trace.get("time_s") != time_s or \
                    video.get("carla_frame") != frame or video.get("time_s") != time_s:
                raise ValueError("original trace/video join missing")
            rows.append({"frame": frame, "time_s": time_s, **participants})
            traces.append(trace)
            video_rows.append(video)
        media = adapter.finalize_media(output, VIEWS, 900)
        if set(media) != set(VIEWS) | {"raw"} or any(
                Path(media[name]).resolve() != (output / (name + ".mkv")).resolve() or
                not Path(media[name]).is_file() or Path(media[name]).stat().st_size == 0
                for name in media):
            raise ValueError("original encoded media incomplete")
    finally:
        for actor in reversed(list(actors.values())):
            adapter.destroy(actor)
        restored = adapter.close() is True
    if not restored or len(rows) != 900:
        raise ValueError("Native restoration or capture incomplete")
    packet = {key: site[key] for key in (
        "map_source_sha256", "intersection_source_sha256", "highway_source_sha256",
        "device_source_sha256", "intersection_polygon_xy_m", "ego_actor_id",
        "other_actor_id", "ego_road_id", "other_road_id")}
    packet.update({"case_id": case, "source_kind": "original_native",
                   "diagnostic_fixture": False, "frames": rows})
    source = original / "entry-timing-source.json"
    write(source, packet)
    measured = measure(source, sha(source), case_id=case)
    (output / "trace.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in traces))
    (output / "video_frames.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in video_rows))
    write(original / "site-binding.json", {"case_id": case, "site_sha256": site_sha256,
                                           "source_sha256": sha(source)})
    write(output / "capture-seal.json", {"events": ["capture_finished", "encoders_closed",
                                                    "restoration_verified"],
                                         "source_sha256": sha(source),
                                         "construction_sha256": sha(output / "construction.json")})
    return {"case_id": case, "frame_count": 900,
            "entry_timing": measured["intersection_entry_time_difference_s"],
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}
