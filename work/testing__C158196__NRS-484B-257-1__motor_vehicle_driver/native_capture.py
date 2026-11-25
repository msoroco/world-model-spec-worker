"""Seal observed C158196 Native ticks and four camera frame identities.

The caller owns CARLA actors and calls ``tick`` after each synchronous world
advance. This module accepts no commanded or predicted observation as a frame.
It leaves the source packet in the attempt for saved-only measurement.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import shutil
import subprocess
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

from PIL import Image

from construction import verify_site_sources
from native_observation import derive
from nearest_view import REQUIRED_SOURCES, measure, verify_source_bytes
from signal_exception import measure as measure_signal

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
DIMENSIONS = ((1920, 1080), (1280, 720), (1280, 720), (1280, 720))


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sealed_source(root: Path, name: str, entry: dict) -> dict:
    if not isinstance(entry, dict) or entry.get("origin") != "original_native":
        raise ValueError(name + " original Native source required")
    relative = entry.get("path")
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError(name + " original source path missing")
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError(name + " original source bytes missing")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if not path.stat().st_size or digest != entry.get("sha256"):
        raise ValueError(name + " original source hash mismatch")
    return {"path": relative, "sha256": digest}


def _camera_row(snapshot: dict, frame: int) -> dict:
    cameras = snapshot.get("cameras")
    if not isinstance(cameras, dict) or set(cameras) != set(VIEWS):
        raise ValueError("four original camera frames required")
    row = {}
    for name, dimensions in zip(VIEWS, DIMENSIONS):
        image = cameras[name]
        if (not isinstance(image, dict) or image.get("frame") != frame or
                (image.get("width"), image.get("height")) != dimensions or
                image.get("source_kind") != "original_native_camera"):
            raise ValueError(name + " original camera frame differs")
        encoded = image.get("png_bytes")
        if not isinstance(encoded, bytes) or not encoded:
            raise ValueError(name + " original camera PNG bytes missing")
        with Image.open(io.BytesIO(encoded)) as pixels:
            if pixels.format != "PNG" or pixels.size != dimensions:
                raise ValueError(name + " original camera PNG dimensions differ")
            pixels.verify()
        digest = hashlib.sha256(encoded).hexdigest()
        row[name] = digest
    return row


def seal(site: dict, case: str, site_root: Path, attempt: Path, tick, *, frames: int = 900) -> dict:
    """Validate one original 20 Hz stream; never report physical acceptance."""
    site_root = Path(site_root).resolve()
    attempt = Path(attempt).resolve()
    if frames != 900:
        raise ValueError("selected 45 second original duration changed")
    selected = verify_site_sources(site, case, site_root)
    if not isinstance(site.get("geometry"), dict):
        raise ValueError("surveyed Native geometry missing")
    source_entries = site.get("measurement_sources")
    expected_sources = (set(REQUIRED_SOURCES) - {"signal_state_readback"}
                        if case == "active_signal_exception" else set(REQUIRED_SOURCES))
    if not isinstance(source_entries, dict) or set(source_entries) != expected_sources:
        raise ValueError("original measurement source inventory differs")
    sources = {name: _sealed_source(site_root, name, source_entries[name])
               for name in expected_sources}
    source_paths = [entry["path"] for entry in sources.values()]
    if (len(source_paths) != len(set(source_paths)) or
            set(source_paths) & {"nearest-view-original.json", "camera-frame-map.json"}):
        raise ValueError("original measurement sources duplicate or shadow capture")
    attempt.mkdir(parents=True, exist_ok=True)
    packet_path = attempt / "nearest-view-original.json"
    receipt_path = attempt / "camera-frame-map.json"
    camera_receipt_path = attempt / "camera-sources.json"
    archive_paths = {name: attempt / (name + ".png.zip") for name in VIEWS}
    if (packet_path.exists() or receipt_path.exists() or
            camera_receipt_path.exists() or any(p.exists() for p in archive_paths.values())):
        raise ValueError("original capture already sealed")
    for entry in sources.values():
        source = (site_root / entry["path"]).resolve()
        destination = (attempt / entry["path"]).resolve()
        if not destination.is_relative_to(attempt):
            raise ValueError("original source escapes attempt")
        if destination != source:
            if destination.exists():
                raise ValueError("original measurement source would be overwritten")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            if hashlib.sha256(destination.read_bytes()).hexdigest() != entry["sha256"]:
                raise ValueError("original source changed during capture setup")
    rows = []
    raw_rows = []
    cameras = []
    signal_rows = []
    first_frame = None
    first_time = None
    archives = {name: ZipFile(path, "w", compression=ZIP_STORED)
                for name, path in archive_paths.items()}
    try:
        for index in range(frames):
            snapshot = tick(index)
            if not isinstance(snapshot, dict) or snapshot.get("source_kind") != "original_native_tick":
                raise ValueError("original Native tick missing")
            raw = snapshot.get("observation")
            if not isinstance(raw, dict):
                raise ValueError("original Native observation missing")
            observed = derive(raw, site["geometry"],
                              expect_signal=case == "active_signal_exception")
            frame, time = observed["frame"], observed["time_s"]
            if first_frame is None:
                first_frame, first_time = frame, time
            if frame != first_frame + index or abs(time - first_time - index / 20) > 0.001:
                raise ValueError("original Native ticks are not contiguous 20 Hz")
            camera_hashes = _camera_row(snapshot, frame)
            for name in VIEWS:
                archives[name].writestr(f"{frame:08d}.png",
                                         snapshot["cameras"][name]["png_bytes"])
            cameras.append({"frame": frame, "pixel_sha256": camera_hashes})
            if case == "active_signal_exception":
                signal = snapshot.get("signal")
                if (not isinstance(signal, dict) or signal.get("frame") != frame or
                        signal.get("source_kind") != "original_native_signal_readback" or
                        signal.get("governs_ego_approach") is not True or
                        signal.get("state") not in ("red", "yellow", "green")):
                    raise ValueError("original governing signal frame missing")
                signal_rows.append({"frame": frame, "state": signal["state"],
                                    "governs_ego_approach": True})
            rows.append(observed)
            raw_rows.append(raw)
    except BaseException:
        for archive in archives.values():
            archive.close()
        for path in archive_paths.values():
            path.unlink(missing_ok=True)
        raise
    for archive in archives.values():
        archive.close()
    if case == "active_signal_exception":
        signal_path = attempt / "signal-state-original.json"
        if signal_path.exists():
            raise ValueError("original signal source already sealed")
        signal_body = (json.dumps({"source_kind": "original_native_signal_readback",
            "device_kind": "traffic_control_signal",
            "governs_ego_approach": True,
            "observed_frame_ids": [row["frame"] for row in signal_rows],
            "observed_signal_states": signal_rows},
            sort_keys=True, separators=(",", ":")) + "\n").encode()
        if len(signal_body) > 2 * 1024 * 1024:
            raise ValueError("original signal source exceeds two MiB")
        signal_path.write_bytes(signal_body)
        sources["signal_state_readback"] = {"path": signal_path.name,
                                             "sha256": hashlib.sha256(signal_body).hexdigest()}
    packet = {"case_id": site.get("case_id"), "context": site.get("context"),
              "site_source_hashes": selected["source_hashes"],
              "sources": sources, "frames": rows, "raw_frames": raw_rows}
    if packet["case_id"] != site.get("assignment_id", "") + "__" + case:
        raise ValueError("original site belongs to another exact case")
    if not isinstance(packet["context"], dict):
        raise ValueError("original site context missing")
    # Measurement proves the packet is processable, not that a judgment is met.
    measured = (measure_signal(packet, attempt) if case == "active_signal_exception"
                else measure(packet))
    body = (json.dumps(packet, sort_keys=True, separators=(",", ":")) + "\n").encode()
    video_map = (json.dumps(cameras, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(body) > 2 * 1024 * 1024 or len(video_map) > 2 * 1024 * 1024:
        raise ValueError("original textual source exceeds two MiB")
    packet_path.write_bytes(body)
    receipt_path.write_bytes(video_map)
    archive_refs = {name: {"path": archive_paths[name].name,
                            "sha256": _sha(archive_paths[name]),
                            "frame_count": frames, "dimensions": list(dimensions)}
                    for name, dimensions in zip(VIEWS, DIMENSIONS)}
    camera_receipt_path.write_text(json.dumps({"format": "c158196-original-four-camera-sources-v1",
        "case_id": packet["case_id"], "frame_map_sha256": hashlib.sha256(video_map).hexdigest(),
        "sources": archive_refs, "physical_acceptance_claimed": False},
        sort_keys=True) + "\n")
    trace_rows = []
    frame_rows = []
    interaction_rows = []
    for index, (raw, observed) in enumerate(zip(raw_rows, rows)):
        heading = raw.get("ego_heading_deg")
        height = raw.get("ego_height_m")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or
               not math.isfinite(value) for value in (heading, height)):
            raise ValueError("original Native heading and height readback required")
        body_corners = raw["ego_body_xy_m"]
        center = [sum(c[0] for c in body_corners) / 4,
                  sum(c[1] for c in body_corners) / 4]
        frame, time = observed["frame"], observed["time_s"]
        trace_rows.append({"frame": frame, "time_s": time,
                           "position": {"x": center[0], "y": center[1], "z": height},
                           "heading_deg": heading, "speed_mps": observed["ego_speed_mps"]})
        frame_rows.append({"video_frame": index, "carla_frame": frame,
                           "native_frame": frame, "time_s": time})
        interaction_rows.append({"frame": frame, "time_s": time,
                                 "ego": {"body_vertices_m": [[x, y, height] for x, y in body_corners]}})
    text_sources = {"trace.jsonl": trace_rows, "video_frames.jsonl": frame_rows,
                    "interaction_history.jsonl": interaction_rows}
    for name, records in text_sources.items():
        path = attempt / name
        if path.exists():
            raise ValueError("original capture source already exists: " + name)
        path.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in records))
    context_path = attempt / "control_context.json"
    if context_path.exists():
        raise ValueError("original control context already exists")
    context_path.write_text(json.dumps({"source_kind": "original_native_control_context",
        "intersection_polygon_xy_m": site["geometry"]["intersection_polygon_xy_m"],
        "site_source_hashes": selected["source_hashes"]}, separators=(",", ":")) + "\n")
    verify_source_bytes(packet, attempt)
    return {"case_id": packet["case_id"], "frames": frames,
            "packet_sha256": hashlib.sha256(body).hexdigest(),
            "camera_frame_map_sha256": hashlib.sha256(video_map).hexdigest(),
            "camera_sources_sha256": hashlib.sha256(camera_receipt_path.read_bytes()).hexdigest(),
            "measurement": measured, "physical_acceptance_claimed": False,
            "legal_verdict": None}


def encode_original_cameras(attempt: Path) -> dict:
    """Encode only sealed original PNG frame bytes after CARLA has been restored."""
    attempt = Path(attempt).resolve()
    receipt = json.loads((attempt / "camera-sources.json").read_text())
    if receipt.get("format") != "c158196-original-four-camera-sources-v1":
        raise ValueError("original four-camera source receipt required")
    outputs = {}
    for name in VIEWS:
        source = receipt["sources"][name]
        archive = attempt / source["path"]
        target = attempt / (name + ".mkv")
        if target.exists():
            raise ValueError(name + " original camera video already exists")
        if _sha(archive) != source["sha256"]:
            raise ValueError(name + " original camera archive changed before encoding")
        command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                   "-f", "image2pipe", "-framerate", "20", "-c:v", "png",
                   "-i", "pipe:0", "-an", "-c:v", "ffv1", "-threads", "1",
                   str(target)]
        process = subprocess.Popen(command, stdin=subprocess.PIPE,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            with ZipFile(archive) as images:
                names = images.namelist()
                if len(names) != 900 or source["frame_count"] != 900:
                    raise ValueError(name + " original camera archive incomplete")
                for frame in names:
                    process.stdin.write(images.read(frame))
            process.stdin.close()
            error = process.stderr.read().decode(errors="replace")
            code = process.wait()
            if code or not target.is_file() or not target.stat().st_size:
                raise ValueError(name + " camera encoder failed: " + error[-1000:])
        except BaseException:
            process.kill()
            process.wait()
            target.unlink(missing_ok=True)
            raise
        outputs[name] = {"path": target.name,
                         "sha256": _sha(target),
                         "source_archive_sha256": source["sha256"],
                         "frame_count": 900, "physical_acceptance_claimed": False}
    path = attempt / "camera-video-encoding.json"
    if path.exists():
        raise ValueError("camera encoding receipt already exists")
    path.write_text(json.dumps({"format": "c158196-original-camera-encoding-v1",
                                "sources": outputs, "physical_acceptance_claimed": False},
                               sort_keys=True) + "\n")
    return outputs
