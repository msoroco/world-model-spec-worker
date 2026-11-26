"""Run current exact-case saved CPU compatibility without touching work scratch."""

import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work/c380107-owner"
MANIFEST = HERE / "diagnostic-execution-manifest.json"
VALIDATOR = REPO / ".runtime-work/c227824-owner/decoder/.lake/build/bin/adapterCheck"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def one(entry):
    case_id = entry["case_id"]
    suffix = case_id.rsplit("__", 1)[-1]
    folder = HERE / "cases" / suffix
    output = SCRATCH / ("compat-" + uuid.uuid4().hex)
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH), TMPDIR=str(SCRATCH),
               MPLCONFIGDIR=str(SCRATCH / "mpl"), PYTHONDONTWRITEBYTECODE="1",
               OMP_NUM_THREADS="1")
    command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"), "compatibility",
               "--manifest", str(MANIFEST), "--case", case_id, "--output", str(output),
               "--library", str(REPO / "runtime/library"), "--validator", str(VALIDATOR)]
    process = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
    log = folder / "cpu-compatibility.log"
    log.write_text((process.stdout + process.stderr).rstrip() + "\n", encoding="utf-8")
    if process.returncode:
        return {"case_id": case_id, "exit_code": process.returncode,
                "error": log.read_text()[-1500:]}
    for name in ("compatibility.json", "compatibility-analysis.log", "negative-analysis.log"):
        source = output / name
        target = folder / ("cpu-analysis.log" if name == "compatibility-analysis.log" else name)
        content = source.read_text(encoding="utf-8")
        if content.endswith("\n\n") or any(line.rstrip(" \t") != line for line in content.splitlines()):
            raise ValueError("sealed compatibility source has checkpoint whitespace: " + name)
        target.write_text(content, encoding="utf-8")
        if name == "compatibility-analysis.log" and digest(source) != digest(target):
            raise ValueError("compatibility analysis log normalization changed sealed hash")
        if name == "negative-analysis.log" and digest(source) != digest(target):
            raise ValueError("negative analysis log normalization changed sealed hash")
    receipt = json.loads((folder / "compatibility.json").read_text())
    if receipt.get("passed") is not True:
        raise ValueError("compatibility receipt did not pass")
    return {"case_id": case_id, "exit_code": 0,
            "receipt": str((folder / "compatibility.json").relative_to(HERE)),
            "receipt_sha256": digest(folder / "compatibility.json"),
            "log": str(log.relative_to(HERE)), "log_sha256": digest(log),
            "negative_log": str((folder / "negative-analysis.log").relative_to(HERE)),
            "negative_log_sha256": digest(folder / "negative-analysis.log")}


def main():
    entries = json.loads(MANIFEST.read_text())["cases"]
    if len(entries) != 18:
        raise ValueError("exact eighteen selected cases required")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(one, entries))
    (HERE / "cpu-compatibility-summary.json").write_text(
        json.dumps({"format": "worker-compatibility-proof-summary", "cases": results},
                   indent=2, sort_keys=True) + "\n")
    for result in results:
        print(result["case_id"].rsplit("__", 1)[-1], result["exit_code"])
    if any(result["exit_code"] for result in results):
        raise ValueError("selected compatibility failed")


if __name__ == "__main__":
    main()
