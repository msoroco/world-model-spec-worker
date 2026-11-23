"""Run C24811 primary saved processing on an explicit synthetic CPU fixture.

This proves protocol wiring only. The fixture cannot establish Native motion,
pixel visibility, physical completion or a legal judgment.
"""

import hashlib
import importlib.util
import json
import os
import shutil
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
    print(json.dumps({"case_id":case_id,"saved_processing":"passed",
        "provenance_kind":"synthetic_fixture","diagnostic_fixture":True,
        "camera_frame_count":len(mapping),"physical_acceptance_claimed":False,
        "native_capture_verified":False},sort_keys=True))


if __name__ == "__main__":
    main()
