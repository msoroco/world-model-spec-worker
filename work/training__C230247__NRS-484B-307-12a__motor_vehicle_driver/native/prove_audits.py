"""CPU source-structure tests for later independent original-delivery audits."""
import json
import os
from pathlib import Path
import subprocess
import sys

from comparison_audit import CASE_A, CASE_B, compare_structure
from delivery_audit import REQUIRED, audit_structure, sha

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
ATTEMPTS = (REPO / ".runtime-work/c230247-condition_a-compat-20261126h",
            REPO / ".runtime-work/c230247-condition_b-compat-20261126h")


def write(name, value):
    (ROOT / name).write_text(json.dumps(value, sort_keys=True) + "\n")


def inventory(attempt):
    return {name: sha(attempt / name) for name in (*REQUIRED, "config.json", "raw.mkv")}


def cli(script, args, log_name, expected):
    env = os.environ.copy()
    env["TMPDIR"] = str(REPO / ".runtime-work")
    env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(REPO / ".runtime-work/c230247")
    result = subprocess.run([sys.executable, str(ROOT / "native" / script), *map(str, args)],
        cwd=REPO, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, timeout=120)
    (ROOT / log_name).write_text(result.stdout.rstrip() + "\n")
    if expected == "positive" and result.returncode != 0:
        raise ValueError("Positive audit command failed: " + result.stdout[-1000:])
    if expected == "negative" and (result.returncode == 0 or
            "Original source inventory incomplete" not in result.stdout and
            "Original source hash changed" not in result.stdout):
        raise ValueError("Negative audit command failed to reject source")
    return result.returncode


def main():
    hashes = [inventory(attempt) for attempt in ATTEMPTS]
    for index, case in enumerate((CASE_A, CASE_B)):
        tag = "a" if index == 0 else "b"
        review = REPO / ".runtime-work" / ("c230247-audit-" + tag + "-review.json")
        review.write_text(json.dumps({"source_sha256": hashes[index]}) + "\n")
        missing = REPO / ".runtime-work" / ("c230247-audit-" + tag + "-missing-review.json")
        omitted = dict(hashes[index])
        omitted.pop("native-signal-rows.jsonl")
        missing.write_text(json.dumps({"source_sha256": omitted}) + "\n")
        cli("delivery_audit.py", ("--case", case, "--attempt", ATTEMPTS[index],
            "--review", review, "--structure-only"),
            "delivery-" + tag + "-positive.log", "positive")
        cli("delivery_audit.py", ("--case", case, "--attempt", ATTEMPTS[index],
            "--review", missing, "--structure-only"),
            "delivery-" + tag + "-negative.log", "negative")
        observed = audit_structure(ATTEMPTS[index], case, hashes[index])
        altered = dict(hashes[index])
        del altered["native-signal-rows.jsonl"]
        try:
            audit_structure(ATTEMPTS[index], case, altered)
        except ValueError as error:
            if "Original source inventory incomplete" not in str(error):
                raise
            pass
        else:
            raise ValueError("Missing-source delivery audit unexpectedly passed")
    comparison = compare_structure(*ATTEMPTS, *hashes)
    review_a = REPO / ".runtime-work/c230247-audit-a-review.json"
    review_b = REPO / ".runtime-work/c230247-audit-b-review.json"
    cli("comparison_audit.py", ("--condition-a", ATTEMPTS[0],
        "--condition-b", ATTEMPTS[1], "--review-a", review_a,
        "--review-b", review_b, "--structure-only"),
        "comparison-positive.log", "positive")
    altered = dict(hashes[1])
    altered["native-map-readback.xodr"] = "0" * 64
    altered_review = REPO / ".runtime-work/c230247-audit-b-changed-map-review.json"
    altered_review.write_text(json.dumps({"source_sha256": altered}) + "\n")
    cli("comparison_audit.py", ("--condition-a", ATTEMPTS[0],
        "--condition-b", ATTEMPTS[1], "--review-a", review_a,
        "--review-b", altered_review, "--structure-only"),
        "comparison-negative.log", "negative")
    try:
        compare_structure(*ATTEMPTS, hashes[0], altered)
    except ValueError as error:
        if "Original source hash changed" not in str(error):
            raise
        pass
    else:
        raise ValueError("Changed-map comparison unexpectedly passed")
    print(json.dumps({"passed": True, "delivery_cases": 2,
                      "comparison_pairs": 1, "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
