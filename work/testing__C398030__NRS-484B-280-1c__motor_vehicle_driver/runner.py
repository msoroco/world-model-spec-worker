"""Exact school-setting pedestrian construction entrypoint.

The observation trigger is an instrumented scripted-driver input. It is not a
claim about human perception or a legal proper-caution determination.
"""
import argparse
import json
import math
from pathlib import Path

from road_scene import controller


ROOT = Path(__file__).resolve().parent


def load_scene(path=None):
    scene = json.loads(Path(path or ROOT / "scene.json").read_text())
    identity = (scene.get("law_id"), scene.get("cell_id"), scene.get("actor"),
                scene.get("layout"), scene.get("maneuver"), scene.get("control"))
    expected = ("NRS-484B-280-1c", "C398030", "motor_vehicle_driver",
                "school_zone", "travel", "school")
    if identity != expected:
        raise ValueError("wrong frozen law or cell identity")
    if scene.get("response_policy") not in ("prompt_brake", "deferred_brake"):
        raise ValueError("unsupported response policy")
    if scene.get("rate_hz") != 20 or scene.get("duration_s") != 30:
        raise ValueError("capture profile differs")
    if scene.get("ego_spawn_offset_m") not in (20, 23):
        raise ValueError("unsupported school approach spawn offset")
    if not (scene["ego_start_xy_m"][0] < scene["pedestrian_start_xy_m"][0]
            < scene["ego_end_xy_m"][0]):
        raise ValueError("ego approach does not reach pedestrian road position")
    if any(not isinstance(value, (int, float)) or not math.isfinite(value)
           for point in (scene["ego_start_xy_m"], scene["ego_end_xy_m"],
                         scene["pedestrian_start_xy_m"], scene["pedestrian_end_xy_m"])
           for value in point):
        raise ValueError("nonfinite authored route")
    if scene.get("case_id") != ROOT.name + "__" + scene["response_policy"]:
        # In a materialized bundle ROOT is a temporary path. Use config there.
        config_path = ROOT / "config.json"
        if not config_path.is_file() or json.loads(config_path.read_text()).get("selected_case_id") != scene.get("case_id"):
            raise ValueError("wrong exact case identity")
    return scene


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    scene = load_scene()
    if args.check:
        print(json.dumps({"source_gated_site_at_capture": True,
                          "original_school_markers_required": True,
                          "scripted_driver_event_not_human_observation": True,
                          "legal_verdict_claimed": False}))
        return
    if not args.output_dir:
        parser.error("--output-dir is required for Native acquisition")
    from native_capture import run_native
    run_native(scene, Path(args.output_dir), args.host, args.port)


if __name__ == "__main__":
    main()
