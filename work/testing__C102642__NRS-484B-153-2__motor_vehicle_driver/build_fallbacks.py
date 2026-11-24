"""Select an exact delayed-command fallback after a missing act readback."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
OLD = "if index == RATE_HZ * 10:"
NEW = "if index == RATE_HZ * 12:"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> None:
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        kind = entry["case_id"].rsplit("__", 1)[1]
        primary = json.loads((HERE / entry["construction"]).read_text())
        candidate = copy.deepcopy(primary)
        code = next(item for item in candidate["files"]
                    if item["path"] == "native_capture.py")
        if code["content"].count(OLD) != 1:
            raise ValueError("primary Native act command time changed")
        code["content"] = code["content"].replace(OLD, NEW)
        candidate["fallback_id"] = "fallback1"
        candidate["fallback_change"] = "Command selected act at 12 s after absent act readback at 10 s"
        path = HERE / f"construction-{kind}-fallback1.json"
        path.write_text(json.dumps(candidate, indent=2) + "\n")
        entry["candidates"] = [{
            "id": "fallback1", "construction": path.name,
            "construction_sha256": sha(path),
            "trigger": {"source": "original Native act observation and capture failure",
                        "metric": "source-confirmed selected act frame IDs",
                        "failure_condition": "primary 10 s command yielded no observed selected act"},
            "changed_knobs": ["Native act command tick moves from 10 s to 12 s"]}]
        entry["candidate_risk"] = {
            "status": "physical",
            "reason": "Original door act may fail to appear at the 10 s command; delayed act command is predeclared and still requires Native review"}
        print(kind, "fallback1", sha(path)[:12])
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    build()
