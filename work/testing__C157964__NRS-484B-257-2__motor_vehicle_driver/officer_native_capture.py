"""Source-bound four-view Native acquisition for the officer exception cases.

An injected Native adapter supplies actual ticks, actor states, cameras and media.
No requested gesture or location is treated as an observed legal fact.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

from officer_scene import CASES, construct
from officer_site_packet import validate_packet


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def capture(adapter, config: dict, site_path: Path, output: Path) -> dict:
    case_id = config["selected_case_id"]
    suffix = case_id.removeprefix(config["assignment_id"] + "__")
    case = next((row for row in CASES if row.suffix == suffix), None)
    if case is None:
        raise ValueError("unknown exact officer case")
    site = validate_packet(site_path, case_id)
    output = Path(output)
    if output.exists():
        if not (output / "construction.json").is_file() or \
                (output / "original-attempt").exists():
            raise ValueError("refusing to overwrite original attempt")
    else:
        output.mkdir(parents=True)
    original = output / "original-attempt"
    original.mkdir()
    sources_folder = original / "source-review"
    sources_folder.mkdir()
    sealed_site = json.loads(json.dumps(site))
    for name, item in sealed_site["sources"].items():
        destination = sources_folder / (name + Path(item["path"]).suffix)
        shutil.copy2(Path(site_path).parent / item["path"], destination)
        if _sha(destination.read_bytes()) != item["sha256"]:
            raise ValueError("source changed during acquisition: " + name)
        item["path"] = "source-review/" + destination.name
    _write(original / "site-packet.json", sealed_site)
    rows = []
    frame_map = []
    traces = []
    video_frames = []
    archives = {}
    owned = ()
    restored = False
    try:
        scene = construct(adapter, site, case)
        owned = scene["actors"]
        cameras = adapter.attach_cameras(owned, config["cameras"])
        if set(cameras) != set(VIEWS):
            raise ValueError("four original camera sources missing")
        for name in VIEWS:
            archives[name] = zipfile.ZipFile(original / (name + ".zip"), "x",
                                             compression=zipfile.ZIP_STORED)
        first_frame = first_time = None
        for index in range(config["frame_count"]):
            adapter.request_officer_case_control(owned, case, index)
            sample = adapter.tick_and_read(owned, cameras)
            if not isinstance(sample, dict):
                raise ValueError("original Native tick missing")
            frame, time_s = sample.get("frame"), sample.get("time_s")
            if type(frame) is not int or type(time_s) not in (int, float):
                raise ValueError("original Native frame/time missing")
            first_frame = frame if first_frame is None else first_frame
            first_time = time_s if first_time is None else first_time
            if frame != first_frame + index or abs(time_s - first_time - index / 20) > .005:
                raise ValueError("original Native frame/time gap")
            cameras_png = sample.get("camera_png")
            if not isinstance(cameras_png, dict) or set(cameras_png) != set(VIEWS):
                raise ValueError("original four-view camera join missing")
            hashes = {}
            for name in VIEWS:
                raw = cameras_png[name]
                if not isinstance(raw, bytes) or not raw.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("invalid original camera PNG: " + name)
                filename = f"{index:04d}-{frame}.png"
                archives[name].writestr(filename, raw)
                hashes[name] = {"member": filename, "sha256": _sha(raw)}
            state = sample.get("state")
            if not isinstance(state, dict) or not all(
                    key in state for key in ("ego", "other", "officer", "officer_directive")):
                raise ValueError("original actor/officer state missing")
            trace = sample.get("trace")
            video_frame = sample.get("video_frame")
            if not isinstance(trace, dict) or trace.get("frame") != frame or \
                    trace.get("time_s") != time_s or \
                    not isinstance(video_frame, dict) or \
                    video_frame.get("video_frame") != index or \
                    video_frame.get("carla_frame") != frame or \
                    video_frame.get("time_s") != time_s:
                raise ValueError("original trace/video identity join missing")
            rows.append({"case_id": case_id, "frame": frame, "elapsed_s": index / 20,
                         "time_s": time_s, "state": state, "camera_frames": hashes})
            frame_map.append({"frame": index, "carla_frame": frame,
                              "elapsed_s": index / 20, "time_s": time_s})
            traces.append(trace)
            video_frames.append(video_frame)
        media = adapter.finalize_media(output, VIEWS, tuple(frame_map))
        if not isinstance(media, dict) or set(media) != set(VIEWS) | {"raw"} or \
                any(Path(media[name]).resolve() != (output / (name + ".mkv")).resolve()
                    or not Path(media[name]).is_file() or Path(media[name]).stat().st_size == 0
                    for name in media):
            raise ValueError("original encoded media incomplete")
    finally:
        for archive in archives.values():
            archive.close()
        try:
            for actor in reversed(owned):
                adapter.destroy(actor)
        finally:
            restored = adapter.close() is True
    if not restored or len(rows) != config["frame_count"]:
        raise ValueError("Native restoration or complete frame history missing")
    _write(original / "history.json", rows)
    _write(original / "frame-map.json", frame_map)
    (output / "trace.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n"
                                              for row in traces))
    (output / "video_frames.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n"
                                                     for row in video_frames))
    sources = {"original-attempt/history.json", "original-attempt/frame-map.json",
               "original-attempt/site-packet.json", "trace.jsonl", "video_frames.jsonl"}
    sources.update("original-attempt/" + name + ".zip" for name in VIEWS)
    sources.update("original-attempt/" + value["path"]
                   for value in sealed_site["sources"].values())
    sources.update(name + ".mkv" for name in (*VIEWS, "raw"))
    _write(output / "capture-seal.json", {
        "format": "c157964-original-native-capture-seal-v1",
        "case_id": case_id, "frame_count": len(rows),
        "events": ["capture_finished", "encoders_closed", "restoration_verified"],
        "source_sha256": {name: _sha((output / name).read_bytes()) for name in sorted(sources)},
        "physical_acceptance_claimed": False, "legal_judgment": None})
    return {"case_id": case_id, "frame_count": len(rows),
            "capture_seal_sha256": _sha((output / "capture-seal.json").read_bytes()),
            "physical_acceptance_claimed": False}
