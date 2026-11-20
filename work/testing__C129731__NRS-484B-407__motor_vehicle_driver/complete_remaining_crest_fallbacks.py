"""Run exact CPU proof paths for the remaining distinct crest case fallbacks."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PYTHON = str(ROOT / ".venv-cpu/bin/python")
RUNTIME = str(ROOT / "runtime.py")
VALIDATOR = str(ROOT / ".runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck")
NAMES = (
    "canonical-short-approach-b", "canonical-short-near-b",
    "canonical-short-approach-a", "canonical-short-near-a",
    "canonical-beyond-approach-b", "canonical-beyond-near-b",
    "canonical-beyond-approach-a", "canonical-beyond-near-a",
)


def run(command, log, environment=None):
    with log.open("w") as output:
        subprocess.run(command, cwd=ROOT, env=environment, stdout=output,
                       stderr=subprocess.STDOUT, check=True)


def candidate(name, case_id, phase, number):
    ident = "fallback" + str(number)
    manifest = str(HERE / ("diagnostic-" + name + "-fallback-manifest.json"))
    base = ROOT / ".runtime-work" / ("c129731-" + name + "-" + ident)
    common = [PYTHON, RUNTIME, phase, "--manifest", manifest, "--case", case_id]
    environment = dict(os.environ)
    if phase == "offline":
        command = common + ["--candidate", ident, "--output", str(base) + "-offline-v1"]
        log = HERE / (name + "-" + ident + "-offline.log")
    elif phase == "compatibility":
        command = common + ["--candidate", ident, "--output", str(base) + "-compat-v1",
                            "--library", "runtime/library", "--validator", VALIDATOR]
        log = HERE / (name + "-" + ident + "-compatibility-command.log")
        environment["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(ROOT / ".runtime-work/pipeline-output")
    elif phase == "process-saved":
        command = common + ["--attempt", str(base) + "-compat-v1",
                            "--output", str(base) + "-saved-v1",
                            "--library", "runtime/library", "--validator", VALIDATOR]
        log = ROOT / ".runtime-work" / ("c129731-" + name + "-" + ident + "-saved-command-v1.log")
        environment["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(ROOT / ".runtime-work/pipeline-output")
    else:
        raise ValueError(phase)
    run(command, log, environment)


def main():
    for name in NAMES:
        manifest = json.loads((HERE / ("diagnostic-" + name + "-manifest.json")).read_text())
        case_id = manifest["cases"][0]["case_id"]
        print("START " + name, flush=True)
        run([PYTHON, str(HERE / "build_promoted_crest_fallbacks.py"), "--name", name],
            HERE / (name + "-fallback-build.log"))
        for phase in ("offline", "compatibility", "process-saved"):
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = [pool.submit(candidate, name, case_id, phase, n) for n in (1, 2, 3)]
                for future in futures:
                    future.result()
            print("PASS " + name + " " + phase, flush=True)
        run([PYTHON, str(HERE / "record_promoted_crest_fallbacks.py"), "--name", name],
            HERE / (name + "-fallback-proof.log"))
        run([PYTHON, str(HERE / "build_promoted_physical_proof.py"), "--name", name],
            HERE / (name + "-physical-proof.log"))
        print("PASS " + name + " physical", flush=True)


if __name__ == "__main__":
    main()
