"""Bind seven exact CPU audit proofs without claiming original delivery readiness."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    cases = [entry["case_id"] for entry in plan["cases"]]
    if len(cases) != 7 or len(set(cases)) != 7:
        raise ValueError("seven exact delivery cases required")
    script = Path("independent/delivery_audit.py")
    rows = []
    for case in cases:
        suffix = case.removeprefix(ROOT.name + "__")
        if suffix == case:
            raise ValueError("case belongs to another assignment")
        positive = Path("independent") / (suffix + "-positive.log")
        negative = Path("independent") / (suffix + "-negative.log")
        if "original pixel review missing or stale" not in (ROOT / negative).read_text():
            raise ValueError("negative proof did not reject stale original pixels")
        command = ("PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/" + ROOT.name +
                   "/independent/prove_delivery_audit.py " + case)
        rows.append({"case_id": case, "sets": ["full-test"],
                     "checks": list(CHECKS), "script": script.as_posix(),
                     "script_sha256": sha(ROOT / script),
                     "command": command, "test_exit_code": 0,
                     "test_log": positive.as_posix(), "test_log_sha256": sha(ROOT / positive),
                     "negative_command": command + " --negative", "negative_exit_code": 1,
                     "negative_expected_error": "original pixel review missing or stale",
                     "negative_log": negative.as_posix(),
                     "negative_log_sha256": sha(ROOT / negative)})
    output = {"format": "worker-delivery-acceptance-cpu-draft",
              "assignment_id": ROOT.name, "cases": rows,
              "original_capture_reviewed": False,
              "canonical_execution_manifest_bound": False}
    (ROOT / "delivery-acceptance.partial.json").write_text(json.dumps(output, indent=2) + "\n")
    print("Seven source-bound independent audit contracts drafted for " + ROOT.name)


if __name__ == "__main__":
    main()
