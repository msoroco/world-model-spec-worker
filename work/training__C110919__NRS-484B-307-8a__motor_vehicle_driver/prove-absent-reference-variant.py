"""Exercise the absent stopping-reference right-turn pair on CPU."""
import copy
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NATIVE = HERE / "native"
sys.path.insert(0, str(NATIVE))
from engineering import CANDIDATES, parameters
from runner import check as runner_check
from variant_geometry import check_for, open_drive_for

spec = importlib.util.spec_from_file_location("c110919_variant_finalize", NATIVE / "finalize.py")
finalize = importlib.util.module_from_spec(spec)
spec.loader.exec_module(finalize)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rejects(action):
    try:
        action()
    except ValueError:
        return
    raise AssertionError("Invalid absent-reference evidence was accepted")


def main():
    template = json.loads((NATIVE / "config.json").read_text())
    variants = {}
    for suffix in ("absent_reference", "absent_reference_contrast"):
        geometry = check_for(suffix)
        if geometry["stopping_reference_kind"] != "intersection_boundary" or \
           geometry["stopping_reference_y_m"] != -7.0 or \
           geometry["nearest_crosswalk_or_stop_marking_present"] is not False:
            raise AssertionError("Absent stopping-reference contract differs")
        xml = ET.fromstring(open_drive_for(suffix))
        approach = next(road for road in xml.findall("road") if road.attrib["id"] == "1")
        if approach.findall("objects/object") or len(xml.findall(".//signal[@id='601']")) != 1:
            raise AssertionError("Original approach still has a stopping object or lacks signal")
        candidates = []
        for ident in CANDIDATES:
            config = copy.deepcopy(template)
            config.update({"case_id": HERE.name + "__" + suffix,
                           "case_suffix": suffix, "candidate_id": ident,
                           "knobs": parameters(suffix, ident)["knobs"]})
            outcome = runner_check(config)
            if outcome["camera_count"] != 4 or outcome["offline_geometry"]["stopping_reference_y_m"] != -7.0:
                raise AssertionError("Variant runner or four-camera setup failed")
            candidates.append(ident)
        source_suffix = "reference" if suffix == "absent_reference" else "contrast"
        prior = ROOT / ".runtime-work/c110919-update017-selected-pair-probe" / source_suffix / "primary/compatibility"
        with tempfile.TemporaryDirectory(prefix="c110919-absent-cpu-") as folder:
            attempt = Path(folder)
            shutil.copyfile(prior / "native_samples.jsonl", attempt / "native_samples.jsonl")
            road = json.loads((prior / "road_geometry.json").read_text())
            road.update({"stop_line_y_m": None, "nearest_crosswalk_y_m": None,
                         "intersection_near_y_m": -7.0,
                         "stopping_reference_kind": "intersection_boundary",
                         "stopping_reference_y_m": -7.0,
                         "native_absence_observed": False})
            (attempt / "road_geometry.json").write_text(json.dumps(road) + "\n")
            samples = [json.loads(line) for line in (attempt / "native_samples.jsonl").read_text().splitlines()]
            signal = finalize.measure_signal(attempt, samples, road)
            stop = finalize.measure_stop(attempt, samples, road)
            expected = suffix == "absent_reference"
            if signal["value"]["stopping_reference_kind"] != "intersection_boundary" or \
               stop["value"]["halt_before_nearest_boundary"] is not expected:
                raise AssertionError("Measured absent-boundary comparison differs")
            damaged = {**road, "stop_line_y_m": -14.0}
            rejects(lambda: finalize.measure_signal(attempt, samples, damaged))
            damaged = {**road, "stopping_reference_y_m": None}
            rejects(lambda: finalize.measure_stop(attempt, samples, damaged))
            variants[suffix] = {"candidates_checked": candidates,
                                "stopping_reference_y_m": -7.0,
                                "stationary_pre_crossing_frames": stop["value"]["stationary_pre_crossing_frames"],
                                "halt_before_boundary": stop["value"]["halt_before_nearest_boundary"],
                                "source_kind": "synthetic_native_sample_reused_in_memory_for_branch_probe",
                                "native_absence_observed": False}
    proof = {"format": "c110919-absent-reference-right-turn-cpu-probe-v1",
             "variant_geometry_sha256": sha(NATIVE / "variant_geometry.py"),
             "runner_sha256": sha(NATIVE / "runner.py"),
             "finalizer_sha256": sha(NATIVE / "finalize.py"),
             "engineering_sha256": sha(NATIVE / "engineering.py"),
             "cases": variants, "physical_absence_or_motion_verified": False,
             "original_recordings_accepted": 0}
    path = HERE / "update022-absent-reference-variant-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"cases": len(variants), "candidates_checked": 8,
                      "stop_frames": {key: value["stationary_pre_crossing_frames"]
                                      for key, value in variants.items()},
                      "proof_sha256": sha(path), "original_recordings_accepted": 0}))


if __name__ == "__main__":
    main()
