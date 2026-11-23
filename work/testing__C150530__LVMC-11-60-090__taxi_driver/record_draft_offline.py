"""Record pinned exact-case offline results without claiming delivery readiness."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = "testing__C150530__LVMC-11-60-090__taxi_driver"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record() -> dict:
    manifest = json.loads((ROOT / "execution-manifest.draft.json").read_text())
    proofs = []
    for entry in manifest["cases"]:
        case = entry["case_id"].removeprefix(ASSIGNMENT + "__")
        folder = ROOT / "cases" / case
        command_log = folder / "pinned-command.log"
        test_log = folder / "offline.log"
        result = json.loads(command_log.read_text())
        if (result.get("case_id") != entry["case_id"] or
                result.get("offline_passed") is not True or
                result.get("simulation_started") is not False or
                result.get("candidate_id") != "primary"):
            raise ValueError("pinned offline command did not pass exact case")
        if ("Ran 2 tests" not in test_log.read_text() or
                "static_construction_valid\": true" not in test_log.read_text() or
                "native_started\": false" not in test_log.read_text()):
            raise ValueError("exact materialized bundle tests incomplete")
        proof = {"case_id": entry["case_id"],
                 "construction_sha256": entry["construction_sha256"],
                 "command": "PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline --manifest work/" + ASSIGNMENT + "/execution-manifest.draft.json --case " + entry["case_id"] + " --output .runtime-work/c150530-offline-draft-" + case + "-20261122-v11 --python \"$PWD/.venv-cpu/bin/python\"",
                 "exit_code": 0,
                 "command_log": (folder / "pinned-command.log").relative_to(ROOT).as_posix(),
                 "command_log_sha256": sha(command_log),
                 "offline_log": (folder / "offline.log").relative_to(ROOT).as_posix(),
                 "offline_log_sha256": sha(test_log),
                 "readiness_claimed": False}
        proofs.append(proof)
    return {"format": "c150530-draft-offline-proofs-v1",
            "assignment_id": ASSIGNMENT, "cases": proofs,
            "limitation": "Pinned offline only; documentary, compatibility and saved-only proofs absent"}


if __name__ == "__main__":
    (ROOT / "pinned-offline-proofs.draft.json").write_text(json.dumps(record(), indent=2) + "\n")
