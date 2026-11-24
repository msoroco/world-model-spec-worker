"""Independent full-decode audit of a sealed four-camera Native acquisition.

The audit checks saved source integrity and timing. It cannot establish that a
vehicle or road feature is visible in the pixels or that the law was obeyed.
"""

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from saved_left_turn import ASSIGNMENT_ID

CAMERAS = ("front", "rear", "left", "right")


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(attempt, *, case_id, allow_diagnostic=False):
    """Reopen and decode all original pixels, joined to the sealed actor trace."""
    attempt = Path(attempt)
    receipt_path = attempt / "acquisition-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if not case_id.startswith(ASSIGNMENT_ID + "__") or (receipt.get("assignment_id"), receipt.get("case_id")) != (ASSIGNMENT_ID, case_id):
        raise ValueError("exact acquisition identity mismatch")
    if receipt.get("diagnostic_fixture") and not allow_diagnostic:
        raise ValueError("diagnostic fixture is not delivery evidence")
    if receipt.get("simulator_frame_rate_hz") != 20 or receipt.get("camera_names") != list(CAMERAS):
        raise ValueError("20 Hz four-camera acquisition required")
    trace_path = attempt / "original-trace.jsonl"
    frame_map_path = attempt / "original-frame-map.json"
    map_path = attempt / "original-map.json"
    for path, key in ((trace_path, "trace_sha256"), (frame_map_path, "frame_map_sha256"), (map_path, "map_sha256")):
        if _sha(path) != receipt.get(key):
            raise ValueError("sealed " + key + " bytes changed")
    trace = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line]
    frame_map = json.loads(frame_map_path.read_text(encoding="utf-8"))
    if frame_map.get("case_id") != case_id or not isinstance(frame_map.get("frames"), list):
        raise ValueError("camera frame map case mismatch")
    rows = frame_map["frames"]
    if len(trace) != len(rows) or len(rows) != receipt.get("frame_count") or not rows:
        raise ValueError("saved frame count mismatch")
    dimensions = {}
    seen_paths = set()
    previous = None
    for actor, row in zip(trace, rows):
        frame, time_s = actor.get("frame"), actor.get("time_s")
        if not isinstance(frame, int) or not isinstance(time_s, (int, float)) or row.get("frame") != frame or row.get("time_s") != time_s:
            raise ValueError("actor and camera frame/time join mismatch")
        if previous is not None and (frame != previous[0] + 1 or abs(time_s - previous[1] - 0.05) > 0.002):
            raise ValueError("saved frame order or 20 Hz cadence mismatch")
        previous = frame, time_s
        cameras = row.get("cameras")
        if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS):
            raise ValueError("four original cameras required per frame")
        for camera in CAMERAS:
            entry = cameras[camera]
            relative = Path(entry["path"])
            if relative.is_absolute() or ".." in relative.parts or relative.parts[:1] != ("original-frames",):
                raise ValueError("camera source path escapes original frame directory")
            if str(relative) in seen_paths:
                raise ValueError("camera source path reused")
            seen_paths.add(str(relative))
            if relative.name != f"{frame:09d}-{camera}.png":
                raise ValueError("camera source name does not match frame")
            path = attempt / relative
            if not path.is_file() or _sha(path) != entry.get("sha256"):
                raise ValueError("original camera source missing or changed")
            try:
                with Image.open(path) as image:
                    if image.format != "PNG" or image.mode not in ("RGB", "RGBA"):
                        raise ValueError("original camera format is not RGB PNG")
                    image.load()
                    if min(image.size) <= 0:
                        raise ValueError("original camera dimensions invalid")
                    size = tuple(image.size)
            except (UnidentifiedImageError, OSError) as exc:
                raise ValueError("original camera image cannot fully decode") from exc
            if camera in dimensions and dimensions[camera] != size:
                raise ValueError("camera dimensions changed within saved stream")
            dimensions[camera] = size
    return {"assignment_id": ASSIGNMENT_ID, "case_id": case_id,
            "frame_count": len(rows), "decoded_images": len(seen_paths),
            "camera_dimensions": {name: list(dimensions[name]) for name in CAMERAS},
            "source_bindings": {"receipt_sha256": _sha(receipt_path),
                                "trace_sha256": _sha(trace_path),
                                "frame_map_sha256": _sha(frame_map_path)},
            "physical_visibility": "unverified", "legal_judgment": "unresolved"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow-diagnostic", action="store_true")
    args = parser.parse_args()
    result = audit(args.attempt, case_id=args.case, allow_diagnostic=args.allow_diagnostic)
    output = Path(args.output)
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
