"""Run recorded-only diagnostic finalization for each exact entrant case."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PYTHON = str(REPO / ".venv-cpu/bin/python")
MANIFEST = ROOT / "execution-manifest.json"
SCRATCH = REPO / ".runtime-work/c135087-saved-v2"
VALIDATOR = REPO / ".runtime-work/c150099-decoder-v2/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(args, log, env):
    result = subprocess.run(args, cwd=REPO, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    log.write_text(result.stdout.rstrip() + "\n" if result.stdout.strip() else "")
    if result.returncode:
        raise ValueError("proof failed: " + " ".join(args) + "\n" + result.stdout[-1500:])


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    tmp = SCRATCH / "tmp"
    tmp.mkdir(exist_ok=True)
    output_root = SCRATCH / "output"
    output_root.mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(tmp),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(output_root))
    data = json.loads(MANIFEST.read_text())
    for entry in data["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(ROOT.name + "__")
        fixture = SCRATCH / ("fixture-" + suffix)
        attempt = SCRATCH / ("attempt-" + suffix)
        saved = SCRATCH / ("saved-" + suffix)
        run([PYTHON, "runtime.py", "fixture", "--recipe",
             str(ROOT / ("diagnostic-" + suffix + "-recipe.json")),
             "--output", str(fixture)], ROOT / ("cpu-fixture-" + suffix + ".log"), env)
        run([PYTHON, "runtime.py", "materialize", "--manifest", str(MANIFEST),
             "--case", case, "--output", str(attempt)],
            ROOT / ("cpu-materialize-" + suffix + ".log"), env)
        for source in fixture.iterdir():
            target = attempt / source.name
            if target.exists():
                raise ValueError("fixture shadows construction")
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
        command = [PYTHON, "runtime.py", "process-saved", "--manifest", str(MANIFEST),
                   "--case", case, "--attempt", str(attempt), "--output", str(saved),
                   "--library", str(REPO / "runtime/library"),
                   "--validator", str(VALIDATOR)]
        log = ROOT / ("cpu-saved-" + suffix + ".log")
        run(command, log, env)
        receipt = ROOT / ("cpu-saved-" + suffix + ".json")
        shutil.copy2(saved / "v0001/processing.json", receipt)
        entry["saved_diagnostic"] = {"receipt": receipt.name, "sha256": sha(receipt),
                                      "source": str(fixture.relative_to(REPO)),
                                      "physical_acceptance_claimed": False}
        entry["post_capture"] = {"recorded_only": True, "command": " ".join(command),
                                 "feedback_command": "inspect " + str(saved / "v0001/feedback.json"),
                                 "test_exit_code": 0, "test_log": log.name,
                                 "test_log_sha256": sha(log)}
        print(suffix + " recorded-only processing passed", flush=True)
    MANIFEST.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
