"""Exercise the pinned four-view CPU composition with exact red-X camera names."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from worker_exchange.media import audit, check_four_view_sources, compose_four_views


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
NAMES = ("overview", "approach", "reference_corner", "driver_reference")


def main():
    runtime_root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if not runtime_root.is_relative_to((REPO / ".runtime-work").resolve()):
        raise ValueError("pipeline output root must stay under .runtime-work")
    output = REPO / ".runtime-work" / "c147332-media-v1"
    if output.exists():
        raise ValueError("retain previous media proof; choose a fresh version")
    output.mkdir(parents=True)
    sources = {}
    for name in NAMES:
        width, height = (1920, 1080) if name == "overview" else (1280, 720)
        target = output / (name + ".mkv")
        subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                        "-f", "lavfi", "-i", f"color=c=red:s={width}x{height}:r=20",
                        "-frames:v", "2", "-an", "-c:v", "ffv1", "-threads", "1",
                        str(target)], check=True, timeout=120)
        sources[name] = target
    mapping = output / "video_frames.jsonl"
    mapping.write_text("".join(json.dumps({"video_frame": index,
                                            "carla_frame": index + 1,
                                            "time_s": (index + 1) / 20}) + "\n"
                               for index in range(2)))
    check_four_view_sources(sources)
    receipt = compose_four_views(sources, mapping, output / "raw.mkv")
    decoded = audit(output / "raw.mkv", 2, mapping_sha256=receipt["frame_map_sha256"])
    if not decoded["passed"] or decoded["frames"] != 2:
        raise AssertionError("pinned four-view full decode failed")
    print(json.dumps({"four_source_names": NAMES, "composed_frames": decoded["frames"],
                      "dimensions": decoded["dimensions"], "diagnostic_only": True}))
    missing = dict(sources)
    missing["overhead_signal"] = missing.pop("reference_corner")
    try:
        check_four_view_sources(missing)
    except ValueError as error:
        if "Four named original camera sources" not in str(error):
            raise
        print("legacy overhead_signal filename rejected by pinned four-view contract")
    else:
        raise AssertionError("legacy camera name was accepted")


if __name__ == "__main__":
    main()
