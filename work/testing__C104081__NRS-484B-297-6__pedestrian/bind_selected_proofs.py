"""Bind exact selected CPU proofs without changing construction bytes.

Compatibility and saved-only attempts are synthetic diagnostic receipts.
Production capture and independent pixel review remain source gated.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
VALIDATOR = ".runtime-work/c111125-owner/validator/.lake/build/bin/adapterCheck"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind() -> None:
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(ROOT.name + "__")
        for candidate in ("primary", "fallback1"):
            selected = entry if candidate == "primary" else entry["candidates"][0]
            construction_hash = selected["construction_sha256"]
            offline_log = ROOT / f"proof-selected-offline-{suffix}-{candidate}.log"
            if '"offline_passed": true' not in offline_log.read_text():
                raise ValueError("selected offline proof absent: " + suffix + candidate)
            offline_output = f".runtime-work/c104081-selected-v2-offline-{suffix}-{candidate}"
            selected["offline"] = {
                "command": f".venv-cpu/bin/python runtime.py offline --manifest work/{ROOT.name}/execution-manifest.json --case {case} --candidate {candidate} --output {offline_output}",
                "construction_sha256": construction_hash,
                "exit_code": 0, "log": offline_log.name,
                "log_sha256": sha(offline_log)}
            compatibility_output = REPO / ".runtime-work" / f"c104081-selected-v2-compat-{suffix}-{candidate}"
            receipt_source = compatibility_output / "compatibility.json"
            if not receipt_source.is_file():
                raise ValueError("selected compatibility proof absent: " + suffix + candidate)
            receipt = json.loads(receipt_source.read_text())
            if receipt.get("construction_sha256") != construction_hash or not receipt.get("passed"):
                raise ValueError("selected compatibility identity differs")
            files = {"receipt": "compatibility.json", "log": "compatibility-analysis.log",
                     "negative_log": "negative-analysis.log"}
            copied = {}
            for key, filename in files.items():
                target = ROOT / f"selected-{suffix}-{candidate}-{filename}"
                shutil.copyfile(compatibility_output / filename, target)
                copied[key] = target.name
            if sha(ROOT / copied["log"]) != receipt["log_sha256"] or \
                    sha(ROOT / copied["negative_log"]) != receipt["negative_log_sha256"]:
                raise ValueError("compatibility source log hash differs")
            selected["compatibility"] = {
                "command": f".venv-cpu/bin/python runtime.py compatibility --manifest work/{ROOT.name}/execution-manifest.json --case {case} --candidate {candidate} --output .runtime-work/c104081-selected-v2-compat-{suffix}-{candidate} --library runtime/library --validator {VALIDATOR}",
                "receipt": copied["receipt"], "sha256": sha(ROOT / copied["receipt"]),
                "log": copied["log"], "negative_log": copied["negative_log"]}
        entry["negative"] = {"log": entry["compatibility"]["negative_log"]}
        entry["acquisition"] = {
            "pedestrian_body_center_xy_m": {
                "entrypoint": "analysis.py",
                "method": "Twenty hertz source-bound projection of original Native walker body vertices and synchronized camera frames",
                "evidence": "channels/pedestrian_body_center_xy_m.jsonl"},
            "nearest_traffic_distance_m": {
                "entrypoint": "analysis.py",
                "method": "Twenty hertz source-bound projection of original Native walker and surveyed traffic actor centers",
                "evidence": "channels/nearest_traffic_distance_m.jsonl"}}
        positive = ROOT / f"proof-delivery-{suffix}-positive.log"
        negative = ROOT / f"proof-delivery-{suffix}-negative.log"
        script = ROOT / "prove_delivery_audit.py"
        if "synthetic CPU original-review fixture passed" not in positive.read_text() or \
                "original saved acquisition required for physical review" not in negative.read_text():
            raise ValueError("production review CPU fixtures incomplete")
        command = f".venv-cpu/bin/python work/{ROOT.name}/{script.name} {case}"
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["full-test"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "command": command, "negative_command": command + " --negative",
            "script": script.name, "script_sha256": sha(script),
            "test_exit_code": 0, "negative_exit_code": 1,
            "negative_expected_error": "original saved acquisition required for physical review",
            "test_log": positive.name, "test_log_sha256": sha(positive),
            "negative_log": negative.name, "negative_log_sha256": sha(negative),
            "scope": "Synthetic CPU source-review contract only; no original source or physical acceptance asserted"}
        saved_log = ROOT / f"proof-selected-saved-{suffix}.log"
        if saved_log.is_file() and '"passed": true' in saved_log.read_text():
            command = (f".venv-cpu/bin/python runtime.py process-saved --manifest work/{ROOT.name}/execution-manifest.json "
                       f"--case {case} --attempt \"$ATTEMPT\" --output \"$SAVED_OUTPUT\" "
                       f"--library \"$LIBRARY\" --validator \"$VALIDATOR\" "
                       f"--owner-release-receipt \"$OWNER_RELEASE_RECEIPT\"")
            entry["post_capture"] = {
                "recorded_only": True, "command": command, "feedback_command": command,
                "test_exit_code": 0, "test_log": saved_log.name,
                "test_log_sha256": sha(saved_log),
                "proof_scope": "Selected synthetic diagnostic saved-only processing; original Native source pending"}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print("bound", len(manifest["cases"]), "selected exact-case CPU proof sets")


if __name__ == "__main__":
    bind()
