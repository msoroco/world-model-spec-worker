"""Exercise the actual pinned Native-result builder on a textual CPU fixture."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
sys.path.insert(1, str(REPO / "runtime/python"))

from analysis import build_report, saved_result


def main():
    spec = importlib.util.spec_from_file_location("fixture", ROOT / "tests/test_analysis.py")
    fixture_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture_module)
    with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work", prefix="c125714-saved-") as tmp:
        folder = Path(tmp)
        fixture_module.fixture(folder)
        description = {
            "channels": [
                {"name": "ego_body_history", "unit": "m"},
                {"name": "other_body_history", "unit": "m"},
            ],
            "context_inputs": [
                {"name": name, "unit": "structured record"}
                for name in ("crossing_geometry", "highway_identity", "device_inventory", "driver_scope")
            ],
        }
        (folder / "construction.json").write_text(json.dumps({"recording_description": description}))
        (folder / "config.json").write_text(json.dumps({
            "law_id": "NRS-484B-250-1", "cell_id": "C125714", "actor": "motor_vehicle_driver",
            "rate_hz": 20, "duration_s": .45,
            "selected_case_id": "testing__C125714__NRS-484B-250-1__motor_vehicle_driver__precedence",
            "case": {"other_entered_first": True, "recording_description": description},
            "physical_completion": {"criterion": "intersection_clearance",
                "motion_source": "ego-body-history.jsonl", "body_key": "body_vertices_xy_m",
                "intersection_polygon_xy_m": [[-1,-1],[1,-1],[1,1],[-1,1]],
                "exit_axis": 1, "exit_sign": 1, "minimum_progress_m": .25,
                "minimum_samples": 2},
        }))
        with (folder / "video_frames.jsonl").open("w") as stream:
            for frame in range(9):
                stream.write(json.dumps({"video_frame": frame, "carla_frame": frame,
                                         "native_frame": frame, "time_s": frame/20}) + "\n")
        with (folder / "trace.jsonl").open("w") as stream:
            for frame in range(9):
                stream.write(json.dumps({"frame": frame, "time_s": frame/20,
                                         "position_m": [0, -2 if frame < 4 else (0 if frame < 6 else 2)]}) + "\n")
        (folder / "acquisition-provenance.json").write_text(json.dumps(
            {"provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}))
        report = build_report(folder)
        result = saved_result(folder, report)
        assert result["case_id"].endswith("__precedence")
        if result["physical_checks"]["maneuver"]["status"] != "met":
            raise AssertionError(json.dumps(result["physical_checks"]["maneuver"], indent=2))
        assert result["physical_acceptance_claimed"] is False
        assert result["measured_values"]["legal_judgment"] == "unresolved"
        config_path = folder / "config.json"
        config = json.loads(config_path.read_text())
        config["physical_completion"]["intersection_polygon_xy_m"][0][0] = -99
        config_path.write_text(json.dumps(config))
        try:
            saved_result(folder, report)
        except ValueError as exc:
            assert "completion polygon differs" in str(exc)
        else:
            raise AssertionError("mismatched physical completion polygon was accepted")
        (folder / "other-body-history.jsonl").unlink()
        try:
            build_report(folder)
        except ValueError as exc:
            assert "Missing required source: other-body-history.jsonl" in str(exc)
        else:
            raise AssertionError("missing original other body was accepted")
        print(json.dumps({"saved_result_valid": True, "physical_fixture_motion": "met",
                          "wrong_completion_polygon_rejected": True,
                          "missing_original_source_rejected": True,
                          "actual_capture_claimed": False}))


if __name__ == "__main__":
    main()
