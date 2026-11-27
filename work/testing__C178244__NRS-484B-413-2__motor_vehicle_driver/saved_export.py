"""Project SHA-verified original PNG streams into saved processing inputs."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from zipfile import ZipFile

from native_capture_contract import CAMERAS
from source_audit import audit


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export(attempt: str | Path, case_id: str, *, allow_diagnostic: bool = False) -> dict:
    root = Path(attempt)
    source_receipt = audit(root, case_id, allow_diagnostic=allow_diagnostic)
    packet = json.loads((root / "original-turn-signal.json").read_text())
    rows = packet["samples"]
    for name in ("video_frames.jsonl", "body_history.jsonl", "acquisition.json",
                 "acquisition-provenance.json", *[view + ".mkv" for view in CAMERAS]):
        if (root / name).exists():
            raise ValueError("saved source projection already exists: " + name)
    scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) / "c178244-video-frames"
    scratch.mkdir(parents=True, exist_ok=True)
    for name in CAMERAS:
        archive = root / packet["camera_archives"][name]["path"]
        with tempfile.TemporaryDirectory(prefix="c178244-frames-", dir=scratch) as temporary:
            frames = Path(temporary)
            with ZipFile(archive) as stream:
                for member in stream.namelist():
                    (frames / member).write_bytes(stream.read(member))
            output = root / (name + ".mkv")
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                            "-framerate", "20", "-start_number", str(rows[0]["frame"]),
                            "-i", str(frames / "%08d.png"), "-frames:v", str(len(rows)),
                            "-c:v", "ffv1", "-pix_fmt", "bgr0", str(output)],
                           check=True, timeout=600)
    with (root / "video_frames.jsonl").open("x") as stream:
        for index, row in enumerate(rows):
            stream.write(json.dumps({"video_frame": index, "carla_frame": row["frame"],
                                     "native_frame": row["frame"], "time_s": row["time_s"]}) + "\n")
    with (root / "body_history.jsonl").open("x") as stream:
        for row in rows:
            stream.write(json.dumps({"frame": row["frame"], "time_s": row["time_s"],
                                     "body_vertices_m": row["body_vertices_m"],
                                     "heading_deg": row["heading_deg"]}) + "\n")
    names = ("original-site.json", "original-turn-signal.json", "original-acquisition-receipt.json",
             "trace.jsonl", "video_frames.jsonl", "body_history.jsonl",
             "road.xodr", "carla_recorder.log", *[name + ".mkv" for name in CAMERAS])
    (root / "acquisition.json").write_text(json.dumps({name: {
        "kind": "original_native" if not allow_diagnostic else "diagnostic_fixture",
        "sha256": _sha(root / name)} for name in names}, indent=2, sort_keys=True) + "\n")
    (root / "acquisition-provenance.json").write_text(json.dumps({
        "diagnostic_fixture": allow_diagnostic,
        "physical_acceptance_claimed": False, "source_decode_receipt": source_receipt},
        indent=2, sort_keys=True) + "\n")
    return {"format": "turn-signal-saved-export", "case_id": case_id,
            "source_decode_receipt": source_receipt,
            "video_frame_map_sha256": _sha(root / "video_frames.jsonl"),
            "body_history_sha256": _sha(root / "body_history.jsonl"),
            "four_video_sha256": {name: _sha(root / (name + ".mkv")) for name in CAMERAS},
            "physical_acceptance_claimed": False}
