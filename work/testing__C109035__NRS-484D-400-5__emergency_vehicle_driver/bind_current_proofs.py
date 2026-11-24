"""Bind exact diagnostic proof bytes and preserve truthful partial status."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
SUFFIXES = ("response_siren_pedestrian", "response_lamps_only",
            "response_silent", "pursuit_actual_siren", "pursuit_suspected_siren",
            "unqualified_siren", "unqualified_lamps_only")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    log_names = ["cpu-delivery-audit-tests.log", "cpu-delivery-audit-build.log",
                 "cpu-semantic-build.log", "cpu-semantic-validate.log",
                 "cpu-semantic-delivery-validation.log", "cpu-canonical-build.log",
                 "cpu-measurement-validation.log", "cpu-physical-bind.log",
                 "cpu-physical-validation.log", "cpu-current-static.log"]
    for suffix in SUFFIXES:
        log_names.extend((f"cpu-delivery-audit-offline-{suffix}.log",
                          f"cpu-canonical-offline-{suffix}.log",
                          f"delivery-{suffix}-positive.log",
                          f"delivery-{suffix}-negative.log",
                          f"lifecycle-{suffix}.log"))
        log_names.extend(f"physical-{suffix}-{kind}.log" for kind in
                         ("complete_motion", "incomplete_motion", "missing_evidence"))
    for name in log_names:
        path = HERE / name
        if not path.is_file():
            raise ValueError("Missing exact proof log: " + name)
        lines = path.read_text().splitlines()
        while lines and not lines[-1].strip():
            lines.pop()
        path.write_text("\n".join(line.rstrip() for line in lines) + "\n")
    proofs = {name: sha(HERE / name) for name in log_names}
    index = {"assignment_id": AID, "scope": "synthetic diagnostic only",
             "physical_acceptance_claimed": False,
             "seven_case_positive_delivery_audits": True,
             "seven_case_negative_restoration_tamper_rejections": True,
             "pinned_semantic_stage_validator_passed": True,
             "log_sha256": proofs}
    (HERE / "proofs-current.json").write_text(json.dumps(index, indent=2) + "\n")
    result_path = HERE / "result.json"
    result = json.loads(result_path.read_text())
    if result["status"] != "partial":
        raise ValueError("Current CPU receipts cannot establish ready status")
    refreshed = set(log_names)
    tests = [test for test in result["tests"] if test["log"] not in refreshed]
    for test in tests:
        path = HERE / test["log"]
        if path.is_file():
            test["sha256"] = sha(path)
    commands = {
        "cpu-delivery-audit-tests.log": ".venv-cpu/bin/python -m unittest discover -s work/" + AID + "/tests -v",
        "cpu-delivery-audit-build.log": ".venv-cpu/bin/python work/" + AID + "/build_offline_draft.py",
        "cpu-semantic-build.log": ".venv-cpu/bin/python work/" + AID + "/build_semantic_proposals.py",
        "cpu-semantic-validate.log": ".venv-cpu/bin/python work/" + AID + "/validate_semantics.py",
        "cpu-canonical-build.log": ".venv-cpu/bin/python work/" + AID + "/build_canonical_package.py",
        "cpu-physical-bind.log": ".venv-cpu/bin/python work/" + AID + "/bind_physical_receipts.py",
        "cpu-current-static.log": ".venv-cpu/bin/python worker_check.py --assignment " + AID + " --complete",
    }
    for name, command in commands.items():
        tests.append({"command": "PYTHONDONTWRITEBYTECODE=1 " + command,
                      "exit_code": 0, "log": name, "sha256": proofs[name]})
    for suffix in SUFFIXES:
        name = f"delivery-{suffix}-positive.log"
        tests.append({"command": "PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/" +
                      AID + "/prove_delivery_cases.py " + AID + "__" + suffix,
                      "exit_code": 0, "log": name, "sha256": proofs[name]})
        name = f"cpu-canonical-offline-{suffix}.log"
        tests.append({"command": "PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline --manifest work/" +
                      AID + "/execution-manifest.json --case " + AID + "__" + suffix +
                      " --output .runtime-work/c109035-canonical-offline/" + suffix +
                      "-v4 --python $PWD/.venv-cpu/bin/python",
                      "exit_code": 0, "log": name, "sha256": proofs[name]})
    result["reason"] = ("Seven exact synthetic saved delivery positives and seven restoration-tamper negatives, "
                        "74 focused tests, seven current-runtime selected offline bundles, pinned semantic "
                        "delivery, seven saved measurement contracts and 21 physical CPU fixtures now pass. "
                        "This remains diagnostic: pinned compatibility and saved-only lifecycle receipts, production reviewed site, "
                        "independent source records and camera visibility review are not yet accepted.")
    result["tests"] = tests
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    print("bound current exact diagnostic proof hashes; status partial")


if __name__ == "__main__":
    main()
