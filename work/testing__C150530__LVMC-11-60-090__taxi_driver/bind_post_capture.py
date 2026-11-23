"""Bind exact saved-only CPU proofs to the canonical taxi case manifest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "execution-manifest.json"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    queue = json.loads((ROOT / "queue-entries.partial.json").read_text())
    commands = {row["case_id"]: row["postprocessing_command"]
                for row in queue["cases"]}
    if (len(manifest["cases"]) != 3 or
            len(commands) != len(queue["cases"]) or
            set(commands) != {entry["case_id"] for entry in manifest["cases"]}):
        raise ValueError("three exact taxi saved-only commands required")
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(ROOT.name + "__")
        log = ROOT / "cases" / suffix / "canonical-saved-command.log"
        receipt = json.loads(log.read_text())
        if (receipt.get("case_id") != entry["case_id"] or
                receipt.get("passed") is not True or
                receipt.get("recorded_only") is not True or
                receipt.get("native_revision", {}).get("construction_sha256") !=
                entry["construction_sha256"]):
            raise ValueError("current construction lacks saved-only proof")
        command = commands[entry["case_id"]]
        if entry["case_id"] not in command or "runtime.py process-saved" not in command:
            raise ValueError("postprocessing command selects another case")
        entry["post_capture"] = {
            "recorded_only": True,
            "command": command,
            "feedback_command": command,
            "test_log": log.relative_to(ROOT).as_posix(),
            "test_log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
            "test_exit_code": 0,
            "proof_scope": "diagnostic saved-only CPU fixture; original Native capture unreviewed",
        }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print("three exact taxi saved-only commands and proofs bound")


if __name__ == "__main__":
    main()
