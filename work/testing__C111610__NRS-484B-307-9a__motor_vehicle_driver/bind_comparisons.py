"""Bind four exact diagnostic comparison proofs after their CPU replay."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    plan = json.loads((HERE / "case-plan.json").read_text())
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    result = []
    for pair in plan["comparisons"]:
        name = pair["comparison_id"]
        positive = HERE / ("proof-comparison-" + name + ".log")
        negative = HERE / ("proof-comparison-" + name + "-negative.log")
        receipt = json.loads(positive.read_text())
        if (receipt.get("comparison_id") != name or
                receipt.get("case_suffixes") != [case.rsplit("__", 1)[-1] for case in pair["case_ids"]] or
                receipt.get("decoded_view_frames") != 4800 or
                receipt.get("physical_acceptance") is not False or
                "source hash mismatch" not in negative.read_text()):
            raise ValueError("comparison replay proof incomplete: " + name)
        command = f".venv-cpu/bin/python comparison_probe.py --comparison {name}"
        result.append({"comparison_id": name, "case_ids": pair["case_ids"],
                       "fixed_conditions": pair["fixed_conditions"],
                       "deliberate_differences": pair["deliberate_differences"],
                       "audit_script": "comparison_probe.py",
                       "audit_script_sha256": sha(HERE / "comparison_probe.py"),
                       "production_command": f".venv-cpu/bin/python saved_pair.py --comparison {name} --left-attempt $LEFT_ATTEMPT --right-attempt $RIGHT_ATTEMPT",
                       "diagnostic_cpu_proof": {"command": command, "exit_code": 0,
                           "log": positive.name, "log_sha256": sha(positive),
                           "negative_command": command + " --negative",
                           "negative_exit_code": 1, "negative_expected_error": "source hash mismatch",
                           "negative_log": negative.name, "negative_log_sha256": sha(negative),
                           "source_bound_saved_replay": receipt,
                           "physical_acceptance_claimed": False}})
    manifest["comparisons"] = result
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print("bound", len(result), "source-replay comparison proofs")


if __name__ == "__main__":
    bind()
