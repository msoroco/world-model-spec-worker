"""Check staged physical source descriptors with the current pinned runtime.

Run with SCENARIO_PIPELINE_OUTPUT_ROOT set under .runtime-work/.
"""

import json
import os
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
output_root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
if not output_root.is_relative_to((REPO / ".runtime-work").resolve()):
    raise ValueError("SCENARIO_PIPELINE_OUTPUT_ROOT must be under .runtime-work")
sys.path.insert(0, str(REPO / "runtime" / "scenario_pipeline"))
from worker_exchange.native_output import assess_physical, default_descriptor  # noqa: E402


def prove_full_duration(config):
    """Exercise the actual physical assessor with joined synthetic sources."""
    output_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_root) as directory:
        attempt = Path(directory)
        (attempt / "config.json").write_text(json.dumps(config) + "\n")
        (attempt / "reverse_site_context.json").write_text(
            json.dumps({"diagnostic_fixture": True}) + "\n")
        route = config["motion_route_xy_m"]
        history, mapping, trace = [], [], []
        for index in range(900):
            point = route[min(index // 5, len(route) - 1)]
            x, y = point
            frame = 100 + index
            time = round((index + 1) / 20, 8)
            body = [[x - 1, y - 1], [x + 1, y - 1],
                    [x + 1, y + 1], [x - 1, y + 1]]
            history.append({"frame": frame, "time_s": time,
                            "body_vertices_m": body, "heading_deg": 0,
                            "velocity_mps": [-1, 0] if index < 5 else [0, 0]})
            mapping.append({"video_frame": index, "carla_frame": frame,
                            "time_s": time})
            trace.append({"frame": frame, "time_s": time,
                          "position_m": [x, y, 0]})
        for name, rows in (("reverse_history.jsonl", history),
                           ("video_frames.jsonl", mapping), ("trace.jsonl", trace)):
            (attempt / name).write_text("".join(json.dumps(row) + "\n" for row in rows))
        good = assess_physical(attempt, config)
        assert good["physical_checks"]["setup"]["status"] == "met"
        assert good["physical_checks"]["maneuver"]["status"] == "met"
        (attempt / "reverse_site_context.json").unlink()
        missing = assess_physical(attempt, config)
        assert missing["physical_checks"]["setup"]["status"] == "unverified"
        assert "reverse_site_context.json" in missing["physical_checks"]["setup"]["missing_evidence"]


def main():
    manifest = json.loads((ROOT / "alternative-offline-manifest.json").read_text())
    for entry in manifest["cases"]:
        bundle = json.loads((ROOT / entry["construction"]).read_text())
        config = json.loads(next(item["content"] for item in bundle["files"]
                                 if item["path"] == "config.json"))
        descriptor = default_descriptor(config)
        assert descriptor["criterion"] == "reverse_goal"
        assert descriptor["motion_source"] == "reverse_history.jsonl"
        assert descriptor["context_sources"] == ["reverse_site_context.json"]
        assert descriptor["goal_xy_m"] == config["motion_route_xy_m"][-1]
        prove_full_duration(config)
        print(entry["case_id"], "900-frame physical source and negative passed")


if __name__ == "__main__":
    main()
