"""Synthetic CPU proof of source binding and full video decoding in delivery audit."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from delivery_audit import CAMERAS, audit

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    if not args.case.startswith(ROOT.name + "__"):
        raise ValueError("audit selects another assignment")
    output = Path(args.output).resolve()
    if not output.is_relative_to(REPO / ".runtime-work"):
        raise ValueError("audit scratch belongs under .runtime-work")
    pipeline = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
    if not pipeline.is_relative_to(REPO / ".runtime-work"):
        raise ValueError("export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
    output.mkdir(parents=True, exist_ok=False)
    provenance = {"diagnostic_fixture": True, "physical_acceptance_claimed": False,
                  "scope": "synthetic 900-frame CPU decoder and source-integrity proof"}
    (output / "fixture-provenance.json").write_text(json.dumps(provenance) + "\n")
    source_video = output / "overview.mkv"
    subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                    "-f", "lavfi", "-i", "color=c=black:s=64x64:r=20",
                    "-frames:v", "900", "-an", "-c:v", "ffv1", "-threads", "1",
                    str(source_video)], check=True, timeout=120)
    streams = {}
    for name in CAMERAS:
        path = output / (name + ".mkv")
        if path != source_video:
            shutil.copyfile(source_video, path)
        streams[name] = {"path": path.name, "sha256": sha(path)}
    arms = ["west", "north", "east"]
    census = output / "actor-census.jsonl"
    census.write_text("".join(json.dumps({"frame": frame, "entering_arms": arms,
                                          "actors": []}) + "\n" for frame in range(900)))
    receipt = {"case_id": args.case, "map_hash": "d" * 64,
               "diagnostic_fixture": True, "capture_kind": "synthetic_fixture",
               "fps": 20, "duration_s": 45, "streams": streams,
               "frame_ids": list(range(900)), "candidate": "primary",
               "entering_arms": arms, "actor_census_sha256": sha(census)}
    measurement = {"case_id": args.case, "map_hash": "d" * 64,
                   "approach_frame_ids": list(range(5)), "traversal_frame_ids": [5, 6, 7, 8],
                   "source_sha256": {"diagnostic_packet": "e" * 64}}
    if args.negative:
        (output / "overview.mkv").write_bytes(b"tampered source")
    result = audit(receipt, measurement, output, args.case, full_video_decode=True)
    print(json.dumps({"scope": "synthetic_cpu_audit_probe", "result": result}, sort_keys=True))


if __name__ == "__main__":
    main()
