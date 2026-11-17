"""Independent source and measurement audit for two saved overtaken responses."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import shutil
import tempfile
from pathlib import Path

SOURCE_NAMES = ("overtaken_source.jsonl", "video_frames.jsonl", "trace.jsonl",
                "signal_command_original.jsonl", "signal_audio_envelope_original.jsonl")
PREFIX = "heldout__C179789__NRS-484B-207-2__motor_vehicle_driver__"
PAIRS = {"right_yield": ("gives_way_holds_speed", "no_right_yield_holds_speed"),
         "speed_hold_until_complete": ("gives_way_holds_speed", "gives_way_increases_speed")}
RIGHT_PASS_PAIR = ("no_right_yield_holds_speed", "right_pass_permitted_no_right_yield")

def read_rows(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]

def load_response():
    source = Path(__file__).with_name("overtaken_response.py")
    spec = importlib.util.spec_from_file_location("overtaken_response_for_behavior_audit", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def read_case(receipt_path, case_id, module, root_override=None):
    receipt = json.loads(Path(receipt_path).read_text())
    root = Path(root_override or receipt.get("analysis_directory", ""))
    if (receipt.get("case_id") != case_id or receipt.get("passed") is not True or
        receipt.get("originals_preserved") is not True or receipt.get("missing_evidence") is not False or
        receipt.get("physical_acceptance_claimed") is not False or
        receipt.get("legal_acceptance_claimed") is not False):
        raise ValueError("Saved receipt identity or status differs")
    for name in SOURCE_NAMES:
        path = root/name
        if not path.is_file() or not path.read_bytes():
            raise ValueError("Saved original source missing: "+name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != receipt["original_source_hashes"].get(name):
            raise ValueError("Saved original source changed: "+name)
    measured = module.measure_audible_saved(*(root/name for name in SOURCE_NAMES))
    report = json.loads((root/"analysis-report.json").read_text())
    result = json.loads((root/"result.json").read_text())
    if (report.get("case_id") != case_id or result.get("case_id") != case_id or
        report["measurements"]["overtaken_response"]["value"] != measured or
        result["measured_values"]["overtaken_response"] != measured or
        report.get("physical_acceptance_claimed") is not False or
        result.get("legal_acceptance_claimed") is not False):
        raise ValueError("Saved measured result differs from original sources")
    return receipt, measured, read_rows(root/SOURCE_NAMES[0]), read_rows(root/SOURCE_NAMES[1]), read_rows(root/SOURCE_NAMES[2])

def read_permission_premise(receipt, root):
    """Require original cited rule and road survey bytes for a reviewed premise.

    This verifies provenance and comparison isolation only. It cannot decide
    whether the cited rule actually permits the maneuver.
    """
    root = Path(root)
    name = "right_pass_premise.json"
    path = root/name
    hashes = receipt.get("original_source_hashes", {})
    if not path.is_file() or not path.read_bytes() or hashes.get(name) != hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError("Right-pass comparison lacks original permission premise")
    premise = json.loads(path.read_text())
    if (premise.get("source_kind") != "reviewed_right_pass_premise" or
        type(premise.get("permission_state")) is not bool or
        premise.get("review_scope") != "comparison premise only" or
        premise.get("legal_conclusion") is not None):
        raise ValueError("Right-pass permission premise is incomplete or asserts a legal result")
    for field, source_name in (("governing_rule_sha256", "right_pass_governing_rule.txt"),
                               ("road_survey_sha256", "right_pass_road_survey.json")):
        source_path = root/source_name
        if (not source_path.is_file() or not source_path.read_bytes() or
            premise.get(field) != hashlib.sha256(source_path.read_bytes()).hexdigest() or
            hashes.get(source_name) != premise[field]):
            raise ValueError("Right-pass premise source missing or changed: "+source_name)
    survey = json.loads((root/"right_pass_road_survey.json").read_text())
    if (survey.get("source_kind") != "original_road_survey" or
        not survey.get("road_id") or not survey.get("lane_ids") or
        not survey.get("passing_side") or not survey.get("source_provenance")):
        raise ValueError("Right-pass road survey lacks original geometry or provenance")
    rule = (root/"right_pass_governing_rule.txt").read_text().strip()
    if not rule or not premise.get("governing_rule_citation"):
        raise ValueError("Right-pass governing rule citation missing")
    return premise, survey

def audit_right_pass_exception(base_receipt, variant_receipt, base_root=None, variant_root=None):
    """Audit the held saved motion and require a distinct, sourced premise."""
    module = load_response()
    a = read_case(base_receipt, PREFIX+RIGHT_PASS_PAIR[0], module, base_root)
    b = read_case(variant_receipt, PREFIX+RIGHT_PASS_PAIR[1], module, variant_root)
    ar, am, ab, af, at = a; br, bm, bb, bf, bt = b
    if len(ab) != len(bb) or af != bf or at != bt:
        raise ValueError("Right-pass comparison changed held frame map or motion")
    if any(ar["original_source_hashes"][name] != br["original_source_hashes"][name]
           for name in SOURCE_NAMES):
        raise ValueError("Right-pass comparison changed held original source")
    held_measurements = ("notice_kind", "notice_frame", "pass_complete_frame",
                         "max_right_shift_m", "max_precompletion_speed_delta_mps",
                         "hearing_confirmed", "acoustic_propagation_confirmed")
    if ab != bb or any(am.get(key) != bm.get(key) for key in held_measurements):
        raise ValueError("Right-pass comparison changed held body or measured response")
    (first, first_survey) = read_permission_premise(ar, base_root or ar["analysis_directory"])
    (second, second_survey) = read_permission_premise(br, variant_root or br["analysis_directory"])
    if first["permission_state"] is not False or second["permission_state"] is not True:
        raise ValueError("Right-pass comparison lacks opposite sourced premises")
    if first["governing_rule_sha256"] != second["governing_rule_sha256"]:
        raise ValueError("Right-pass comparison changed governing rule")
    if first["road_survey_sha256"] == second["road_survey_sha256"]:
        raise ValueError("Right-pass comparison has no distinct surveyed premise")
    return {"comparison":"right_pass_exception", "comparison_complete":True,
            "held_original_motion":True, "declared_difference":"source-backed road survey premise",
            "premise_source_hashes":[first["road_survey_sha256"],second["road_survey_sha256"]],
            "diagnostic_fixture_only":any("synthetic" in str(survey.get("source_provenance", "")).lower()
                                          for survey in (first_survey, second_survey)),
            "physical_acceptance_claimed":False,"legal_acceptance_claimed":False}

def audit(base_receipt, variant_receipt, comparison, variant_root=None):
    if comparison not in PAIRS:raise ValueError("Unknown saved comparison")
    module = load_response()
    a,b = (read_case(base_receipt, PREFIX+PAIRS[comparison][0], module),
           read_case(variant_receipt, PREFIX+PAIRS[comparison][1], module, variant_root))
    ar, am, ab, af, at = a; br, bm, bb, bf, bt = b
    if len(ab)!=9 or len(bb)!=9 or af!=bf or am["notice_frame"]!=bm["notice_frame"]:
        raise ValueError("Comparison frame map or notice differs")
    for name in SOURCE_NAMES[3:]:
        if ar["original_source_hashes"][name] != br["original_source_hashes"][name]:
            raise ValueError("Comparison changed held signal source")
    for i,(x,y) in enumerate(zip(ab,bb)):
        for key in ("frame","time_s","subject_id","overtaker_id","overtaker_corners",
                    "road_tangent_xy","notice_stimulus","notice_observed","visibility_relation"):
            if x.get(key)!=y.get(key):raise ValueError("Comparison changed held actor or notice: "+key)
        if comparison == "right_yield":
            for key in ("road_waypoint_xy","subject_speed_mps","body_pass_complete"):
                if x.get(key)!=y.get(key):raise ValueError("Right-yield comparison changed held source: "+key)
            if abs(x["subject_pose_xy"][0]-y["subject_pose_xy"][0])>1e-6 or abs(at[i]["speed_mps"]-bt[i]["speed_mps"])>1e-6:
                raise ValueError("Right-yield comparison changed held longitudinal motion")
        else:
            if abs(x["road_waypoint_xy"][1]-y["road_waypoint_xy"][1])>1e-6:
                raise ValueError("Speed comparison changed held road reference")
            if i<=5 and abs(x["subject_right_offset_m"]-y["subject_right_offset_m"])>1e-6:
                raise ValueError("Speed comparison changed held precompletion right offset")
    if comparison == "right_yield":
        if (abs(am["max_precompletion_speed_delta_mps"]-bm["max_precompletion_speed_delta_mps"])>1e-6 or
            am["pass_complete_frame"]!=bm["pass_complete_frame"] or
            am["max_right_shift_m"]<=0.2 or abs(bm["max_right_shift_m"])>1e-6):
            raise ValueError("Right-yield comparison lacks isolated response difference")
    else:
        if (abs(am["max_right_shift_m"]-bm["max_right_shift_m"])>1e-5 or
            abs(am["max_precompletion_speed_delta_mps"])>1e-6 or
            bm["max_precompletion_speed_delta_mps"]<0.9 or
            bm["pass_complete_frame"]<=am["pass_complete_frame"]):
            raise ValueError("Speed comparison lacks isolated precompletion increase")
    return {"comparison":comparison,"comparison_complete":True,"frames":9,
            "base_right_shift_m":am["max_right_shift_m"],"variant_right_shift_m":bm["max_right_shift_m"],
            "base_speed_delta_mps":am["max_precompletion_speed_delta_mps"],
            "variant_speed_delta_mps":bm["max_precompletion_speed_delta_mps"],
            "base_pass_complete_frame":am["pass_complete_frame"],
            "variant_pass_complete_frame":bm["pass_complete_frame"],
            "physical_acceptance_claimed":False,"legal_acceptance_claimed":False}

def proof(base_receipt, variant_receipt, comparison):
    positive=audit(base_receipt,variant_receipt,comparison)
    receipt=json.loads(Path(variant_receipt).read_text());root=Path(receipt["analysis_directory"])
    negatives=[]
    for label in ("missing_signal", "changed_saved_measurement"):
        with tempfile.TemporaryDirectory(prefix="overtaken-behavior-negative-") as tmp:
            stage=Path(tmp)
            for name in SOURCE_NAMES+("analysis-report.json","result.json"):
                shutil.copy2(root/name,stage/name)
            if label=="missing_signal":(stage/SOURCE_NAMES[3]).unlink()
            else:
                path=stage/"analysis-report.json";obj=json.loads(path.read_text())
                obj["measurements"]["overtaken_response"]["value"]["max_right_shift_m"]+=0.25
                path.write_text(json.dumps(obj,indent=2)+"\n")
            try:audit(base_receipt,variant_receipt,comparison,stage)
            except ValueError as exc:negatives.append({"case":label,"rejected":True,"error":str(exc)})
            else:raise ValueError("Saved behavior negative unexpectedly passed: "+label)
    return {"format":"worker-overtaken-saved-behavior-proof",
            "auditor_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "base_receipt_sha256":hashlib.sha256(Path(base_receipt).read_bytes()).hexdigest(),
            "variant_receipt_sha256":hashlib.sha256(Path(variant_receipt).read_bytes()).hexdigest(),
            "positive":positive,"negative":negatives,"diagnostic_fixture_only":True}

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--base-receipt",required=True)
    parser.add_argument("--variant-receipt",required=True)
    parser.add_argument("--comparison",choices=tuple(PAIRS),required=True)
    args=parser.parse_args()
    print(json.dumps(proof(args.base_receipt,args.variant_receipt,args.comparison),indent=2))
