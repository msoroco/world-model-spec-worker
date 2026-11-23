"""Run C24811 primary saved processing on an explicit synthetic CPU fixture.

This proves protocol wiring only. The fixture cannot establish Native motion,
pixel visibility, physical completion or a legal judgment.
"""

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def main():
    output_root = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
    if (not output_root or
            not Path(output_root).resolve().is_relative_to(REPO/".runtime-work")):
        raise ValueError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
    root = Path(output_root).resolve()/"c24811-primary-synthetic"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    sys.path.insert(0,str(REPO/"runtime/scenario_pipeline"))
    sys.path.insert(0,str(ROOT))
    spec = importlib.util.spec_from_file_location(
        "c24811_fixture",ROOT/"tests/test_blind_signal.py")
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    fixture.BlindSignalTests().fixture(root)
    config = json.loads((ROOT/"config.json").read_text())
    (root/"config.json").write_text(json.dumps(config))
    case_id = config["selected_case_id"]
    mapping = [json.loads(row) for row in (root/"video_frames.jsonl").read_text().splitlines()]
    (root/"trace.jsonl").write_text("".join(json.dumps({
        "frame":row["carla_frame"],"time_s":row["time_s"],
        "position_m":[float(index),0,0]})+"\n" for index,row in enumerate(mapping)))
    (root/"capture").mkdir()
    (root/"capture/evidence.jsonl").write_text("{}\n")
    (root/"capture/manifest.json").write_text(json.dumps({
        "case_id":case_id,"acquisition":"synthetic_fixture",
        "extraction_confirmed":True,"frames":len(mapping)}))
    for name in fixture.cameras.CAMERAS:
        with fixture.cameras.ffv1_writer(root/(name+".mkv"),(4,4)) as writer:
            for _ in mapping:
                writer(bytes([0,0,0,255])*16)
    sealed = {name:hashlib.sha256((root/name).read_bytes()).hexdigest()
              for name in fixture.finalizer.REQUIRED if name!="capture-seal.json"}
    seal = {"provenance_kind":"synthetic_fixture","diagnostic_fixture":True,
            "frames":len(mapping),"restoration":{"restored":True,"fixture":True},
            "physical_acceptance_claimed":False,
            "encoder_exit_codes":{name:0 for name in fixture.cameras.CAMERAS},
            "sources":sealed}
    seal_path = root/"capture-seal.json"
    seal_path.write_text(json.dumps(seal))
    mixed = dict(seal,provenance_kind="native")
    seal_path.write_text(json.dumps(mixed))
    try:
        fixture.finalizer.validate_sources(root)
    except ValueError as error:
        if "provenance" not in str(error):
            raise
    else:
        raise AssertionError("Synthetic acquisition passed with a Native seal")
    seal_path.write_text(json.dumps(seal))
    analysis_path = root.parent/"c24811-primary-analysis.json"
    if analysis_path.exists():
        analysis_path.unlink()
    analysis = fixture.finalizer.finalize_saved(root,analysis_path)
    from worker_exchange.measurement_contract import validate, verify_report
    contract = json.loads((ROOT/"measurement-contract.json").read_text())
    plan = json.loads((ROOT/"case-plan.json").read_text())
    validate(contract,plan["requirement_dispositions"],
             (ROOT/"saved_finalizer.py").read_text(),case_id)
    measured = verify_report(contract,analysis,root)
    context_path = root/contract["negative"]["remove"][0]
    context_bytes = context_path.read_bytes()
    context_path.unlink()
    try:
        fixture.finalizer.validate_sources(root)
    except ValueError as error:
        if contract["negative"]["error_contains"] not in str(error):
            raise
    else:
        raise AssertionError("Missing exact context source passed saved preflight")
    finally:
        context_path.write_bytes(context_bytes)
    result = json.loads((root/"result.json").read_text())
    if (analysis.get("analysis_complete") is not True or
            analysis.get("provenance_kind") != "synthetic_fixture" or
            analysis.get("diagnostic_fixture") is not True or
            result.get("physical_acceptance_claimed") is not False or
            result.get("provenance_kind") != "synthetic_fixture" or
            result.get("diagnostic_fixture") is not True or
            analysis["source_report"].get("exact_case_id") != case_id or
            analysis["camera_frame_counts"] !=
            {name:len(mapping) for name in fixture.cameras.CAMERAS}):
        raise AssertionError("Primary saved fixture did not retain exact provenance")
    proved_cases = [case_id]
    fixture_roots = {case_id:root}
    for short in ("off_stop_earlier_only", "off_stop_occupant_only",
                  "off_no_full_halt", "operative_signal"):
        other_case = case_id.rsplit("__",1)[0]+"__"+short
        other_root = Path(output_root).resolve()/("c24811-"+short+"-synthetic")
        if other_root.exists():
            shutil.rmtree(other_root)
        other_root.mkdir(parents=True)
        fixture.BlindSignalTests().fixture(other_root)
        other_config = dict(config,selected_case_id=other_case,
                            operative_signal_state="Green" if short == "operative_signal" else None)
        (other_root/"config.json").write_text(json.dumps(other_config))
        rows = [json.loads(line) for line in
                (other_root/"vehicle_signal_history.jsonl").read_text().splitlines()]
        if short == "off_stop_earlier_only":
            rows[-1]["occupant"]["body_vertices_xy_m"] = [
                [x-12,y] for x,y in rows[-1]["occupant"]["body_vertices_xy_m"]]
        if short == "off_stop_occupant_only":
            rows[0]["earlier"]["speed_mps"] = 2
            rows[1]["earlier"]["speed_mps"] = 2
        if short == "off_no_full_halt":
            rows[1]["ego"]["speed_mps"] = 2
        if short == "operative_signal":
            for row in rows:
                row["signal_states"] = {key:"Green" for key in row["signal_states"]}
        (other_root/"vehicle_signal_history.jsonl").write_text(
            "".join(json.dumps(row)+"\n" for row in rows))
        other_mapping = [json.loads(line) for line in
                         (other_root/"video_frames.jsonl").read_text().splitlines()]
        (other_root/"trace.jsonl").write_text("".join(json.dumps({
            "frame":row["carla_frame"],"time_s":row["time_s"],
            "position_m":[float(index),0,0]})+"\n"
            for index,row in enumerate(other_mapping)))
        (other_root/"capture").mkdir()
        (other_root/"capture/evidence.jsonl").write_text("{}\n")
        (other_root/"capture/manifest.json").write_text(json.dumps({
            "case_id":other_case,"acquisition":"synthetic_fixture",
            "extraction_confirmed":True,"frames":len(other_mapping)}))
        for name in fixture.cameras.CAMERAS:
            with fixture.cameras.ffv1_writer(other_root/(name+".mkv"),(4,4)) as writer:
                for _ in other_mapping:
                    writer(bytes([0,0,0,255])*16)
        other_sealed = {name:hashlib.sha256((other_root/name).read_bytes()).hexdigest()
                        for name in fixture.finalizer.REQUIRED
                        if name != "capture-seal.json"}
        (other_root/"capture-seal.json").write_text(json.dumps({
            "provenance_kind":"synthetic_fixture","diagnostic_fixture":True,
            "frames":len(other_mapping),
            "restoration":{"restored":True,"fixture":True},
            "physical_acceptance_claimed":False,
            "encoder_exit_codes":{name:0 for name in fixture.cameras.CAMERAS},
            "sources":other_sealed}))
        other_analysis_path = other_root.parent/("c24811-"+short+"-analysis.json")
        if other_analysis_path.exists():
            other_analysis_path.unlink()
        other_analysis = fixture.finalizer.finalize_saved(
            other_root,other_analysis_path)
        verify_report(contract,other_analysis,other_root)
        other_result = json.loads((other_root/"result.json").read_text())
        if (other_analysis["source_report"]["exact_case_id"] != other_case or
                other_analysis["provenance_kind"] != "synthetic_fixture" or
                other_result["physical_acceptance_claimed"] is not False):
            raise AssertionError("Comparison case lost exact diagnostic provenance")
        proved_cases.append(other_case)
        fixture_roots[other_case] = other_root
    from worker_exchange.runtime_cli import materialize, execution_env
    manifest_path = ROOT/"execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    proved_fallbacks = []
    for entry in manifest["cases"]:
        case = entry["case_id"]
        short = case.rsplit("__",1)[-1]
        source_root = fixture_roots[case]
        for candidate in entry["candidates"]:
            candidate_id = candidate["id"]
            name = short+"-"+candidate_id
            bundle = REPO/".runtime-work"/("c24811-materialized-"+name)
            attempt = Path(output_root).resolve()/("saved-"+name)
            analysis_path = Path(output_root).resolve()/("analysis-"+name+".json")
            for directory in (bundle,attempt):
                if directory.exists():
                    shutil.rmtree(directory)
            if analysis_path.exists():
                analysis_path.unlink()
            materialize(manifest_path,case,bundle,candidate_id)
            attempt.mkdir()
            for relative in fixture.finalizer.REQUIRED:
                if relative in ("config.json","capture-seal.json"):
                    continue
                destination = attempt/relative
                destination.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(source_root/relative,destination)
            shutil.copyfile(bundle/"config.json",attempt/"config.json")
            source_seal = json.loads((source_root/"capture-seal.json").read_text())
            source_seal["sources"] = {
                relative:hashlib.sha256((attempt/relative).read_bytes()).hexdigest()
                for relative in fixture.finalizer.REQUIRED
                if relative != "capture-seal.json"}
            (attempt/"capture-seal.json").write_text(json.dumps(source_seal))
            subprocess.run([sys.executable,str(bundle/"runner.py"),
                            "--attempt",str(attempt),"--output",str(analysis_path)],
                           cwd=bundle,env=execution_env(),check=True,
                           stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                           text=True,timeout=300)
            candidate_analysis = json.loads(analysis_path.read_text())
            verify_report(contract,candidate_analysis,attempt)
            candidate_result = json.loads((attempt/"result.json").read_text())
            if (candidate_analysis["case_id"] != case or
                    candidate_analysis["provenance_kind"] != "synthetic_fixture" or
                    candidate_result["diagnostic_fixture"] is not True or
                    candidate_result["physical_acceptance_claimed"] is not False):
                raise AssertionError("Fallback saved proof lost exact diagnostic provenance")
            proved_fallbacks.append(name)
    print(json.dumps({"case_id":case_id,"saved_processing":"passed",
        "provenance_kind":"synthetic_fixture","diagnostic_fixture":True,
        "camera_frame_count":len(mapping),"physical_acceptance_claimed":False,
        "native_capture_verified":False,
        "source_bound_measurements":len(measured),
        "missing_context_rejected":True,
        "saved_processing_case_count":len(proved_cases),
        "saved_processing_fallback_count":len(proved_fallbacks)},sort_keys=True))


if __name__ == "__main__":
    main()
