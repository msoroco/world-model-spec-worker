"""Construct exact CPU sweep candidates from source-matched authored cases."""

import copy
import hashlib
import json
import shutil
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = {
    "signal-appropriateness-pending-0000": "left_signal_late_clear_gap",
    "signal-appropriateness-pending-0001": "left_signal_before_clear_gap",
    "signal-appropriateness-pending-0002": "left_signal_at_departure_clear_gap",
    "safety-ascertainment-pending-0000": "left_signal_before_close_gap",
    "safety-ascertainment-pending-0001": "left_signal_before_clear_gap",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":")) + "\n")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Candidate exceeds returned file limit")


def build():
    stage = json.loads((HERE / "physical-sweep-stage-proof.json").read_text())
    if set(stage["case_ids"]) != set(SOURCE):
        raise ValueError("Generated sweep identity changed")
    selected = json.loads((HERE / "execution-manifest.json").read_text())
    zero = json.loads((HERE / "zero-execution-manifest.json").read_text())
    staged_cases = json.loads((ROOT / ".runtime-work" / "c144550-physical-sweeps" / "cases.json").read_text())
    sweep_cases = {c["case_id"]: c for c in staged_cases["cases"] if c.get("sweep_id")}
    entries = {e["case_id"].split("__")[-1]: e for e in selected["cases"]}
    entries["left_signal_at_departure_clear_gap"] = zero["cases"][0]
    output = {"format": selected["format"], "assignment_id": selected["assignment_id"],
              "runtime_manifest_sha256": sha(ROOT / "runtime/SOURCE-MANIFEST.json"),
              "cases": []}
    for case, donor in SOURCE.items():
        original = entries[donor]
        donor_path = HERE / original["construction"]
        construction = json.loads(donor_path.read_text())
        constructed_id = case
        construction["case_id"] = constructed_id
        construction["recording_description"] = copy.deepcopy(sweep_cases[case]["recording_description"])
        files = {item["path"]: item for item in construction["files"]}
        config = json.loads(files["config.json"]["content"])
        config["selected_case_id"] = constructed_id
        config["recording_description"] = copy.deepcopy(construction["recording_description"])
        donor_id = HERE.name + "__" + donor
        config["supported_case_ids"].insert(config["supported_case_ids"].index(donor_id) + 1, constructed_id)
        files["config.json"]["content"] = json.dumps(config, indent=2) + "\n"
        for name in ("native_lane_construction.py", "lane_change_measurements.py"):
            content = files[name]["content"]
            old_line = next((line for line in content.splitlines()
                             if line.lstrip().startswith('"' + donor + '":')), None)
            if old_line is None:
                raise ValueError("Donor policy missing in " + name + ": " + donor)
            content = content.replace(old_line, old_line + "\n" + old_line.replace('"' + donor + '"', '"' + case + '"'), 1)
            suffix_expr = 'case_id[len(CASE_PREFIX):] if case_id.startswith(CASE_PREFIX) else ""'
            content = content.replace(suffix_expr,
                                      'case_id[len(CASE_PREFIX):] if case_id.startswith(CASE_PREFIX) else (case_id if case_id in SIGNAL_CASES else "")' if name == "native_lane_construction.py" else
                                      'case_id[len(CASE_PREFIX):] if case_id.startswith(CASE_PREFIX) else (case_id if case_id in CASE_PATTERNS else "")')
            if name == "lane_change_measurements.py":
                content = content.replace(
                    'case_id[len(CASE_PREFIX):] if isinstance(case_id,str) and case_id.startswith(CASE_PREFIX) else ""',
                    'case_id[len(CASE_PREFIX):] if isinstance(case_id,str) and case_id.startswith(CASE_PREFIX) else (case_id if isinstance(case_id,str) and case_id in CASE_PATTERNS else "")')
                anchor = '    evidence=[]\n    for name,(unit,extract) in channels.items():'
                if anchor not in content:
                    raise ValueError("Recording evidence insertion point missing")
                content = content.replace(anchor,
                    '    sweep_specs=' + repr(sweep_cases[case]["sweep_measurements"]) + '\n'
                    '    departure=observations["first_body_leaves_lane"]["frame"]\n'
                    '    first_signal=observations["first_appropriate_signal"]\n'
                    '    movement=next(row for row in observations["samples"] if row["frame"]==departure)\n'
                    '    if first_signal is None:raise ValueError("Appropriate signal source absent")\n'
                    '    sweep_values={"appropriate_signal_lead_frames":departure-first_signal["frame"],\n'
                    '                  "nearest_target_body_gap_at_departure_m":movement["nearest_target_body_longitudinal_gap_m"]}\n'
                    '    sweep_realized={}\n' + anchor, 1)
                anchor2 = '    lane_inventory={"marked_same_direction_lane_inventory"'
                if anchor2 not in content:
                    raise ValueError("Derived sweep channel insertion point missing")
                content = content.replace(anchor2,
                    '    for axis in sweep_specs:\n'
                    '        name=axis["observable"];value=sweep_values[name]\n'
                    '        path=channel_dir/(name+".jsonl")\n'
                    '        path.write_text(json.dumps({"original_frame":departure,"time_s":movement["time_s"],"value":value},allow_nan=False)+"\\n")\n'
                    '        reference="channels/"+path.name\n'
                    '        evidence.append({"name":name,"unit":axis["unit"],"reference":reference})\n'
                    '        sweep_realized[name]={"value":value,"unit":axis["unit"],\n'
                    '            **axis["measurement"],"reference":reference}\n' + anchor2, 1)
                content = content.replace('"source_evidence_hashes":report["sources"],"realized_observables":{}}',
                                          '"source_evidence_hashes":report["sources"],"realized_observables":sweep_realized}')
            if name == "native_lane_construction.py":
                content = content.replace('if not case_id.startswith(CASE_PREFIX) or case_id[len(CASE_PREFIX):] not in SIGNAL_CASES:',
                                          'if not (case_id.startswith(CASE_PREFIX) and case_id[len(CASE_PREFIX):] in SIGNAL_CASES or case_id in SIGNAL_CASES):')
                content = content.replace('direction,policy=SIGNAL_CASES[case_id[len(CASE_PREFIX):]]',
                                          'direction,policy=SIGNAL_CASES[case_id[len(CASE_PREFIX):] if case_id.startswith(CASE_PREFIX) else case_id]')
            if donor == "left_signal_at_departure_clear_gap" and name == "native_lane_construction.py":
                old_guard = 'case_id.endswith("__left_signal_at_departure_clear_gap")'
                if old_guard not in content:
                    raise ValueError("Zero-stage guard missing")
                content = content.replace(old_guard, '(' + old_guard + ' or case_id == "' + case + '")', 1)
            files[name]["content"] = content
            files[name]["source"] = None
        runner = files["runner.py"]["content"]
        runner = runner.replace('expected=[CASE_PREFIX+suffix for suffix in SIGNAL_CASES]',
                                'expected=[suffix if suffix == "' + case + '" else CASE_PREFIX+suffix for suffix in SIGNAL_CASES]')
        runner = runner.replace('suffix=case_id[len(CASE_PREFIX):]',
                                'suffix=case_id[len(CASE_PREFIX):] if case_id.startswith(CASE_PREFIX) else case_id')
        files["runner.py"]["content"] = runner
        files["runner.py"]["source"] = None
        path = HERE / "sweep-cases" / case / "construction.json"
        write(path, construction)
        entry = {"case_id": constructed_id, "kind": "delivery",
                 "construction": str(path.relative_to(HERE)),
                 "construction_sha256": sha(path),
                 "fixture_recipe": original["fixture_recipe"],
                 "candidate_risk": copy.deepcopy(original["candidate_risk"]),
                 "candidates": [], "status": "unselected_sweep_cpu_candidate"}
        for key in ("measurement_contract", "measurement_procedure", "acquisition"):
            entry[key] = copy.deepcopy(original[key])
        output["cases"].append(entry)
    write(HERE / "sweep-execution-manifest.json", output)
    staging = ROOT / ".runtime-work" / "c144550-sweep-compat-stage"
    plan = json.loads((HERE / "case-plan.json").read_text())
    plan["requirement_dispositions"][0]["case_ids"].extend(SOURCE)
    write(staging / "case-plan.json", plan)
    shutil.copyfile(HERE / "measurement-contract.json", staging / "measurement-contract.json")
    (staging / "proposals").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / ".runtime-work" / "c144550-physical-sweeps" / "cases.json",
                    staging / "proposals" / "cases.json")
    for entry in output["cases"]:
        target = staging / entry["construction"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(HERE / entry["construction"], target)
    write(staging / "execution-manifest.json", output)
    return {"case_count": len(output["cases"]), "manifest_sha256": sha(HERE / "sweep-execution-manifest.json"),
            "candidate_ids": [e["case_id"] for e in output["cases"]],
            "selected_for_delivery": False}


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
