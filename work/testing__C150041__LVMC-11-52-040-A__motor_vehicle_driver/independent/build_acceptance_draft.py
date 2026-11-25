"""Bind the exact diagnostic CPU audit proofs without claiming delivery."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from delivery_audit import CHECKS, OBSERVATIONS, ROOT, SUFFIXES

REPO = ROOT.parents[1]
PYTHON = ".venv-cpu/bin/python"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parent
    plan = json.loads((ROOT / "case-plan.json").read_text())
    if {case["case_id"] for case in plan["cases"]} != {
            ROOT.name + "__" + suffix for suffix in SUFFIXES}:
        raise ValueError("exact case plan differs")
    entries = []
    tests = []
    for suffix in SUFFIXES:
        case_id = ROOT.name + "__" + suffix
        positive = root / (suffix + "-positive.log")
        negative = root / (suffix + "-negative.log")
        if ("diagnostic protocol positive and four negatives passed" not in positive.read_text()
                or "original pixel review missing or stale" not in negative.read_text()):
            raise ValueError("exact diagnostic audit proof missing: " + suffix)
        command = f"{PYTHON} work/{ROOT.name}/independent/prove_delivery_audit.py {case_id}"
        entries.append({
            "case_id": case_id, "sets": ["full-test"], "checks": list(CHECKS),
            "script": "independent/delivery_audit.py",
            "script_sha256": sha(root / "delivery_audit.py"),
            "command": command, "test_exit_code": 0,
            "test_log": "independent/" + positive.name,
            "test_log_sha256": sha(positive),
            "negative_command": command + " --negative", "negative_exit_code": 1,
            "negative_expected_error": "original pixel review missing or stale",
            "negative_log": "independent/" + negative.name,
            "negative_log_sha256": sha(negative),
            "original_capture_reviewed": False,
            "canonical_manifest_bound": False,
            "status": "diagnostic_cpu_protocol_only"})
        tests.extend((
            {"command": command, "exit_code": 0,
             "log": "independent/" + positive.name, "sha256": sha(positive)},
            {"command": command + " --negative", "exit_code": 1,
             "log": "independent/" + negative.name, "sha256": sha(negative)}))
        template = {"format": "worker-original-pixel-review", "case_id": case_id,
                    "diagnostic_fixture": False, "reviewer": None,
                    "video_sha256": None, "frame_map_sha256": None,
                    "core_trace_sha256": None,
                    "observations": {name: {"visible": None, "frame": None,
                                            "view": None, "description": None,
                                            "camera_sha256": None}
                                     for name in OBSERVATIONS}}
        (root / (suffix + "-pixel-review.template.json")).write_text(
            json.dumps(template, indent=2) + "\n")
    comparisons = []
    for item in plan["comparisons"]:
        pair = item["comparison_id"]
        log = root / (pair + "-comparison.log")
        if "measured diagnostic positive and missing-pixel/source negatives passed" not in log.read_text():
            raise ValueError("exact comparison CPU proof missing: " + pair)
        command = f"{PYTHON} work/{ROOT.name}/independent/prove_comparison_audit.py {pair}"
        comparisons.append({"comparison_id": pair, "case_ids": item["case_ids"],
                            "script": "independent/comparison_audit.py",
                            "script_sha256": sha(root / "comparison_audit.py"),
                            "proof_command": command,
                            "proof_log": "independent/" + log.name,
                            "proof_log_sha256": sha(log),
                            "original_comparison_accepted": False})
        tests.append({"command": command, "exit_code": 0,
                      "log": "independent/" + log.name, "sha256": sha(log)})
    draft = {"format": "c150041-delivery-acceptance-partial", "diagnostic_only": True,
             "cases": entries, "comparisons": comparisons,
             "missing": ["reviewed Native roadway/activity/Chapter source packet",
                         "source-backed semantic and judgment sweep",
                         "canonical six-case execution manifest and integration proof",
                         "original acquisition, physical, decode and pixel review receipts"]}
    (ROOT / "delivery-acceptance.partial.json").write_text(json.dumps(draft, indent=2) + "\n")
    result_path = ROOT / "result.json"
    result = json.loads(result_path.read_text())
    prior = [item for item in result["tests"] if not item["log"].startswith("independent/")]
    validation = root / "validate-acceptance-draft.log"
    if validation.is_file() and "six exact pinned delivery contracts" in validation.read_text():
        tests.append({"command": "export SCENARIO_PIPELINE_OUTPUT_ROOT=\"$PWD/.runtime-work/c150041-acceptance-draft-validation\"; "
                      "PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/" + ROOT.name +
                      "/independent/validate_acceptance_draft.py",
                      "exit_code": 0, "log": "independent/" + validation.name,
                      "sha256": sha(validation)})
    result["tests"] = prior + tests
    result["status"] = "partial"
    result["readiness_kind"] = "diagnostic_delivery_and_comparison_cpu_protocols_built"
    result["reason"] = ("Six exact independent delivery audit protocols and four measured comparison "
                        "protocols pass CPU diagnostic positive/negative proofs. Original Native "
                        "source review, source-backed semantic sweep, canonical execution manifest "
                        "and local integration, acquisition, physical completion, full decode and "
                        "pixel receipts remain incomplete; no original acceptance is claimed.")
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    print("bound", len(entries), "case and", len(comparisons), "comparison CPU protocols")


if __name__ == "__main__":
    main()
