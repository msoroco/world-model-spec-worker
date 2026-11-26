"""Prove synthetic physical outcome triads for source-gated selections."""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from physical_completion import assess
from prove_physical_preparation import EVENTS, capture, lifecycle

HERE = Path(__file__).resolve().parent
SCRATCH = HERE.parents[1] / ".runtime-work/c158208-owner-nov26b/physical-v1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def prove() -> dict:
    manifest_path = HERE / "execution-manifest.source-gated-draft.json"
    manifest = json.loads(manifest_path.read_text())
    SCRATCH.mkdir(parents=True, exist_ok=True)
    count = 0
    for entry in manifest["cases"]:
        kind = entry["case_id"].split("__")[-1]
        case_id = entry["case_id"]
        construction_sha = entry["construction_sha256"]
        target = HERE / "cases" / kind / "primary" / "physical"
        target.mkdir(parents=True, exist_ok=True)
        fixtures = []
        with tempfile.TemporaryDirectory(prefix=kind + "-", dir=SCRATCH) as temporary:
            for fixture, expected in (("complete_motion", "met"),
                                      ("incomplete_motion", "not_met"),
                                      ("missing_evidence", "unverified")):
                attempt = Path(temporary) / fixture
                attempt.mkdir()
                if fixture != "missing_evidence":
                    capture(attempt, incomplete=(fixture == "incomplete_motion"))
                result = assess(attempt, case_id, construction_sha, diagnostic_fixture=True)
                if result["physical_checks"]["maneuver"]["status"] != expected:
                    raise ValueError("physical fixture differs: " + kind + " " + fixture)
                output = target / (fixture + ".json")
                log = target / (fixture + ".log")
                write(output, result)
                log.write_text("synthetic physical " + case_id + " " + fixture + ": " + expected + "\n")
                fixtures.append({"kind": fixture, "command": "prove_deferred_physical.py " + fixture,
                                 "exit_code": 0, "log": str(log.relative_to(HERE)),
                                 "log_sha256": sha(log), "result": str(output.relative_to(HERE)),
                                 "result_sha256": sha(output)})
        lifecycle(EVENTS)
        try:
            lifecycle([event for event in EVENTS if event != "owner_released"])
        except ValueError:
            pass
        else:
            raise ValueError("missing owner release accepted")
        life_log = target / "lifecycle.log"
        life_log.write_text("synthetic lifecycle: " + ", ".join(EVENTS) +
                            "\nnegative: missing owner release rejected\n")
        proof = {"case_id": case_id, "construction_sha256": construction_sha,
                 "provenance_kind": "synthetic_fixture", "fixtures": fixtures,
                 "lifecycle": {"events": EVENTS, "exit_code": 0,
                               "log": str(life_log.relative_to(HERE)),
                               "log_sha256": sha(life_log)},
                 "physical_acceptance_claimed": False}
        receipt = target / "physical-preparation.json"
        write(receipt, proof)
        entry["physical_preparation"] = {"receipt": str(receipt.relative_to(HERE)),
                                         "sha256": sha(receipt)}
        count += 1
    write(manifest_path, manifest)
    return {"physical_triads": count, "manifest_sha256": sha(manifest_path),
            "scope": "synthetic_cpu_only"}


if __name__ == "__main__":
    print(json.dumps(prove(), indent=2))
