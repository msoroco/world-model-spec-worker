"""Run exact offline and positive/negative compatibility for nine fallbacks."""

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
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.rsplit("__", 1)[-1]
        for candidate in entry["candidates"]:
            ident = candidate["id"]
            stem = "delivery-" + suffix + "-" + ident
            stamp = str(time_ns())
            offline = ROOT / ".runtime-work" / ("c147331-" + stem + "-offline-" + stamp)
            compat = ROOT / ".runtime-work" / ("c147331-" + stem + "-compat-" + stamp)
            offline_command = [sys.executable, "runtime.py", "offline", "--manifest",
                               str(MANIFEST), "--case", case, "--candidate", ident,
                               "--output", str(offline), "--python", sys.executable]
            compat_command = [sys.executable, "runtime.py", "compatibility", "--manifest",
                              str(MANIFEST), "--case", case, "--candidate", ident,
                              "--output", str(compat), "--library", "runtime/library",
                              "--validator", str(VALIDATOR)]
            for command, path in ((offline_command, HERE / (stem + "-offline-command.log")),
                                  (compat_command, HERE / (stem + "-compatibility-command.log"))):
                with path.open("w") as log:
                    subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                   check=True)
            names = {"offline": offline / "offline.log",
                     "compatibility": compat / "compatibility.json",
                     "compat": compat / "compatibility-analysis.log",
                     "negative": compat / "negative-analysis.log"}
            for key, source in names.items():
                shutil.copyfile(source, HERE / (stem + "-" + key + (".json" if key == "compatibility" else ".log")))
            receipt_name = stem + "-compatibility.json"
            receipt = json.loads((HERE / receipt_name).read_text())
            if (receipt.get("passed") is not True or receipt.get("case_id") != case
                    or receipt.get("candidate_id") != ident
                    or receipt.get("construction_sha256") != candidate["construction_sha256"]
                    or receipt.get("negative_removed") != "marked_lane_sources.jsonl"):
                raise ValueError("Fallback compatibility failed: " + stem)
            candidate["offline"] = {"command": " ".join(offline_command), "exit_code": 0,
                                    "log": stem + "-offline.log",
                                    "log_sha256": digest(HERE / (stem + "-offline.log")),
                                    "construction_sha256": candidate["construction_sha256"]}
            candidate["compatibility"] = {"receipt": receipt_name,
                                          "sha256": digest(HERE / receipt_name),
                                          "log": stem + "-compat.log",
                                          "negative_log": stem + "-negative.log"}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
