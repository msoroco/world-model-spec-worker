"""Refresh exact CPU receipts after a source-bound delivery audit revision."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work"
MANIFEST = ROOT / "execution-manifest.json"
RESULT = ROOT / "result.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, log):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(SCRATCH / "c147332-12a-custody-proof-runtime")
    completed = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
    output = completed.stdout + completed.stderr
    log.write_text("\n".join(line.rstrip() for line in output.splitlines()).rstrip() + "\n")
    if completed.returncode:
        raise RuntimeError(f"CPU proof failed: {log}; exit {completed.returncode}")


def main():
    manifest = json.loads(MANIFEST.read_text())
    result = json.loads(RESULT.read_text())
    tests = {item["log"]: item for item in result["tests"]}
    python = str(REPO / ".venv-cpu/bin/python")
    for entry in manifest["cases"]:
        kind = entry["case_id"].rsplit("__", 1)[-1]
        entry.setdefault("fixture_recipe", str((ROOT / "cases" / kind / "fixture-recipe.json").relative_to(REPO)))
        MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        for candidate in ("primary", "fallback1"):
            row = entry if candidate == "primary" else entry["candidates"][0]
            construction_hash = sha(ROOT / row["construction"])
            if construction_hash != row["construction_sha256"]:
                raise ValueError("construction hash mismatch")
            offline_output = SCRATCH / f"c147332-12a-camera-offline-{kind}-{candidate}"
            offline_log = ROOT / "cases" / kind / ("cpu-offline.log" if candidate == "primary" else "cpu-offline-fallback1.log")
            offline_command = [python, str(REPO / "runtime.py"), "offline", "--manifest", str(MANIFEST),
                               "--case", entry["case_id"], "--candidate", candidate,
                               "--output", str(offline_output)]
            run(offline_command, offline_log)
            row.setdefault("offline", {}).update(command=" ".join(offline_command), exit_code=0,
                                  construction_sha256=construction_hash,
                                  log=str(offline_log.relative_to(ROOT)), log_sha256=sha(offline_log))
            tests[str(offline_log.relative_to(ROOT))] = {
                "command": " ".join(offline_command), "exit_code": 0,
                "log": str(offline_log.relative_to(ROOT)), "sha256": sha(offline_log)}

            compat_output = SCRATCH / "c147332-12a-camera-compat" / kind / candidate
            compat_log = ROOT / f"cpu-compat-{kind}-{candidate}.log"
            compat_command = [python, str(REPO / "runtime.py"), "compatibility", "--manifest", str(MANIFEST),
                              "--case", entry["case_id"], "--candidate", candidate,
                              "--output", str(compat_output), "--library", str(REPO / "runtime/library"),
                              "--validator", str(SCRATCH / "c109755-decoder-v2/.lake/build/bin/adapterCheck")]
            run(compat_command, compat_log)
            stem = f"compat-{kind}-{candidate}"
            for source, target in (("compatibility.json", stem + "-receipt.json"),
                                   ("compatibility-analysis.log", stem + "-analysis.log"),
                                   ("negative-analysis.log", stem + "-negative.log")):
                shutil.copyfile(compat_output / source, ROOT / target)
            receipt_name = stem + "-receipt.json"
            receipt = json.loads((ROOT / receipt_name).read_text())
            if (receipt["construction_sha256"] != construction_hash or receipt["passed"] is not True or
                    receipt["log_sha256"] != sha(ROOT / (stem + "-analysis.log")) or
                    receipt["negative_log_sha256"] != sha(ROOT / (stem + "-negative.log"))):
                raise ValueError("compatibility source or log mismatch")
            proof = {"receipt": receipt_name, "sha256": sha(ROOT / receipt_name),
                     "log": stem + "-analysis.log"}
            if candidate == "primary":
                entry["compatibility"] = proof
                entry["negative"] = {"log": stem + "-negative.log",
                                     "sha256": sha(ROOT / (stem + "-negative.log"))}
            else:
                row["compatibility"] = {**proof, "negative_log": stem + "-negative.log"}
            tests[compat_log.name] = {"command": " ".join(compat_command), "exit_code": 0,
                                      "log": compat_log.name, "sha256": sha(compat_log)}
            print(kind, candidate, "offline and compatibility passed", flush=True)
    result["tests"] = list(tests.values())
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    RESULT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
