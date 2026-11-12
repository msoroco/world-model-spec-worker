"""Bind six independent diagnostic auditor proofs to selected delivery cases."""
from __future__ import annotations

import json
import shlex
from pathlib import Path

from source_join_audit import read, require, sha

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
AUDITOR = HERE / "delivery_audit.py"
PROVER = HERE / "prove-selected-delivery-case.py"
CHECKS = ["native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion"]
SUFFIXES = ("rail_reference", "rail_contrast", "oneway_absent", "oneway_present",
            "traversal_reference", "traversal_contrast")


def command(case: str, *, negative: bool) -> str:
    args = [".venv-cpu/bin/python", f"work/{HERE.name}/{PROVER.name}",
            "--case", case]
    if negative:
        args.append("--negative")
    return shlex.join(args)


def build() -> dict:
    manifest = read(MANIFEST)
    require(len(manifest["cases"]) == 6, "Selected manifest lacks six cases")
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(HERE.name + "__")
        require(suffix in SUFFIXES and entry["kind"] == "delivery",
                "Unselected acceptance case")
        proof_dir = HERE / "update024-delivery-case-proofs" / suffix
        positive, negative = (proof_dir / f"{name}.log" for name in ("positive", "negative"))
        outcome = json.loads(positive.read_text())
        require(outcome.get("case_id") == case and
                outcome.get("auditor_sha256") == sha(AUDITOR) and
                outcome.get("construction_sha256") == entry["construction_sha256"] and
                outcome.get("source_shape_passed") is True and
                outcome.get("delivery_accepted") is False and
                "Delivery construction differs from selected manifest" in negative.read_text(),
                "Selected delivery proof or rejection differs")
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["full-train"], "checks": CHECKS,
            "script": AUDITOR.name, "script_sha256": sha(AUDITOR),
            "command": command(case, negative=False), "test_exit_code": 0,
            "test_log": str(positive.relative_to(HERE)),
            "test_log_sha256": sha(positive),
            "negative_command": command(case, negative=True),
            "negative_exit_code": 1,
            "negative_expected_error": "Delivery construction differs from selected manifest",
            "negative_log": str(negative.relative_to(HERE)),
            "negative_log_sha256": sha(negative),
            "scope": "source-shaped CPU mechanics only; original Native acceptance unverified"}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    from scenario_pipeline.worker_exchange.delivery_handoff import validate_case
    for entry in manifest["cases"]:
        validate_case(HERE, entry, ["full-train"])
    return {"cases": len(manifest["cases"]), "manifest_sha256": sha(MANIFEST),
            "accepted_recordings": 0}


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT / "runtime/pipeline"))
    print(json.dumps(build()))
