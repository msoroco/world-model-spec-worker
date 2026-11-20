"""Run and bind exact positive/negative and recorded-only fallback CPU proofs.

The command is resumable after a completed stage. It never marks the package ready.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PYTHON = REPO / ".venv-cpu/bin/python"
VALID = {"at": ("curve", "at_500ft"),
         "beyond": ("curve", "beyond_500ft"),
         "crest-short": ("crest", "short_of_500ft"),
         "crest-at": ("crest", "at_500ft"),
         "crest-beyond": ("crest", "beyond_500ft")}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, log):
    env = os.environ.copy()
    env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(REPO / ".runtime-work/pipeline-output")
    with log.open("w") as output:
        status = subprocess.run(command, cwd=REPO, env=env,
                                stdout=output, stderr=subprocess.STDOUT).returncode
    if status:
        raise RuntimeError("CPU proof failed (exit %d): %s; log %s" %
                           (status, " ".join(map(str, command)), log))


def prove(suffix, ident):
    feature, probe = VALID[suffix]
    case = HERE.name + "__" + feature + "__" + probe
    manifest = HERE / ("diagnostic-" + suffix + "-fallback-manifest.json")
    entry = next(row for row in json.loads(manifest.read_text())["cases"][0]["candidates"]
                 if row["id"] == ident)
    base = REPO / ".runtime-work" / ("c129731-" + suffix + "-" + ident)
    compat, saved = Path(str(base) + "-compat-v1"), Path(str(base) + "-saved-v1")
    compat_log = Path(str(base) + "-compat-v1-command.log")
    saved_log = Path(str(base) + "-saved-v1-command.log")
    common = ["--manifest", str(manifest.relative_to(REPO)), "--case", case]
    decoder = ["--library", "runtime/library", "--validator",
               ".runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck"]
    compat_command = [str(PYTHON), "runtime.py", "compatibility", *common,
                      "--candidate", ident, "--output", str(compat.relative_to(REPO)),
                      *decoder]
    saved_command = [str(PYTHON), "runtime.py", "process-saved", *common,
                     "--attempt", str(compat.relative_to(REPO)),
                     "--output", str(saved.relative_to(REPO)), *decoder]
    if not (compat / "compatibility.json").is_file():
        if compat.exists():
            raise RuntimeError("Incomplete compatibility output; inspect and choose a fresh output: " + str(compat))
        run(compat_command, compat_log)
    receipt = json.loads((compat / "compatibility.json").read_text())
    if not (receipt.get("passed") is True and receipt.get("candidate_id") == ident
            and receipt.get("case_id") == case
            and receipt.get("construction_sha256") == entry["construction_sha256"]):
        raise ValueError("Compatibility receipt does not bind the current exact fallback")
    if not saved_log.is_file():
        if saved.exists():
            raise RuntimeError("Incomplete saved output; inspect and choose a fresh output: " + str(saved))
        run(saved_command, saved_log)
    processing = json.loads(saved_log.read_text())
    if not (processing.get("passed") is True and processing.get("recorded_only") is True
            and processing.get("originals_preserved") is True
            and processing.get("native_revision", {}).get("construction_sha256") == entry["construction_sha256"]):
        raise ValueError("Saved receipt does not bind original sources and the current fallback")
    files = [(compat / "compatibility.json", suffix + "-" + ident + "-compatibility.json"),
             (compat / "negative-analysis.log", suffix + "-" + ident + "-negative-analysis.log"),
             (saved_log, suffix + "-" + ident + "-processing.json")]
    for source, name in files:
        shutil.copyfile(source, HERE / name)
    result_path = HERE / "result.json"
    result = json.loads(result_path.read_text())
    claims = [
        (" ".join(map(str, compat_command)), files[0][1]),
        (" ".join(map(str, saved_command)), files[2][1])]
    for command, name in claims:
        if not any(row["command"] == command for row in result["tests"]):
            result["tests"].append({"command": command, "exit_code": 0,
                "log": name, "sha256": sha(HERE / name)})
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    return {"case": case, "candidate": ident, "construction_sha256": entry["construction_sha256"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("targets", nargs="+", help="suffix:candidate, e.g. crest-short:fallback1")
    args = parser.parse_args()
    for target in args.targets:
        suffix, ident = target.split(":", 1)
        if suffix not in VALID or ident not in ("fallback1", "fallback2", "fallback3"):
            raise ValueError("Unknown exact fallback: " + target)
        print(json.dumps(prove(suffix, ident)), flush=True)
