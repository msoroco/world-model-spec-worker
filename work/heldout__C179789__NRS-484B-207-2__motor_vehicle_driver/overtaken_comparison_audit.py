"""Check source-bound comparison isolation for overtaken-driver diagnostics."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import tempfile
from pathlib import Path


def audit(result_paths, comparison):
    if comparison not in ("right_shift", "speed_hold_until_complete", "right_pass_exception", "notice_modality"):
        raise ValueError("Unsupported overtaken-driver comparison")
    if len(result_paths) != 2:
        raise ValueError("Exactly two retained result paths are required")
    first, second = (json.loads(Path(path).read_text()) for path in result_paths)
    source = Path(__file__).with_name("overtaken_response.py")
    spec = importlib.util.spec_from_file_location("overtaken_response_for_audit", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for result in (first, second):
        hashes = result.get("source_sha256")
        if not isinstance(hashes, dict) or not all(hashes.get(key) for key in ("context", "events", "motion")):
            raise ValueError("Comparison lacks original source binding")
        paths = result.get("source_paths")
        if not isinstance(paths, dict) or not all(paths.get(key) for key in ("context", "events", "motion")):
            raise ValueError("Comparison lacks original source paths")
        for key in ("context", "events", "motion"):
            if hashlib.sha256(Path(paths[key]).read_bytes()).hexdigest() != hashes[key]:
                raise ValueError("Comparison original source changed: "+key)
        rebuilt = module.measure(paths["context"], paths["events"], paths["motion"])
        if rebuilt != result:
            raise ValueError("Comparison measurement differs from original sources")
        if result.get("legal_conclusion") is not None:
            raise ValueError("Diagnostic comparison cannot assert a legal conclusion")
    fixed = ("subject_id", "overtaker_id", "notice_frame", "pass_complete_frame",
             "road_source", "actor_source")
    if comparison != "notice_modality":
        fixed += ("notice_kind", "notice_source")
    if any(first.get(key) != second.get(key) for key in fixed):
        raise ValueError("Comparison changed held notice or actor conditions")
    if comparison == "right_shift":
        if first.get("right_pass_permitted_premise") != second.get("right_pass_permitted_premise"):
            raise ValueError("Right-shift comparison changed held exception premise")
        if first.get("max_precompletion_speed_delta_mps") != second.get("max_precompletion_speed_delta_mps"):
            raise ValueError("Right-shift comparison changed held motion")
        varied = "max_right_shift_m"
    elif comparison == "speed_hold_until_complete":
        if first.get("right_pass_permitted_premise") != second.get("right_pass_permitted_premise") or first.get("max_right_shift_m") != second.get("max_right_shift_m"):
            raise ValueError("Speed comparison changed held motion or exception premise")
        varied = "max_precompletion_speed_delta_mps"
    elif comparison == "right_pass_exception":
        if first.get("max_precompletion_speed_delta_mps") != second.get("max_precompletion_speed_delta_mps") or first.get("max_right_shift_m") != second.get("max_right_shift_m"):
            raise ValueError("Exception comparison changed held motion")
        varied = "right_pass_permitted_premise"
    else:
        if (first.get("right_pass_permitted_premise") != second.get("right_pass_permitted_premise")
                or first.get("max_precompletion_speed_delta_mps") != second.get("max_precompletion_speed_delta_mps")
                or first.get("max_right_shift_m") != second.get("max_right_shift_m")):
            raise ValueError("Notice comparison changed held motion or exception premise")
        varied = "notice_kind"
    if first.get(varied) == second.get(varied):
        raise ValueError("Comparison has no declared difference")
    return {"comparison_complete": True, "comparison": comparison, "declared_difference": varied,
            "source_hashes": [first["source_sha256"], second["source_sha256"]],
            "legal_conclusion": None}


def audit_saved_notice_pair(audible_receipt, observed_receipt, *, audible_root=None,
                            observed_root=None):
    """Independently verify the saved audible/observed notice comparison."""
    source = Path(__file__).with_name("overtaken_response.py")
    spec = importlib.util.spec_from_file_location("overtaken_saved_response_for_audit", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    receipts = [json.loads(Path(path).read_text()) for path in
                (audible_receipt, observed_receipt)]
    roots = [Path(override or receipt.get("analysis_directory", "")) for override, receipt in
             zip((audible_root, observed_root), receipts)]
    prefix = "heldout__C179789__NRS-484B-207-2__motor_vehicle_driver__"
    expected_ids = (prefix+"gives_way_holds_speed", prefix+"observed_gives_way_holds_speed")
    common = ("overtaken_source.jsonl", "video_frames.jsonl", "trace.jsonl")
    signal = ("signal_command_original.jsonl", "signal_audio_envelope_original.jsonl")
    measurements = []
    bodies = []
    for index, (receipt, root) in enumerate(zip(receipts, roots)):
        if (receipt.get("case_id") != expected_ids[index] or receipt.get("passed") is not True or
            receipt.get("originals_preserved") is not True or receipt.get("missing_evidence") is not False or
            receipt.get("physical_acceptance_claimed") is not False or
            receipt.get("legal_acceptance_claimed") is not False):
            raise ValueError("Saved comparison receipt identity or source status differs")
        names = common + signal if index == 0 else common
        for name in names:
            path = root/name
            if not path.is_file() or not path.read_bytes() or hashlib.sha256(path.read_bytes()).hexdigest() != receipt.get("original_source_hashes",{}).get(name):
                raise ValueError("Saved comparison original source changed: "+name)
        paths = [root/name for name in names]
        measured = (module.measure_audible_saved(*paths) if index == 0
                    else module.measure_observed_saved(*paths))
        report = json.loads((root/"analysis-report.json").read_text())
        result = json.loads((root/"result.json").read_text())
        if (report.get("case_id") != expected_ids[index] or result.get("case_id") != expected_ids[index] or
            report.get("measurements",{}).get("overtaken_response",{}).get("value") != measured or
            result.get("measured_values",{}).get("overtaken_response") != measured or
            result.get("physical_acceptance_claimed") is not False or
            result.get("legal_acceptance_claimed") is not False):
            raise ValueError("Saved comparison analysis differs from original sources")
        measurements.append(measured)
        bodies.append([json.loads(line) for line in (root/common[0]).read_text().splitlines() if line.strip()])
    if any(receipts[0]["original_source_hashes"][name] != receipts[1]["original_source_hashes"][name]
           for name in ("video_frames.jsonl", "trace.jsonl")):
        raise ValueError("Notice comparison changed held frame map or motion")
    for a, b in zip(*bodies):
        for row in (a,b):
            for name in ("notice_stimulus", "notice_observed", "visibility_relation"):
                row.pop(name,None)
        if a != b:
            raise ValueError("Notice comparison changed held actor, body or road conditions")
    first, second = measurements
    if (len(bodies[0]) != len(bodies[1]) or first["notice_frame"] != second["notice_frame"] or
        first["pass_complete_frame"] != second["pass_complete_frame"] or
        first["max_right_shift_m"] != second["max_right_shift_m"] or
        first["max_precompletion_speed_delta_mps"] != second["max_precompletion_speed_delta_mps"] or
        first["notice_kind"] != "audible_signal_command" or second["notice_kind"] != "observed_vehicle" or
        first["hearing_confirmed"] is not None):
        raise ValueError("Notice comparison changed held outcome or lacks declared modality difference")
    return {"format":"worker-overtaken-saved-comparison-audit", "comparison_complete":True,
            "comparison":"notice_modality", "declared_difference":"source-backed notice modality",
            "frames":len(bodies[0]), "notice_frame":first["notice_frame"],
            "pass_complete_frame":first["pass_complete_frame"],
            "held_motion_and_body":True, "hearing_confirmed":None,
            "physical_acceptance_claimed":False,"legal_acceptance_claimed":False,
            "source_hashes":[first["source_sha256"],second["source_sha256"]]}


def audit_saved_notice_pair_proof(audible_receipt, observed_receipt):
    """Run the positive comparison and two isolated source/hold negatives."""
    source = Path(__file__).with_name("overtaken_response.py")
    spec = importlib.util.spec_from_file_location("overtaken_saved_response_for_negative", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    audible_receipt, observed_receipt = Path(audible_receipt), Path(observed_receipt)
    saved = json.loads(audible_receipt.read_text())
    root = Path(saved["analysis_directory"])
    names = ("overtaken_source.jsonl", "video_frames.jsonl", "trace.jsonl",
             "signal_command_original.jsonl", "signal_audio_envelope_original.jsonl",
             "analysis-report.json", "result.json")
    positive = audit_saved_notice_pair(audible_receipt, observed_receipt)
    negatives = []
    for label in ("missing_signal", "changed_held_body"):
        with tempfile.TemporaryDirectory(prefix="overtaken-comparison-negative-") as temporary:
            stage = Path(temporary)
            for name in names:
                shutil.copy2(root/name, stage/name)
            modified = json.loads(audible_receipt.read_text())
            modified["analysis_directory"] = str(stage)
            if label == "missing_signal":
                (stage/names[3]).unlink()
            else:
                body = stage/names[0]
                rows = [json.loads(line) for line in body.read_text().splitlines() if line.strip()]
                rows[2]["right_pass_permission_verified"] = False
                body.write_text("".join(json.dumps(row, separators=(",", ":"))+"\n" for row in rows))
                modified["original_source_hashes"][names[0]] = hashlib.sha256(body.read_bytes()).hexdigest()
                measurement = module.measure_audible_saved(*(stage/name for name in names[:5]))
                for file_name, path in (("analysis-report.json", ("measurements", "overtaken_response", "value")),
                                        ("result.json", ("measured_values", "overtaken_response"))):
                    target_file = stage/file_name
                    content = json.loads(target_file.read_text())
                    target = content
                    for key in path[:-1]:
                        target = target[key]
                    target[path[-1]] = measurement
                    target_file.write_text(json.dumps(content, indent=2)+"\n")
            altered_receipt = stage/"saved-receipt.json"
            altered_receipt.write_text(json.dumps(modified, indent=2)+"\n")
            try:
                audit_saved_notice_pair(altered_receipt, observed_receipt)
            except ValueError as exc:
                message = str(exc)
                expected = ("Saved comparison original source changed: signal_command_original.jsonl"
                            if label == "missing_signal" else
                            "Notice comparison changed held actor, body or road conditions")
                if message != expected:
                    raise ValueError("Unexpected saved comparison negative: "+message) from exc
                negatives.append({"case":label, "rejected":True, "error":message})
            else:
                raise ValueError("Saved comparison negative unexpectedly passed: "+label)
    return {"format":"worker-overtaken-saved-comparison-proof",
            "auditor_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "audible_saved_receipt_sha256":hashlib.sha256(audible_receipt.read_bytes()).hexdigest(),
            "observed_saved_receipt_sha256":hashlib.sha256(observed_receipt.read_bytes()).hexdigest(),
            "positive":positive,"negative":negatives,"diagnostic_fixture_only":True}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--audible-receipt", required=True)
    parser.add_argument("--observed-receipt", required=True)
    args = parser.parse_args()
    print(json.dumps(audit_saved_notice_pair_proof(args.audible_receipt,
                                                    args.observed_receipt), indent=2))
