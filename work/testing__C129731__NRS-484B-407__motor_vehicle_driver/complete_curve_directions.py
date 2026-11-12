"""Complete exact CPU paths for the at/beyond curve direction pairs."""

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
PROBES = (("at_500ft", "at"), ("beyond_500ft", "beyond"))


def run(command, log, environment=None):
    with log.open("w") as output:
        subprocess.run(command, cwd=ROOT, env=environment, stdout=output,
                       stderr=subprocess.STDOUT, check=True)


def prove(probe, short, direction):
    suffix = "a" if direction == "approach_a" else "b"
    name = "canonical-curve-" + short + "-" + suffix
    case_id = HERE.name + "__curve__" + probe + "__occluded_" + direction
    args = ["--probe", probe, "--direction", direction]
    run([PYTHON, str(HERE / "build_curve_direction_proof.py")] + args,
        HERE / (name + "-branch-build.log"))
    run([PYTHON, str(HERE / "extend_curve_case_plan.py")] + args,
        HERE / (name + "-plan.log"))
    manifest = str(HERE / ("diagnostic-" + name + "-manifest.json"))
    base = str(ROOT / ".runtime-work" / ("c129731-" + name))
    common = [PYTHON, RUNTIME]
    decode = ["--library", "runtime/library", "--validator", VALIDATOR]
    run(common + ["offline", "--manifest", manifest, "--case", case_id,
                  "--output", base + "-offline-v1"], HERE / (name + "-branch-offline.log"))
    print("PASS " + name + " offline", flush=True)
    environment = dict(os.environ)
    environment["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(ROOT / ".runtime-work/pipeline-output")
    run(common + ["compatibility", "--manifest", manifest, "--case", case_id,
                  "--output", base + "-compat-v1"] + decode,
        HERE / (name + "-branch-compatibility-command.log"), environment)
    print("PASS " + name + " compatibility", flush=True)
    run(common + ["process-saved", "--manifest", manifest, "--case", case_id,
                  "--attempt", base + "-compat-v1", "--output", base + "-saved-v1"] + decode,
        ROOT / ".runtime-work" / ("c129731-" + name + "-saved-command-v1.log"), environment)
    run([PYTHON, str(HERE / "record_curve_direction_proof.py")] + args,
        HERE / (name + "-proof.log"))
    print("PASS " + name + " saved", flush=True)


def main():
    for probe, short in PROBES:
        for direction in ("approach_a", "approach_b"):
            prove(probe, short, direction)
        run([PYTHON, str(HERE / "prove_curve_direction_comparison.py"),
             "--probe", probe], HERE / ("canonical-curve-" + short + "-comparison-proof.log"))
        print("PASS curve " + short + " comparison", flush=True)


if __name__ == "__main__":
    main()
