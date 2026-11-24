"""Bind five exact delayed-command candidate CPU proofs to selection."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work/c102642-selected"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record() -> None:
    path = HERE / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    for entry in manifest["cases"]:
        kind = entry["case_id"].rsplit("__", 1)[1]
        candidate = entry["candidates"][0]
        case = HERE / "cases" / kind
        offline = SCRATCH / f"offline-{kind}-fallback1-v2/offline.log"
        output = SCRATCH / f"compat-{kind}-fallback1-v2"
        for name, source in (("fallback1-offline.log", offline),
                             ("fallback1-compatibility-analysis.log", output / "compatibility-analysis.log"),
                             ("fallback1-negative-analysis.log", output / "negative-analysis.log"),
                             ("fallback1-compatibility.json", output / "compatibility.json")):
            if not source.is_file():
                raise ValueError("fallback CPU proof missing: " + str(source))
            shutil.copyfile(source, case / name)
        receipt = json.loads((case / "fallback1-compatibility.json").read_text())
        if (receipt["candidate_id"] != "fallback1" or
                receipt["construction_sha256"] != candidate["construction_sha256"] or
                sha(case / "fallback1-compatibility-analysis.log") != receipt["log_sha256"] or
                sha(case / "fallback1-negative-analysis.log") != receipt["negative_log_sha256"]):
            raise ValueError("fallback receipt changed: " + kind)
        candidate["offline"] = {
            "command": f".venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/execution-manifest.json --case {entry['case_id']} --candidate fallback1 --output .runtime-work/c102642-selected/offline-{kind}-fallback1-v2 --python .venv-cpu/bin/python",
            "exit_code": 0,
            "construction_sha256": candidate["construction_sha256"],
            "log": f"cases/{kind}/fallback1-offline.log",
            "log_sha256": sha(case / "fallback1-offline.log")}
        candidate["compatibility"] = {
            "receipt": f"cases/{kind}/fallback1-compatibility.json",
            "sha256": sha(case / "fallback1-compatibility.json"),
            "log": f"cases/{kind}/fallback1-compatibility-analysis.log",
            "negative_log": f"cases/{kind}/fallback1-negative-analysis.log"}
        print(kind, "fallback1 CPU receipt", sha(case / "fallback1-compatibility.json")[:12])
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    record()
