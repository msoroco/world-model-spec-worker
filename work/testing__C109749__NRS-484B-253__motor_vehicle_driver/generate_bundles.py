"""Generate eight exact inline offline bundles from current local sources."""

import hashlib
import json
from pathlib import Path

from construction import POLICIES
from requirement_finalizer import ASSIGNMENT_ID

ROOT = Path(__file__).resolve().parent
SOURCES = {
    "runner.py": "bundle_runner.py",
    "construction.py": "construction.py",
    "native_intersection.py": "native_intersection.py",
    "left_turn_controller.py": "left_turn_controller.py",
    "left_turn_measurements.py": "left_turn_measurements.py",
    "saved_left_turn.py": "saved_left_turn.py",
    "native_acquisition.py": "native_acquisition.py",
    "saved_media_audit.py": "saved_media_audit.py",
    "delivery_audit.py": "delivery_audit.py",
    "requirement_finalizer.py": "requirement_finalizer.py",
    "analysis.py": "analysis.py",
}
RECIPROCAL_SOURCES = (
    "bundle_runner.py", "reciprocal_entrypoint.py", "reciprocal_live.py",
    "reciprocal_native_capture.py", "reciprocal_saved.py", "reciprocal_witness.py",
    "reciprocal_finalization.py", "carla_scene_factory.py", "carla_live_adapter.py",
    "native_source_review.py", "live_capture.py",
)
STANDARD_SOURCES = (
    "carla_scene_factory.py", "carla_live_adapter.py", "native_source_review.py",
    "live_capture.py", "native_entrypoint.py",
)

RECORDING_DESCRIPTION = {
    "channels": [
        {"name": name, "unit": unit, "method": "original source-bound actor sample",
         "time_window": "full original recording", "reference_frame": "original CARLA world frame",
         "uncertainty": "diagnostic software fixture or unreviewed Native sensor accuracy",
         "sampling_rate_hz": 20}
        for name, unit in (("ego_body_history", "structured"),
                           ("opponent_body_history", "structured"),
                           ("ego_signal_history", "categorical"))],
    "context_inputs": [{"name": "intersection_geometry", "unit": "structured",
                        "method": "source-hashed original map packet"}],
    "limitations": ["Immediate hazard, legal yield and signal duty require separate judgment.",
                    "Diagnostic sources do not establish physical realization."],
}


