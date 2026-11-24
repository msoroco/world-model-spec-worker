"""Bind the tested exact pedestrian camera fallback candidate."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SUFFIX = "response_siren_pedestrian"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    path = HERE / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    entry = next(item for item in manifest["cases"] if item["case_id"].endswith("__" + SUFFIX))
    candidate = entry["candidates"][0]
    if candidate["id"] != "fallback1" or candidate["construction_sha256"] != sha(HERE / candidate["construction"]):
        raise ValueError("Fallback candidate changed")
    offline_log = HERE / "cpu-offline-response_siren_pedestrian-fallback1-v9.log"
    if '"offline_passed": true' not in offline_log.read_text():
        raise ValueError("Fallback offline proof missing")
    candidate["offline"] = {
        "command": "PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline --manifest work/" +
                   HERE.name + "/execution-manifest.json --case " + entry["case_id"] +
                   " --candidate fallback1 --output .runtime-work/c109035-offline-response_siren_pedestrian-fallback1-v9 --python $PWD/.venv-cpu/bin/python",
        "exit_code": 0, "construction_sha256": candidate["construction_sha256"],
        "log": offline_log.name, "log_sha256": sha(offline_log)}
    output = REPO / ".runtime-work/c109035-compat-response_siren_pedestrian-fallback1-v9"
    receipt = json.loads((output / "compatibility.json").read_text())
    if (receipt.get("case_id") != entry["case_id"] or
            receipt.get("candidate_id") != "fallback1" or
            receipt.get("construction_sha256") != candidate["construction_sha256"] or
            receipt.get("passed") is not True):
        raise ValueError("Fallback compatibility source differs")
    destination = HERE / "compat-response_siren_pedestrian-fallback1-receipt.json"
    destination.write_text(json.dumps(receipt, indent=2) + "\n")
    names = {}
    for source_name in ("compatibility-analysis.log", "negative-analysis.log"):
        source = output / source_name
        key = ("negative_" if source_name.startswith("negative") else "") + "log_sha256"
        if sha(source) != receipt[key]:
            raise ValueError("Fallback compatibility log differs")
        target = HERE / ("compat-response_siren_pedestrian-fallback1-" + source_name)
        target.write_bytes(source.read_bytes())
        data = target.read_bytes()
        if not data.endswith(b"\n") or data.endswith(b"\n\n") or any(
                line.rstrip(b" \t\r") != line for line in data.split(b"\n")):
            raise ValueError("Fallback log whitespace differs")
        names[source_name] = target.name
    candidate["compatibility"] = {
        "receipt": destination.name, "sha256": sha(destination),
        "log": names["compatibility-analysis.log"],
        "negative_log": names["negative-analysis.log"]}
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print("bound exact source-gated pedestrian camera fallback")


if __name__ == "__main__":
    main()
