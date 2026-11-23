"""Independent saved Native seal and four-video decode audit for C227824.

This validates source continuity and decodability. It cannot infer that a
pedestrian or signal was visible in pixels, or make a legal determination.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess

from native_recorder import SIZES
from saved_entry import CAMERAS, PACKETS, build_report


def _sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(data.encode()).hexdigest()


def _source(root, name):
    relative = PurePosixPath(name)
    if (not name or relative.is_absolute() or ".." in relative.parts or
            "." in relative.parts or "\\" in name):
        raise ValueError("unsafe sealed source path")
    path = root.joinpath(*relative.parts)
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
        raise ValueError("missing or unsafe sealed source: " + name)
    return path


def verify_seal(root):
    root = Path(root).resolve()
    seal = json.loads(_source(root, "capture-seal.json").read_text())
    if (seal.get("format") != "worker-sealed-capture" or
            seal.get("provenance_kind") != "native" or
            seal.get("diagnostic_fixture") is not False or
            seal.get("restoration", {}).get("restored") is not True):
        raise ValueError("Native capture seal or restoration invalid")
    if seal.get("events") != ["capture_finished", "encoders_closed", "restoration_verified"]:
        raise ValueError("Native capture lifecycle incomplete")
    sources = seal.get("sources")
    required = {"scene.json", "construction.json", "runner.py", "trace.jsonl", *PACKETS,
                *(name + ".mkv" for name in CAMERAS), "acquisition-provenance.json"}
    if not isinstance(sources, dict) or not required <= set(sources):
        raise ValueError("Native seal missing original sources")
    for name, expected in sources.items():
        if not isinstance(name, str) or not isinstance(expected, str) or _sha(_source(root, name)) != expected:
            raise ValueError("sealed source hash changed: " + str(name))
    if seal.get("source_digest") != _digest(sources):
        raise ValueError("sealed source tree digest changed")
    revision = seal.get("native_revision", {})
    if any(revision.get(name + "_sha256") != sources[name + (".json" if name == "construction" else ".py")]
           for name in ("construction", "runner")):
        raise ValueError("Native construction/runner revision differs")
    codes = seal.get("encoder_exit_codes")
    if not isinstance(codes, dict) or set(codes) != set(CAMERAS) or any(type(v) is not int or v != 0 for v in codes.values()):
        raise ValueError("four successful original encoders required")
    frames = seal.get("frames")
    if type(frames) is not int or frames < 3:
        raise ValueError("Native seal frame count invalid")
    provenance = json.loads(_source(root, "acquisition-provenance.json").read_text())
    if provenance.get("provenance_kind") != "native" or provenance.get("diagnostic_fixture") is not False:
        raise ValueError("Native acquisition provenance differs")
    return frames


def decode_video(path, *, frames, size):
    """Probe stream metadata and fully decode the video with installed FFmpeg."""
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                            "-show_entries", "stream=codec_name,width,height,nb_read_frames",
                            "-of", "json", str(path)], capture_output=True, text=True, timeout=1200)
    if probe.returncode:
        raise ValueError("original video probe failed: " + path.name)
    try:
        streams = json.loads(probe.stdout)["streams"]
        stream = streams[0]
        actual = (stream["codec_name"], int(stream["width"]), int(stream["height"]),
                  int(stream["nb_read_frames"]))
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("original video stream metadata missing: " + path.name) from exc
    if actual != ("ffv1", *size, frames) or len(streams) != 1:
        raise ValueError("original video codec, size or frame count differs: " + path.name)
    decoded = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path),
                              "-map", "0:v:0", "-f", "null", "-"],
                             capture_output=True, text=True, timeout=1200)
    if decoded.returncode:
        raise ValueError("full original video decode failed: " + path.name)
    return {"codec": actual[0], "width": actual[1], "height": actual[2],
            "decoded_frames": actual[3], "full_decode_passed": True,
            "source_sha256": _sha(path)}


def audit(attempt):
    root = Path(attempt).resolve()
    frames = verify_seal(root)
    report = build_report(root)
    if report["provenance_kind"] != "native" or report["sample_count"] != frames:
        raise ValueError("saved measurement and Native seal frame count differ")
    videos = {name: decode_video(_source(root, name + ".mkv"), frames=frames,
                                 size=SIZES[name]) for name in CAMERAS}
    return {"format": "worker-independent-delivery-audit", "case_id": report["case_id"],
            "native_seal_verified": True, "source_hashes_verified": True,
            "synchronized_frame_count": frames, "videos": videos,
            "entry_measurement": report["measurement"],
            "actual_pixels_verified": False, "physical_acceptance_claimed": False,
            "legal_verdict_claimed": False}
