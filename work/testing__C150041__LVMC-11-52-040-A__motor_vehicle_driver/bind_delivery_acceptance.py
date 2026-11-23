"""Bind tested diagnostic delivery audit contracts to exact manifest cases."""
from __future__ import annotations

import json
import os
import hashlib
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
runtime_output = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "/")).resolve()
if not runtime_output.is_relative_to(REPO / ".runtime-work"):
    raise ValueError("set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
sys.path.insert(0, str(REPO / "runtime"))
from scenario_pipeline.worker_exchange.delivery_handoff import validate_case


def main() -> None:
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    draft = json.loads((ROOT / "delivery-acceptance.partial.json").read_text())
    if draft.get("diagnostic_only") is not True:
        raise ValueError("independent audit draft must remain diagnostic")
    receipts = {row["case_id"]: row for row in draft["cases"]}
    queue = json.loads((ROOT / "queue-entries.partial.json").read_text())
    commands = {row["case_id"]: row["postprocessing_command"]
                for row in queue["cases"]}
    if len(receipts) != len(draft["cases"]) or set(receipts) != {
            row["case_id"] for row in manifest["cases"]}:
        raise ValueError("six exact delivery contracts must match the manifest")
    if len(commands) != len(queue["cases"]) or set(commands) != set(receipts):
        raise ValueError("six saved processing commands must match the manifest")
    for entry in manifest["cases"]:
        receipt = dict(receipts[entry["case_id"]])
        if receipt.get("original_capture_reviewed") is not False or receipt.get("status") != "diagnostic_cpu_protocol_only":
            raise ValueError("audit proof must not claim original capture acceptance")
        receipt["canonical_manifest_bound"] = True
        validate_case(ROOT, {"case_id": entry["case_id"],
                             "delivery_acceptance": receipt}, {"full-test"})
        entry["delivery_acceptance"] = receipt
        suffix = entry["case_id"].removeprefix(ROOT.name + "__")
        log = ROOT / "diagnostic" / suffix / "cpu-delivery-saved-proof.log"
        saved = json.loads(log.read_text())
        if (saved.get("case_id") != entry["case_id"] or
                saved.get("passed") is not True or
                saved.get("recorded_only") is not True or
                saved.get("native_revision", {}).get("construction_sha256") !=
                entry["construction_sha256"]):
            raise ValueError("saved-only CPU proof is stale for " + entry["case_id"])
        command = commands[entry["case_id"]]
        if entry["case_id"] not in command or "runtime.py process-saved" not in command:
            raise ValueError("saved-only command selects another case")
        entry["post_capture"] = {
            "recorded_only": True,
            "command": command,
            "feedback_command": command,
            "test_exit_code": 0,
            "test_log": log.relative_to(ROOT).as_posix(),
            "test_log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
            "proof_scope": "synthetic saved-only CPU fixture; original capture unreviewed",
        }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print("six exact diagnostic delivery and saved-only contracts bound and validated")


if __name__ == "__main__":
    main()
