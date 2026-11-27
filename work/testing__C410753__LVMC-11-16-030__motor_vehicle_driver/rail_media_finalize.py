"""Encode and verify original railway camera frames after Native capture exits."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from rail_native_capture import CAMERAS
from rail_saved_measurement import _source, verify_camera_row


def _run(command, timeout):
    result = subprocess.run(command, capture_output=True, timeout=timeout)
    if result.returncode:
        raise ValueError("original rail media command failed: " +
                         result.stderr.decode("utf-8", "replace")[-500:])
    return result.stdout


def encode_camera(root, camera, first_frame, frame_count, dimensions, output):
    """Encode a contiguous original PNG sequence and fully decode the FFV1 result."""
    root = Path(root).resolve()
    output = Path(output)
    if (not isinstance(camera, str) or not camera.isidentifier() or
            type(first_frame) is not int or first_frame < 0 or
            type(frame_count) is not int or frame_count < 1 or
            not isinstance(dimensions, tuple) or len(dimensions) != 2 or
            any(type(value) is not int or value < 1 for value in dimensions) or
            output.exists() or output.is_symlink()):
        raise ValueError("original rail media profile invalid")
    folder = root / "original-cameras" / camera
    for frame in range(first_frame, first_frame + frame_count):
        if not (folder / f"{frame:08d}.png").is_file():
            raise ValueError("original rail camera sequence incomplete")
    pattern = str(folder / "%08d.png")
    try:
        _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
              "-framerate", "20", "-start_number", str(first_frame),
              "-i", pattern, "-frames:v", str(frame_count),
              "-c:v", "ffv1", "-level", "3", "-g", "1", str(output)], 600)
        probe = json.loads(_run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                 "-count_frames", "-show_entries",
                                 "stream=nb_read_frames,codec_name,width,height,r_frame_rate",
                                 "-of", "json", str(output)], 120))
        streams = probe.get("streams", [])
        if len(streams) != 1:
            raise ValueError("original rail media stream count differs")
        stream = streams[0]
        if (stream.get("codec_name") != "ffv1" or
                (stream.get("width"), stream.get("height")) != dimensions or
                stream.get("r_frame_rate") != "20/1" or
                int(stream.get("nb_read_frames", -1)) != frame_count):
            raise ValueError("original rail media profile differs")
        _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
              "-i", str(output), "-f", "null", "-"], 600)
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return {"path": output.name,
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "frames": frame_count, "codec": "ffv1",
            "width": dimensions[0], "height": dimensions[1], "fps": 20,
            "full_decode": True}


def finalize(root, packet, case_id):
    """Require the sealed original receipt and encode all four exact 900-frame views."""
    root = Path(root).resolve()
    receipt_path = root / "native-rail-receipt.json"
    if not receipt_path.is_file() or receipt_path.is_symlink():
        raise ValueError("original rail receipt missing")
    receipt = json.loads(receipt_path.read_text())
    if (receipt.get("case_id") != case_id or receipt.get("capture_kind") != "original_native" or
            receipt.get("frame_count") != 900 or receipt.get("fps") != 20):
        raise ValueError("original rail receipt identity or profile differs")
    retained_packet = json.loads(_source(root, receipt.get("packet")).read_text())
    if retained_packet != packet:
        raise ValueError("reviewed rail packet differs from original capture")
    rows = json.loads(_source(root, receipt.get("camera_map")).read_text())
    frames = json.loads(_source(root, receipt.get("frames")).read_text())
    if len(rows) != 900 or len(frames) != 900:
        raise ValueError("original rail camera/frame count differs")
    first = frames[0]["original_frame"]
    for index, (row, frame) in enumerate(zip(rows, frames)):
        expected = first + index
        if frame.get("original_frame") != expected:
            raise ValueError("original rail frame sequence differs")
        verify_camera_row(root, row, expected)
    media = {}
    created = []
    try:
        for camera, dimensions in CAMERAS.items():
            output = root / (camera + ".mkv")
            media[camera] = encode_camera(root, camera, first, 900, dimensions,
                                          output)
            created.append(output)
    except Exception:
        for output in created:
            output.unlink(missing_ok=True)
        raise
    result = {"case_id": case_id, "source_receipt_sha256":
              hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
              "original_frame_count": 900, "media": media,
              "physical_completion_confirmed": False, "legal_conclusion": None}
    (root / "rail-media-receipt.json").write_text(json.dumps(result, indent=2,
                                                          sort_keys=True) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    args = parser.parse_args()
    receipt_path = args.attempt / "native-rail-receipt.json"
    if not receipt_path.is_file() or receipt_path.is_symlink():
        raise ValueError("original rail receipt missing")
    receipt = json.loads(receipt_path.read_text())
    packet = json.loads(_source(args.attempt, receipt.get("packet")).read_text())
    result = finalize(args.attempt, packet, args.case_id)
    print(json.dumps({"case_id": result["case_id"], "media_ready": True}))


if __name__ == "__main__":
    main()
