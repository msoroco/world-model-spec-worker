"""Bind the executed exact-case offline receipts into the selected manifest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(raw: str) -> str:
    return "\n".join(line.rstrip() for line in raw.splitlines()).rstrip() + "\n"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        tag = case_id.rsplit("__", 1)[-1]
        for candidate in ("primary", "fallback1"):
            proof = (REPO / ".runtime-work" /
                     f"c378304-offline-{tag}-{candidate}-v5")
            source = proof / "offline.log"
            command_log = Path(str(proof) + "-command.log")
            if (not source.is_file() or not command_log.is_file() or
                    json.loads(command_log.read_text()).get("offline_passed") is not True):
                raise ValueError("missing executed exact offline proof: " + tag + "/" + candidate)
            log_name = f"proof-offline-{tag}-{candidate}.log"
            log = ROOT / log_name
            log.write_text(clean(source.read_text()))
            command = (f"{REPO / '.venv-cpu/bin/python'} {REPO / 'runtime.py'} offline "
                       f"--manifest {MANIFEST} --case {case_id} --output {proof} "
                       f"--python {REPO / '.venv-cpu/bin/python'} --candidate {candidate}")
            selected = entry if candidate == "primary" else entry["candidates"][0]
            selected["offline"] = {"command": command, "exit_code": 0,
                                    "construction_sha256": selected["construction_sha256"],
                                    "log": log_name, "log_sha256": sha(log)}
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
