"""Saved-only four-camera media decode and source custody for Native attempts."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

from cycle_lane_original import VIEWS, _sha, audit


def _checked_video(path: Path) -> dict:
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-count_frames", "-show_entries",
                            "stream=codec_type,width,height,avg_frame_rate,nb_read_frames",
                            "-of", "json", str(path)], capture_output=True, text=True,
                           timeout=120, check=False)
    if probe.returncode:
        raise ValueError("camera probe failed: " + path.name)
    try:
        streams = json.loads(probe.stdout)["streams"]
        stream = streams[0]
        frames = int(stream["nb_read_frames"])
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("camera frame metadata missing: " + path.name) from exc
    if (len(streams) != 1 or stream.get("codec_type") != "video" or
            frames != 900 or stream.get("avg_frame_rate") != "20/1" or
            int(stream.get("width", 0)) < 64 or int(stream.get("height", 0)) < 64):
        raise ValueError("camera 45-second 20 Hz profile mismatch: " + path.name)
    decode = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path),
                             "-map", "0:v:0", "-f", "null", "-"],
                            capture_output=True, text=True, timeout=120, check=False)
    if decode.returncode:
        raise ValueError("camera full decode failed: " + path.name)
    return {"sha256": _sha(path), "frame_count": frames,
            "width": int(stream["width"]), "height": int(stream["height"]),
            "full_decode": True}


def audit_delivery(attempt_root: str | Path, reviewed_site_sha256: str,
                   reviewed_exception_sha256: str,
                   reviewed_vehicle_sha256: str) -> dict:
    root = Path(attempt_root).resolve()
    measurement = audit(root, reviewed_site_sha256, reviewed_exception_sha256,
                        reviewed_vehicle_sha256)
    seal = json.loads((root / "attempt-source.json").read_text(encoding="utf-8"))
    media = {}
    for view in VIEWS:
        reference = seal["cameras"][view]
        path = root / reference["path"]
        if not path.resolve().is_relative_to(root) or _sha(path) != reference["sha256"]:
            raise ValueError("camera changed: " + view)
        media[view] = _checked_video(path)
    return {"format": "cycle-lane-delivery-audit-v1",
            "case_id": measurement["case_id"],
            "source_kind": "original_native", "measurement": measurement,
            "media": media,
            "checks": {"native_source": True, "all_participants": True,
                       "time_join": True, "full_video_decode": True,
                       "actual_pixels": False, "physical_completion": False},
            "physical_acceptance_claimed": False, "legal_verdict": None}
