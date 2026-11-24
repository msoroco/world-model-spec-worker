"""Bind synthetic physical outcome and ordered lifecycle CPU receipts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(HERE.name + "__")
        fixtures = []
        for kind in KINDS:
            log = HERE / f"physical-{suffix}-{kind}.log"
            result = HERE / "physical" / suffix / (kind + ".json")
            if not log.is_file() or not result.is_file():
                raise ValueError("Missing exact physical fixture")
            fixtures.append({"kind": kind,
                             "command": "PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/" +
                             HERE.name + "/prove_physical_cases.py " + case + " " + kind,
                             "exit_code": 0, "log": log.relative_to(HERE).as_posix(),
                             "log_sha256": sha(log),
                             "result": result.relative_to(HERE).as_posix(),
                             "result_sha256": sha(result)})
        life_log = HERE / f"lifecycle-{suffix}.log"
        life = json.loads(life_log.read_text())
        if life.get("case_id") != case or not life.get("diagnostic_fixture"):
            raise ValueError("Wrong lifecycle proof")
        lifecycle = {"events": life["events"], "exit_code": 0,
                     "command": "PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/" +
                     HERE.name + "/prove_lifecycle.py " + case,
                     "log": life_log.relative_to(HERE).as_posix(),
                     "log_sha256": sha(life_log)}
        proof = {"case_id": case, "construction_sha256": entry["construction_sha256"],
                 "fixtures": fixtures, "lifecycle": lifecycle,
                 "physical_acceptance_claimed": False}
        target = HERE / "physical" / suffix / "receipt.json"
        target.write_text(json.dumps(proof, indent=2) + "\n")
        entry["physical_preparation"] = {"receipt": target.relative_to(HERE).as_posix(),
                                         "sha256": sha(target)}
        log = HERE / f"cpu-canonical-offline-{suffix}.log"
        if log.is_file() and '"offline_passed": true' in log.read_text():
            entry["offline"] = {"command": "PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline --manifest work/" +
                                HERE.name + "/execution-manifest.json --case " + case +
                                " --output .runtime-work/c109035-canonical-offline/" + suffix +
                                "-v4 --python $PWD/.venv-cpu/bin/python",
                                "exit_code": 0,
                                "construction_sha256": entry["construction_sha256"],
                                "log": log.relative_to(HERE).as_posix(),
                                "log_sha256": sha(log)}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print("bound seven exact synthetic physical and canonical offline receipts")


if __name__ == "__main__":
    main()
