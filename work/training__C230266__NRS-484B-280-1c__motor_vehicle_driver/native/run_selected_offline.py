"""Run exact current-runtime offline tests for all selected constructions."""

import hashlib
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "selected-preflight-manifest.json"
SCRATCH = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) / "selected-offline"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = SCRATCH / (path.name + ".staging")
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_text(content.rstrip() + "\n")
    os.replace(staged, path)


def main():
    manifest = json.loads(MANIFEST.read_text())
    checks = []
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.rsplit("__", 1)[-1]
        output = SCRATCH / suffix
        if output.exists():
            raise ValueError("Use fresh exact offline output: " + str(output))
        command = [str(REPO / ".venv-cpu/bin/python"), "-B", str(REPO / "runtime.py"),
                   "offline", "--manifest", str(MANIFEST), "--case", case,
                   "--output", str(output)]
        result = subprocess.run(command, cwd=REPO, capture_output=True,
                                text=True, env=os.environ.copy(), timeout=120)
        native_log = (output / "offline.log").read_text() if (output / "offline.log").is_file() else ""
        log_path = ROOT / "selected-offline" / (suffix + ".log")
        write(log_path, result.stdout + result.stderr + native_log)
        row = {"case_id": case, "construction_sha256": entry["construction_sha256"],
               "exit_code": result.returncode, "command": " ".join(command),
               "log": str(log_path.relative_to(ROOT)), "log_sha256": sha(log_path)}
        checks.append(row)
        print(json.dumps({"case": suffix, "exit_code": result.returncode}), flush=True)
        if result.returncode:
            break
    path = ROOT / "selected-offline" / "index.json"
    write(path, json.dumps({"format": "worker-nrs280-selected-offline-index-v1",
                            "checks": checks, "pass_count": sum(row["exit_code"] == 0 for row in checks),
                            "scope": "CPU implementation contract only"}, indent=2))
    if len(checks) != len(manifest["cases"]) or any(row["exit_code"] for row in checks):
        raise ValueError("Selected exact offline construction failed")


if __name__ == "__main__":
    main()
