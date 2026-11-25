"""Prove selected analysis output against the pinned Native result validator.

Uses a deliberately synthetic three-tick source fixture; this is software
compatibility evidence, not a production acquisition or physical acceptance.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "tests"))
sys.path.insert(0, str(ROOT / "runtime"))
sys.path.insert(0, str(ROOT / "runtime" / "scenario_pipeline"))


def prove() -> dict:
    output_root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    scratch = ROOT / ".runtime-work"
    if scratch not in output_root.parents:
        raise ValueError("pipeline output root must be under .runtime-work")
    work = scratch / "c158208-owner-nov24b" / "tmp"
    work.mkdir(parents=True, exist_ok=True)
    from analysis import analyze
    from build_semantic_proposals import recording_description
    from camera_sources import write_camera_sources
    from test_camera_sources import fixture
    from batch_pipeline.carla import validate_attempt
    from worker_exchange.native_output import validate_result
    from worker_exchange.fixture_recipe import materialize as materialize_fixture
    from worker_exchange.measurement_contract import validate as validate_measurements
    from worker_exchange.measurement_contract import verify_report
    from worker_exchange.saved_processing import prepare_video
    from worker_exchange.runtime_cli import process, render
    from worker_exchange.media import audit as audit_video
    from selected_delivery_audit import audit as audit_delivery
    validator = scratch / "c158208-owner-nov24b" / "decoder/.lake/build/bin/adapterCheck"
    if not validator.is_file():
        raise ValueError("isolated pinned Lean decoder has not been built")
    case = HERE.name + "__nearest_view_response"
    with tempfile.TemporaryDirectory(dir=work) as directory:
        stage = Path(directory) / "attempt"
        frames = fixture(stage)
        write_camera_sources(stage, frames, diagnostic_fixture=True)
        description = recording_description()
        config = {"selected_case_id": case, "rate_hz": 20, "duration_s": 45,
                  "cell_id": "C158208", "actor": "motor_vehicle_driver"}
        construction = {"case_id": case, "recording_description": description}
        (stage / "config.json").write_text(json.dumps(config) + "\n")
        (stage / "construction.json").write_text(json.dumps(construction) + "\n")
        analyze(stage, stage / "analysis-report.json")
        result = validate_result(json.loads((stage / "result.json").read_text()))
        proposal = {"case_id": case, "recording_description": description,
                    "sweep_measurements": []}
        checked = validate_attempt(stage,
            {"case": proposal, "cell": {"cell_id": "C158208"},
             "actor": "motor_vehicle_driver"}, construction,
            {"recorded_exit_code": 0}, {})
        if checked["status"] != "draft" or not result["diagnostic_fixture"]:
            raise ValueError("synthetic source proof changed status")
        selected = {}
        plan = json.loads((HERE / "case-plan.json").read_text())
        code = (HERE / "analysis.py").read_text()
        for kind in ("nearest_view_response", "nearest_view_uninterrupted"):
            selected_case = HERE.name + "__" + kind
            contract = json.loads((HERE / ("measurement-contract-" + kind + ".json")).read_text())
            validate_measurements(contract, plan["requirement_dispositions"], code, selected_case)
            fixture_stage = Path(directory) / ("fixture-" + kind)
            source = materialize_fixture(ROOT, HERE / ("fixture-recipe-" + kind + ".json"),
                                         fixture_stage)
            construction = {"case_id": selected_case, "recording_description": description}
            config = {"selected_case_id": selected_case, "rate_hz": 20, "duration_s": 45,
                      "cell_id": "C158208", "actor": "motor_vehicle_driver"}
            (fixture_stage / "construction.json").write_text(json.dumps(construction) + "\n")
            (fixture_stage / "config.json").write_text(json.dumps(config) + "\n")
            prepare_video(fixture_stage)
            report = analyze(fixture_stage, fixture_stage / "analysis-report.json")
            verify_report(contract, report, fixture_stage)
            native = validate_result(json.loads((fixture_stage / "result.json").read_text()))
            validate_attempt(fixture_stage,
                {"case": {"case_id": selected_case, "recording_description": description},
                 "cell": {"cell_id": "C158208"}, "actor": "motor_vehicle_driver"},
                construction, {"recorded_exit_code": 0}, {})
            converted = fixture_stage / "converted"
            process(fixture_stage, converted, ROOT / "runtime/library", validator,
                    diagnostic_fixture=True)
            rendered = render(fixture_stage, converted,
                              {"case_id": selected_case,
                               "recording_description": description,
                               "rationale": "synthetic source-shaped software proof"})
            final_decode = audit_video(rendered["video"], 3)
            delivery = audit_delivery(fixture_stage, case_id=selected_case,
                                      diagnostic_fixture=True)
            if delivery["source_frames"] != 3 or len(delivery["camera_sources"]) != 4:
                raise ValueError("independent selected delivery audit incomplete")
            report_path = fixture_stage / "analysis-report.json"
            original_report = report_path.read_text()
            altered = json.loads(original_report)
            altered["measurements"]["nearest_view_history"]["sources"]["capture-identity.json"] = "0" * 64
            report_path.write_text(json.dumps(altered) + "\n")
            try:
                audit_delivery(fixture_stage, case_id=selected_case,
                               diagnostic_fixture=True)
            except ValueError as error:
                if "selected measurement source differs" not in str(error):
                    raise
            else:
                raise ValueError("independent delivery audit accepted altered source hash")
            finally:
                report_path.write_text(original_report)
            omitted = json.loads(original_report)
            omitted["measurements"]["governing_control_context"]["sources"].pop(
                "nearest-view-saved-packet.json")
            report_path.write_text(json.dumps(omitted) + "\n")
            try:
                audit_delivery(fixture_stage, case_id=selected_case,
                               diagnostic_fixture=True)
            except ValueError as error:
                if "selected measurement source inventory differs" not in str(error):
                    raise
            else:
                raise ValueError("independent delivery audit accepted omitted original source")
            finally:
                report_path.write_text(original_report)
            negative = Path(directory) / ("negative-" + kind)
            materialize_fixture(ROOT, HERE / ("fixture-recipe-" + kind + ".json"), negative)
            (negative / "nearest-view-saved-packet.json").unlink()
            try:
                analyze(negative, negative / "analysis-report.json")
            except ValueError as error:
                if contract["negative"]["error_contains"] not in str(error):
                    raise
            else:
                raise ValueError("missing selected source did not fail")
            selected[kind] = {"fixture_sha256": source["fixture_sha256"],
                              "measurement_keys": sorted(report["measurements"]),
                              "native_result_valid": True, "negative_source_rejected": True,
                              "core_and_lean_valid": True,
                              "independent_delivery_audit": True,
                              "altered_source_hash_rejected": True,
                              "omitted_source_rejected": True,
                              "final_video_frames": final_decode["frames"],
                              "diagnostic_fixture": native["diagnostic_fixture"]}
        return {"case_id": case, "original_frames": 3,
                "source_videos": len(result["video_references"]),
                "recording_evidence": len(result["recording_evidence"]),
                "pinned_native_validation": True, "diagnostic_fixture": True,
                "physical_acceptance": False, "selected_recipe_proofs": selected}


if __name__ == "__main__":
    print(json.dumps(prove(), sort_keys=True))
