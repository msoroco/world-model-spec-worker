"""Retain exact electric synthetic outcome and lifecycle CPU proofs."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    for machine in ("electric_bicycle", "electric_scooter"):
        for behavior in ("obey", "turn", "dismount"):
            label = f"{machine}_{behavior}"
            folder = ROOT / "electric-drafts" / label / "physical-proof"
            folder.mkdir(parents=True, exist_ok=True)
            fixtures = []
            for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
                result = folder / (kind + ".json")
                log = folder / (kind + ".log")
                command = [".venv-cpu/bin/python", str((ROOT / "prove-selected-physical.py").relative_to(REPO)),
                           "--case", label, "--kind", kind, "--output", str(result.relative_to(REPO))]
                with log.open("w") as stream:
                    run = subprocess.run(command, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT,
                                         env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
                if run.returncode:
                    raise RuntimeError("Electric physical CPU proof failed: " + label + "/" + kind)
                fixtures.append({"kind": kind, "command": " ".join(command), "exit_code": 0,
                                 "log": str(log.relative_to(ROOT)), "log_sha256": sha(log),
                                 "result": str(result.relative_to(ROOT)), "result_sha256": sha(result)})
            log = folder / "lifecycle.log"
            command = [".venv-cpu/bin/python", str((ROOT / "prove-selected-physical.py").relative_to(REPO)),
                       "--case", label, "--kind", "lifecycle"]
            with log.open("w") as stream:
                run = subprocess.run(command, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT,
                                     env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
            if run.returncode:
                raise RuntimeError("Electric lifecycle CPU proof failed: " + label)
            events = json.loads(log.read_text())["events"]
            construction = ROOT / "electric-drafts" / label / "construction.json"
            proof = {"format": "c104538-electric-physical-preparation-v1",
                     "case_id": f"{ROOT.name}__{label}",
                     "construction_sha256": sha(construction),
                     "scope": "synthetic source-row outcomes only; reviewed electric Native asset and original capture pending",
                     "fixtures": fixtures,
                     "lifecycle": {"events": events, "premature_rejected": True,
                                   "exit_code": 0, "log": str(log.relative_to(ROOT)),
                                   "log_sha256": sha(log)}}
            (folder / "proof.json").write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
