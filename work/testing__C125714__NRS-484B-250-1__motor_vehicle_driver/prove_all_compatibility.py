"""Run pinned software compatibility for all seven synthetic diagnostic cases."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SUFFIXES = ("precedence", "advance", "other_later", "opposite_straight",
            "opposite_intends_left", "opposite_makes_left", "wide_same_crossing")
EXPECTED = {
    "precedence": (True, False, False, "east"),
    "advance": (True, False, False, "east"),
    "other_later": (False, False, False, "east"),
    "opposite_straight": (True, False, False, "east"),
    "opposite_intends_left": (True, True, False, "east"),
    "opposite_makes_left": (True, True, True, "east"),
    "wide_same_crossing": (True, False, False, "west"),
}


def prove(output_root, validator):
    output_root = Path(output_root).resolve()
    if REPO / ".runtime-work" not in output_root.parents or output_root.exists():
        raise ValueError("Use a fresh output root beneath .runtime-work")
    runtime_output = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
    if not runtime_output or REPO / ".runtime-work" not in Path(runtime_output).resolve().parents:
        raise ValueError("Export SCENARIO_PIPELINE_OUTPUT_ROOT beneath .runtime-work")
    output_root.mkdir(parents=True)
    results = []
    for suffix in SUFFIXES:
        folder = ROOT if suffix == "precedence" else ROOT / "cases" / suffix
        case_id = ROOT.name + "__" + suffix
        output = output_root / suffix
        command = [sys.executable, str(REPO / "runtime.py"), "compatibility",
                   "--manifest", str(ROOT / "diagnostic-execution-manifest.json"),
                   "--case", case_id, "--output", str(output),
                   "--library", str(REPO / "runtime" / "library"),
                   "--validator", str(Path(validator).resolve())]
        command_log = folder / "diagnostic-compatibility-command.log"
        with command_log.open("w") as stream:
            status = subprocess.run(command, cwd=REPO, env=os.environ,
                                    stdout=stream, stderr=subprocess.STDOUT,
                                    timeout=600).returncode
        if status:
            raise ValueError("Compatibility failed for " + suffix +
                             "; inspect " + str(command_log))
        receipt = json.loads((output / "compatibility.json").read_text())
        if receipt.get("passed") is not True or receipt.get("case_id") != case_id:
            raise ValueError("Compatibility receipt mismatched " + suffix)
        observed = receipt["measurement_examples"]["crossing_entry_measurement"]["value"]
        actual = (observed["other_entered_before_ego"],
                  observed["opposite_left_exclusion"],
                  observed["observed_left_turn"],
                  observed["ego_approach_direction"])
        if actual != EXPECTED[suffix] or observed["legal_judgment"] != "unresolved":
            raise ValueError("Diagnostic source measurement differs for " + suffix)
        if (receipt["negative_removed"] != "other-body-history.jsonl" or
                receipt["negative_error_contains"] not in
                (output / "negative-analysis.log").read_text()):
            raise ValueError("Missing case-source negative proof for " + suffix)
        contract_hash = hashlib.sha256((folder / "measurement-contract.json").read_bytes()).hexdigest()
        if receipt["measurement_contract_sha256"] != contract_hash:
            raise ValueError("Measurement contract changed for " + suffix)
        for name, returned in (("compatibility.json", "diagnostic-compatibility.json"),
                               ("compatibility-analysis.log", "diagnostic-compatibility-analysis.log"),
                               ("negative-analysis.log", "diagnostic-compatibility-negative.log")):
            shutil.copyfile(output / name, folder / returned)
        results.append({"case_id": case_id, "passed": True,
                        "diagnostic_only": True, "receipt": str((folder / "diagnostic-compatibility.json").relative_to(ROOT))})
        print(json.dumps(results[-1]), flush=True)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--validator", required=True)
    args = parser.parse_args()
    prove(args.output_root, args.validator)
