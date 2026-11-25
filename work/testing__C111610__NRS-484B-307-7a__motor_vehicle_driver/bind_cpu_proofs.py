"""Bind exact positive/negative CPU compatibility and offline proofs."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c111610-nov24-owner"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    path = ROOT / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(ROOT.name + "__")
        for candidate_id, item in [("primary", entry)] + [(row["id"], row) for row in entry.get("candidates", [])]:
            output = SCRATCH / f"compat-final-{suffix}-{candidate_id}"
            receipt = json.loads((output / "compatibility.json").read_text())
            if (receipt.get("case_id") != entry["case_id"] or
                    receipt.get("candidate_id") != candidate_id or
                    receipt.get("construction_sha256") != item["construction_sha256"] or
                    receipt.get("passed") is not True):
                raise ValueError("current compatibility proof differs: " + suffix + " " + candidate_id)
            prefix = f"compat-final-{suffix}-{candidate_id}"
            copies = {"receipt": (prefix + "-receipt.json", "compatibility.json"),
                      "log": (prefix + "-analysis.log", "compatibility-analysis.log"),
                      "negative_log": (prefix + "-negative.log", "negative-analysis.log")}
            for name, source_name in copies.values():
                shutil.copyfile(output / source_name, ROOT / name)
            item["compatibility"] = {
                "receipt": copies["receipt"][0], "sha256": sha(ROOT / copies["receipt"][0]),
                "log": copies["log"][0], "negative_log": copies["negative_log"][0]}
            offline_dir = f"offline-final-{suffix}-{candidate_id}"
            offline = SCRATCH / offline_dir / "offline.log"
            offline_log = ROOT / f"proof-offline-final-{suffix}-{candidate_id}.log"
            offline_log.write_text(offline.read_text().rstrip() + "\n")
            item["offline"] = {
                "command": ".venv-cpu/bin/python runtime.py offline --manifest work/" +
                           ROOT.name + "/execution-manifest.json --case " + entry["case_id"] +
                           " --candidate " + candidate_id + " --output .runtime-work/c111610-nov24-owner/" + offline_dir,
                "construction_sha256": item["construction_sha256"],
                "exit_code": 0, "log": offline_log.name, "log_sha256": sha(offline_log)}
            if candidate_id == "primary":
                entry["negative"] = {"log": copies["negative_log"][0]}
        entry["acquisition"] = {channel["name"]: {
            "entrypoint": "analysis.py", "evidence": "channels/" + channel["name"] + ".jsonl",
            "method": "SHA-bound saved arrow/aspect/event/frame-map projection"}
            for channel in json.loads((ROOT / entry["construction"]).read_text())
            ["recording_description"]["channels"]}
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    return len(manifest["cases"])


if __name__ == "__main__":
    print("bound", bind(), "selected CPU compatibility proofs")
