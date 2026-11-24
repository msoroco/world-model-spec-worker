"""Bind source-shaped positive/negative CPU audits to exact delivery cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_log(source: Path, target: Path) -> None:
    lines = [line.rstrip() for line in source.read_text().splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    target.write_text("\n".join(lines) + "\n")


def bind() -> None:
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    result_path = HERE / "result.json"
    result = json.loads(result_path.read_text())
    script = HERE / "delivery_audit.py"
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.rsplit("__", 1)[-1]
        short = suffix.removeprefix("distance_").replace("_500ft", "")
        version = "v2" if short == "at" else "v1"
        source = SCRATCH / f"c129731-audit-{short}-{version}.json"
        audit = json.loads(source.read_text())
        required = ("all_participants", "time_join", "full_video_decode", "actual_pixels")
        if (audit.get("case_id") != case or audit.get("cpu_test") is not True
                or audit.get("passed") is not False
                or audit.get("auditor_sha256") != sha(script)
                or audit.get("frames") != 900
                or not all(audit["checks"].get(name) is True for name in required)
                or audit["checks"].get("native_source") is not False
                or audit["checks"].get("physical_completion") is not False):
            raise ValueError("Diagnostic audit misstates its source scope: " + suffix)
        receipt = HERE / f"cpu-delivery-audit-{suffix}.json"
        receipt.write_bytes(source.read_bytes())
        log = HERE / f"cpu-delivery-audit-{suffix}.log"
        negative = HERE / f"negative-delivery-audit-{suffix}.log"
        clean_log(SCRATCH / f"c129731-audit-{short}-{version}.log", log)
        clean_log(SCRATCH / f"c129731-audit-{short}-negative-v2.log", negative)
        expected = "missing delivery source: sight_rays.json"
        if ("software_checks_passed\": true" not in log.read_text()
                or "canonical_eligible\": false" not in log.read_text()
                or expected not in negative.read_text()):
            raise ValueError("Positive/negative audit proof incomplete: " + suffix)
        command = (f".venv-cpu/bin/python work/{HERE.name}/delivery_audit.py "
                   f"--attempt .runtime-work/c129731-compat-{suffix}-v12 --case {case} "
                   f"--job cpu-fixture-{short} --attempt-number 1 --recording cpu-fixture-{short} "
                   f"--decode-receipt .runtime-work/c129731-audit-{short}-decode-{version}.json "
                   f"--output .runtime-work/c129731-audit-{short}-{version}.json --cpu-test")
        negative_command = command.replace(
            f"c129731-compat-{suffix}-v12", f"c129731-audit-negative-{short}-v1")
        negative_command = negative_command.replace(
            f"c129731-audit-{short}-decode-{version}.json",
            f"c129731-audit-{short}-negative-decode-v2.json")
        negative_command = negative_command.replace(
            f"c129731-audit-{short}-{version}.json",
            f"c129731-audit-{short}-negative-v2.json")
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["demo-test", "full-test"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "script": script.name, "script_sha256": sha(script),
            "command": command, "test_exit_code": 0,
            "test_log": log.name, "test_log_sha256": sha(log),
            "negative_command": negative_command, "negative_exit_code": 1,
            "negative_expected_error": expected,
            "negative_log": negative.name, "negative_log_sha256": sha(negative),
            "cpu_audit_receipt": receipt.name, "cpu_audit_receipt_sha256": sha(receipt),
            "proof_scope": "source-shaped diagnostic method only; canonical acceptance requires original Native evidence",
        }
        result["tests"] = [row for row in result["tests"] if row["log"] != log.name]
        result["tests"].append({"command": command, "exit_code": 0,
                                "log": log.name, "sha256": sha(log)})
        print(suffix, sha(log), sha(negative))
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    result_path.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    bind()
