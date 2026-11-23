"""Retain each passed pinned offline log beside its exact compatibility receipt."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    proof = json.loads((ROOT / "cpu-offline-proof.json").read_text())
    if proof.get("all_passed") is not True:
        raise ValueError("eight-case pinned offline proof incomplete")
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        match = next((row for row in proof["results"] if row["case_id"] == entry["case_id"]), None)
        if match is None or match["exit_code"] != 0:
            raise ValueError("exact offline case absent: " + entry["case_id"])
        if proof["construction_hashes"][entry["case_id"]] != entry["construction_sha256"]:
            raise ValueError("offline construction changed")
        source = REPO / match["offline_log"]
        if sha(source) != match["offline_log_sha256"]:
            raise ValueError("offline log changed")
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        destination = ROOT / "diagnostics" / suffix / "offline.log"
        shutil.copyfile(source, destination)
        entry["offline"] = {"command": " ".join(match["command"]),
                            "construction_sha256": entry["construction_sha256"],
                            "exit_code": 0,
                            "log": str(destination.relative_to(ROOT)),
                            "log_sha256": sha(destination)}
        print("retained exact pinned offline log", suffix)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
