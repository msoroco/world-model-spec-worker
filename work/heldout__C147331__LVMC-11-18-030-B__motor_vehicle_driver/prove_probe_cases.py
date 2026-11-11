"""Re-run exact CPU offline and case-source compatibility for lane probes."""

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
MANIFEST = HERE / "construction-probe-manifest.json"
VALIDATOR = ROOT / ".runtime-work/fire-decoder/.lake/build/bin/adapterCheck"


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def run(command, log):
    with Path(log).open("w") as stream:
        subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                       check=True)


def main():
    if not VALIDATOR.is_file():
        raise ValueError("Pinned Lean adapter decoder is missing: " + str(VALIDATOR))
    entries = json.loads(MANIFEST.read_text())["cases"]
    proofs = []
    for entry in entries:
        case = entry["case_id"]
        suffix = case.rsplit("__", 1)[-1]
        stamp = str(time_ns())
        offline_dir = ROOT / ".runtime-work" / ("c147331-" + suffix + "-offline-" + stamp)
        compat_dir = ROOT / ".runtime-work" / ("c147331-" + suffix + "-compat-" + stamp)
        offline_command = [sys.executable, "runtime.py", "offline", "--manifest",
                           str(MANIFEST), "--case", case, "--output", str(offline_dir),
                           "--python", sys.executable]
        compat_command = [sys.executable, "runtime.py", "compatibility", "--manifest",
                          str(MANIFEST), "--case", case, "--output", str(compat_dir),
                          "--library", "runtime/library", "--validator", str(VALIDATOR)]
        run(offline_command, HERE / (suffix + "-offline-command.log"))
        run(compat_command, HERE / (suffix + "-compatibility-command.log"))
        files = {"offline_log": (offline_dir / "offline.log", suffix + "-offline.log"),
                 "compatibility_receipt": (compat_dir / "compatibility.json",
                                           suffix + "-compatibility.json"),
                 "analysis_log": (compat_dir / "compatibility-analysis.log",
                                  suffix + "-compat.log"),
                 "negative_log": (compat_dir / "negative-analysis.log",
                                  suffix + "-negative.log")}
        copied = {}
        for key, (source, name) in files.items():
            shutil.copyfile(source, HERE / name)
            copied[key] = {"path": name, "sha256": digest(HERE / name)}
        receipt = json.loads((HERE / copied["compatibility_receipt"]["path"]).read_text())
        if (receipt.get("passed") is not True or receipt.get("case_id") != case
                or receipt.get("construction_sha256") != entry["construction_sha256"]
                or receipt.get("negative_removed") != "marked_lane_sources.jsonl"):
            raise ValueError("Exact case compatibility receipt failed: " + suffix)
        proofs.append({"case_id": case, "construction_sha256": entry["construction_sha256"],
                       "offline_command": " ".join(offline_command),
                       "compatibility_command": " ".join(compat_command),
                       "exit_code": 0, **copied})
    (HERE / "probe-case-proofs.json").write_text(json.dumps({
        "format": "worker-lane-probe-case-proofs", "delivery_ready": False,
        "manifest_sha256": digest(MANIFEST), "cases": proofs}, indent=2) + "\n")


if __name__ == "__main__":
    main()
