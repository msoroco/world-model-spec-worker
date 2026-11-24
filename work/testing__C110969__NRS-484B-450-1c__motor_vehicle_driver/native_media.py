"""Bind four original camera PNG streams to each Native 20 Hz frame.

The caller's camera adapter must return bytes from four actual sensor callbacks
for the just-ticked Native frame. This writer validates and seals those bytes;
it cannot establish that a body or sign is physically visible in the images.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import zipfile

from PIL import Image

from intersection_observables import _require


CAMERAS = {
    "overview": (1920, 1080),
    "approach": (1280, 720),
    "reference_corner": (1280, 720),
    "driver_reference": (1280, 720),
}


class NativeMediaWriter:
    def __init__(self, output: Path, camera_adapter):
        self.output = Path(output)
        self.adapter = camera_adapter
        self.archives = {}
        self.rows = []
        self.closed = False
        self.output.mkdir(parents=True, exist_ok=True)
        for camera in CAMERAS:
            self.archives[camera] = zipfile.ZipFile(
                self.output / (camera + ".zip"), "w", compression=zipfile.ZIP_STORED
            )

    def capture(self, snapshot, actor):
        _require(not self.closed, "media writer already closed")
        frame = snapshot.frame
        returned = self.adapter.capture(snapshot, actor)
        _require(isinstance(returned, dict) and set(returned) == set(CAMERAS),
                 "four exact camera callbacks required")
        row = {"frame": frame, "time_s": snapshot.timestamp.elapsed_seconds,
               "sources": {}}
        validated = {}
        for camera, expected_size in CAMERAS.items():
            sample = returned[camera]
            _require(isinstance(sample, dict) and sample.get("frame") == frame and
                     sample.get("source") == "original_native_camera_callback" and
                     isinstance(sample.get("png"), bytes),
                     "camera callback frame/source mismatch: " + camera)
            raw = sample["png"]
            try:
                with Image.open(io.BytesIO(raw)) as image:
                    image.verify()
                with Image.open(io.BytesIO(raw)) as image:
                    _require(image.format == "PNG" and image.size == expected_size,
                             "camera PNG format/size mismatch: " + camera)
                    image.load()
            except (OSError, ValueError) as exc:
                raise ValueError("camera PNG decode failed: " + camera) from exc
            validated[camera] = raw
        for camera, raw in validated.items():
            member = f"{frame:08d}.png"
            self.archives[camera].writestr(member, raw)
            row["sources"][camera] = {"archive": camera + ".zip", "member": member,
                                       "sha256": hashlib.sha256(raw).hexdigest()}
        self.rows.append(row)

    def close(self, *, case_id: str, run_id: str, expected_frames: list[int]):
        _require(not self.closed, "media writer already closed")
        self.closed = True
        for archive in self.archives.values():
            archive.close()
        _require([row["frame"] for row in self.rows] == expected_frames,
                 "camera/frame-map join differs from original trace")
        archives = {}
        for camera in CAMERAS:
            path = self.output / (camera + ".zip")
            archives[camera] = {"path": path.name,
                                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        manifest = {"case_id": case_id, "native_run_id": run_id, "fps": 20,
                    "frame_count": len(self.rows), "frame_map": self.rows,
                    "archives": archives, "physical_visibility_reviewed": False}
        raw = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
        (self.output / "media-manifest.json").write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()

    def abort(self):
        if not self.closed:
            self.closed = True
            for archive in self.archives.values():
                archive.close()


def audit_saved_media(output: Path, *, case_id: str, run_id: str,
                      expected_frames: list[int]):
    """Reopen every original PNG and archive; reject stale or missing sources."""
    output = Path(output)
    manifest_path = output / "media-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    _require(manifest.get("case_id") == case_id and
             manifest.get("native_run_id") == run_id and
             manifest.get("fps") == 20 and
             manifest.get("frame_count") == len(expected_frames),
             "media identity/rate/count differs")
    rows = manifest.get("frame_map", [])
    _require([row.get("frame") for row in rows] == expected_frames,
             "media frame-map differs from original trace")
    _require(set(manifest.get("archives", {})) == set(CAMERAS),
             "four camera archives required")
    for camera, dimensions in CAMERAS.items():
        info = manifest["archives"][camera]
        _require(info.get("path") == camera + ".zip", "camera archive path differs")
        path = output / info["path"]
        _require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == info.get("sha256"),
                 "camera archive seal differs: " + camera)
        with zipfile.ZipFile(path) as archive:
            expected_members = [f"{frame:08d}.png" for frame in expected_frames]
            _require(archive.namelist() == expected_members,
                     "camera archive members differ: " + camera)
            for row, member in zip(rows, expected_members):
                source = row.get("sources", {}).get(camera, {})
                _require(source.get("archive") == path.name and source.get("member") == member,
                         "camera frame-map source differs: " + camera)
                data = archive.read(member)
                _require(hashlib.sha256(data).hexdigest() == source.get("sha256"),
                         "camera frame hash differs: " + camera)
                with Image.open(io.BytesIO(data)) as image:
                    _require(image.format == "PNG" and image.size == dimensions,
                             "camera decoded dimensions differ: " + camera)
                    image.load()
    return {"case_id": case_id, "native_run_id": run_id,
            "frame_count": len(rows), "decoded_camera_frames": 4 * len(rows),
            "media_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "physical_visibility_reviewed": False}


def audit_saved_acquisition(output: Path):
    """Join a sealed original trace to complete saved media without trusting labels."""
    output = Path(output)
    sources = json.loads((output / "source-manifest.json").read_text())
    for key, expected in (("trace", "trace.json"), ("media", "media-manifest.json")):
        info = sources.get(key, {})
        _require(info.get("path") == expected, "source manifest path differs: " + key)
        path = output / expected
        _require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == info.get("sha256"),
                 "source manifest seal differs: " + key)
    trace = json.loads((output / "trace.json").read_text())
    _require(trace.get("case_id") == sources.get("case_id") and
             trace.get("native_run_id") == sources.get("native_run_id"),
             "trace/source identity differs")
    frames = [sample.get("frame") for sample in trace.get("samples", [])]
    _require(frames and all(isinstance(frame, int) for frame in frames),
             "original trace frames missing")
    return audit_saved_media(output, case_id=sources["case_id"],
                             run_id=sources["native_run_id"], expected_frames=frames)
