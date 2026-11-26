"""Run exact construction and source-bound positive/negative CPU proofs."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
SCRATCH = REPO / ".runtime-work" / "c150088-nov26" / "proofs-v5"
VALIDATOR = REPO / ".runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def saved_log(source, destination):
    text = source.read_text(encoding="utf-8").rstrip() + "\n" if source.stat().st_size else ""
    destination.write_text(text, encoding="utf-8")
    return sha(destination)


def run():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        for candidate in ("primary", "fallback1"):
            selected = entry if candidate == "primary" else entry["candidates"][0]
            output = SCRATCH / (suffix + "-" + candidate)
            output.mkdir(exist_ok=True)
            offline = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"), "offline",
                       "--manifest", str(MANIFEST), "--case", entry["case_id"],
                       "--candidate", candidate, "--output", str(output / "offline"),
                       "--python", str(REPO / ".venv-cpu/bin/python")]
            completed = subprocess.run(offline, cwd=REPO, capture_output=True, text=True)
            log = ROOT / ("cpu-offline-" + suffix + "-" + candidate + ".log")
            log.write_text((completed.stdout + completed.stderr).rstrip() + "\n", encoding="utf-8")
            if completed.returncode:
                raise RuntimeError("offline " + suffix + " " + candidate + ": " + log.read_text()[-1000:])
            selected["offline"] = {"command": " ".join(offline), "exit_code": 0,
                                   "log": log.name, "log_sha256": sha(log),
                                   "construction_sha256": selected["construction_sha256"]}
            compatibility = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"), "compatibility",
                             "--manifest", str(MANIFEST), "--case", entry["case_id"],
                             "--candidate", candidate, "--output", str(output / "compat"),
                             "--library", str(REPO / "runtime/library"),
                             "--validator", str(VALIDATOR)]
            completed = subprocess.run(compatibility, cwd=REPO, capture_output=True, text=True)
            if completed.returncode:
                failure = ROOT / ("cpu-compatibility-" + suffix + "-" + candidate + "-failure.log")
                failure.write_text((completed.stdout + completed.stderr).rstrip() + "\n", encoding="utf-8")
                raise RuntimeError("compatibility " + suffix + " " + candidate + ": " + failure.read_text()[-1000:])
            receipt = ROOT / ("cpu-compatibility-" + suffix + "-" + candidate + ".json")
            receipt.write_bytes((output / "compat/compatibility.json").read_bytes())
            analysis = ROOT / ("cpu-compatibility-analysis-" + suffix + "-" + candidate + ".log")
            negative = ROOT / ("cpu-compatibility-negative-" + suffix + "-" + candidate + ".log")
            saved_log(output / "compat/compatibility-analysis.log", analysis)
            saved_log(output / "compat/negative-analysis.log", negative)
            proof = json.loads(receipt.read_text(encoding="utf-8"))
            if proof["log_sha256"] != sha(analysis) or proof["negative_log_sha256"] != sha(negative):
                raise RuntimeError("retained compatibility logs differ from CPU receipt")
            selected["compatibility"] = {"command": " ".join(compatibility),
                                          "receipt": receipt.name, "sha256": sha(receipt),
                                          "log": analysis.name,
                                          "negative_log": negative.name}
            selected["negative"] = {"log": negative.name}
            MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            print(suffix, candidate, "passed", flush=True)


if __name__ == "__main__":
    run()