def _write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate():
    plan = json.loads((ROOT / "case-plan.json").read_text(encoding="utf-8"))
    entrypoints = {case["case_id"] for case in plan["cases"]}
    if entrypoints != {ASSIGNMENT_ID + "__" + suffix for suffix in POLICIES}:
        raise ValueError("case-plan and exact construction cases differ")
    fixture = (ROOT / "cases/inside_yield/diagnostic-map.json").read_text(encoding="utf-8")
    fixture_obj = json.loads(fixture)
    if fixture_obj.get("diagnostic_fixture") is not True:
        raise ValueError("offline map must be diagnostic")
    entries = []
    for suffix, (_, wait, signal, later_wait) in POLICIES.items():
        case_id = ASSIGNMENT_ID + "__" + suffix
        config = {"law_id": "NRS-484B-253", "cell_id": "C109749",
                  "actor": "motor_vehicle_driver", "selected_case_id": case_id,
                  "rate_hz": 20, "duration_s": 45,
                  "cameras": ["overview", "approach", "reference_corner", "driver_reference"],
                  "required_atoms": [], "source_packets": [],
                  "controller": {"wait_for_initial_opponent": wait, "signal_left": signal,
                                 "wait_for_later_opponent": later_wait, "target_speed_mps": 5.0},
                  "native_map_survey": "required_before_capture",
                  "case": {"recording_description": RECORDING_DESCRIPTION},
                  "physical_completion": {"criterion": "intersection_clearance",
                                          "motion_source": "interaction_history.jsonl",
                                          "body_key": "subject_body_vertices_m",
                                          "context_sources": ["road_geometry.json"],
                                          "intersection_polygon_xy_m": [[-5, -5], [5, -5], [5, 5], [-5, 5]],
                                          "exit_axis": 1, "exit_sign": -1},
                  "physical_realization": "unverified"}
        files = [{"path": target, "source": str((ROOT / source).relative_to(ROOT.parents[1])),
                  "content": (ROOT / source).read_text(encoding="utf-8")}
                 for target, source in SOURCES.items()]
        if suffix.startswith("reciprocal_"):
            files.extend({"path": source,
                          "source": str((ROOT / source).relative_to(ROOT.parents[1])),
                          "content": (ROOT / source).read_text(encoding="utf-8")}
                         for source in RECIPROCAL_SOURCES)
            runner = next(item for item in files if item["path"] == "runner.py")
            old = '    raise RuntimeError("Native CARLA adapter and world lifecycle binding still required")'
            new = ('    from reciprocal_entrypoint import run_native\n'
                   '    if not args.output_dir:\n'
                   '        raise ValueError("Native attempt output directory required")\n'
                   '    result = run_native("config.json", args.map_packet, args.output_dir,\n'
                   '                        args.host or "127.0.0.1", int(args.port or 2000))\n'
                   '    print(json.dumps(result, default=str))')
            if runner["content"].count(old) != 1:
                raise ValueError("reciprocal runner production seam changed")
            runner["content"] = runner["content"].replace(old, new)
            runner_source = ROOT / "reciprocal_bundle_runner.py"
            runner_source.write_text(runner["content"], encoding="utf-8")
            runner["source"] = str(runner_source.relative_to(ROOT.parents[1]))
            analysis = next(item for item in files if item["path"] == "analysis.py")
            old = "from requirement_finalizer import finalize\n"
            new = "from reciprocal_finalization import finalize_reciprocal as finalize\n"
            if analysis["content"].count(old) != 1:
                raise ValueError("reciprocal saved finalizer seam changed")
            analysis["content"] = analysis["content"].replace(old, new)
            analysis_source = ROOT / "reciprocal_bundle_analysis.py"
            analysis_source.write_text(analysis["content"], encoding="utf-8")
            analysis["source"] = str(analysis_source.relative_to(ROOT.parents[1]))
        else:
            files.extend({"path": source,
                          "source": str((ROOT / source).relative_to(ROOT.parents[1])),
                          "content": (ROOT / source).read_text(encoding="utf-8")}
                         for source in STANDARD_SOURCES)
            runner = next(item for item in files if item["path"] == "runner.py")
            old = '    raise RuntimeError("Native CARLA adapter and world lifecycle binding still required")'
            new = ('    from native_entrypoint import run_native\n'
                   '    if not args.output_dir:\n'
                   '        raise ValueError("Native attempt output directory required")\n'
                   '    result = run_native("config.json", args.map_packet, args.output_dir,\n'
                   '                        args.host or "127.0.0.1", int(args.port or 2000))\n'
                   '    print(json.dumps(result, default=str))')
            if runner["content"].count(old) != 1:
                raise ValueError("standard runner production seam changed")
            runner["content"] = runner["content"].replace(old, new)
            runner_source = ROOT / "standard_bundle_runner.py"
            runner_source.write_text(runner["content"], encoding="utf-8")
            runner["source"] = str(runner_source.relative_to(ROOT.parents[1]))
        files.extend([{"path": "config.json", "content": json.dumps(config, indent=2) + "\n"},
                      {"path": "diagnostic-map.json", "content": fixture},
                      {"path": "tests/test_bundle.py", "content":
                       "import json\nimport unittest\nfrom pathlib import Path\n"
                       "from runner import check\n"
                       "class BundleTests(unittest.TestCase):\n"
                       " def test_exact_case(self):\n"
                       "  cfg=json.loads(Path('config.json').read_text())\n"
                       "  source=json.loads(Path('diagnostic-map.json').read_text())\n"
                       "  self.assertEqual(check(cfg,source)['case_id'],cfg['selected_case_id'])\n"
                       " def test_reject_wrong_policy(self):\n"
                       "  cfg=json.loads(Path('config.json').read_text())\n"
                       "  source=json.loads(Path('diagnostic-map.json').read_text())\n"
                       "  cfg['controller']['signal_left']=not cfg['controller']['signal_left']\n"
                       "  with self.assertRaisesRegex(ValueError,'case policy'):\n"
                       "   check(cfg,source)\n"}])
        bundle = {"law_id": "NRS-484B-253", "cell_id": "C109749",
                  "actor": "motor_vehicle_driver", "case_id": case_id,
                  "entrypoint": "runner.py", "files": files,
                  "recording_description": RECORDING_DESCRIPTION,
                  "measurement_plan": ["full-body intersection occupancy", "opposite approach and clearance", "left-signal and turn commitment", "source-bound four-camera frame join"],
                  "source_kind": "diagnostic_offline_only_native_map_survey_required"}
        path = ROOT / "cases" / suffix / "construction.json"
        _write(path, bundle)
        entries.append({"case_id": case_id, "construction": str(path.relative_to(ROOT)),
                        "construction_sha256": _sha(path), "kind": "partial_offline_bundle"})
    manifest = {"format": "worker-offline-checkpoint-manifest", "assignment_id": ASSIGNMENT_ID,
                "cases": entries, "delivery_ready": False}
    _write(ROOT / "bundle-checkpoint-manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    print(json.dumps({"case_count": len(generate()["cases"])}))
