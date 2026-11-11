"""Re-run exact CPU offline and compatibility for delivery runner candidates."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
from time import time_ns


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "delivery-construction-manifest.json"
VALIDATOR = ROOT / ".runtime-work/fire-decoder/.lake/build/bin/adapterCheck"


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def main():
    if not VALIDATOR.is_file():
        raise ValueError("Pinned Lean adapter decoder is missing")
    proofs = []
    for entry in json.loads(MANIFEST.read_text())["cases"]:
        case = entry["case_id"]
        suffix = case.rsplit("__", 1)[-1]
        stamp = str(time_ns())
        offline = ROOT / ".runtime-work" / ("c147331-delivery-" + suffix + "-offline-" + stamp)
        compat = ROOT / ".runtime-work" / ("c147331-delivery-" + suffix + "-compat-" + stamp)
        commands = [
            [sys.executable, "runtime.py", "offline", "--manifest", str(MANIFEST),
             "--case", case, "--output", str(offline), "--python", sys.executable],
            [sys.executable, "runtime.py", "compatibility", "--manifest", str(MANIFEST),
             "--case", case, "--output", str(compat), "--library", "runtime/library",
             "--validator", str(VALIDATOR)],
        ]
        for index, command in enumerate(commands):
            with (HERE / ("delivery-" + suffix + ("-offline-command.log" if index == 0
                           else "-compatibility-command.log"))).open("w") as log:
                subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                               check=True)
        copied = {}
        for key, source, name in (
                ("offline_log", offline / "offline.log", "delivery-" + suffix + "-offline.log"),
                ("compatibility_receipt", compat / "compatibility.json", "delivery-" + suffix + "-compatibility.json"),
                ("analysis_log", compat / "compatibility-analysis.log", "delivery-" + suffix + "-compat.log"),
                ("negative_log", compat / "negative-analysis.log", "delivery-" + suffix + "-negative.log")):
            shutil.copyfile(source, HERE / name)
            copied[key] = {"path": name, "sha256": digest(HERE / name)}
        receipt = json.loads((HERE / copied["compatibility_receipt"]["path"]).read_text())
        if (receipt.get("passed") is not True or receipt.get("case_id") != case
                or receipt.get("construction_sha256") != entry["construction_sha256"]
                or receipt.get("negative_removed") != "marked_lane_sources.jsonl"):
            raise ValueError("Delivery candidate compatibility failed: " + suffix)
        proofs.append({"case_id": case, "construction_sha256": entry["construction_sha256"],
                       "offline_command": " ".join(commands[0]),
                       "compatibility_command": " ".join(commands[1]),
                       "exit_code": 0, **copied})
    (HERE / "delivery-case-proofs.json").write_text(json.dumps({
        "format": "worker-lane-delivery-case-proofs", "delivery_ready": False,
        "manifest_sha256": digest(MANIFEST), "cases": proofs}, indent=2) + "\n")


if __name__ == "__main__":
    main()
