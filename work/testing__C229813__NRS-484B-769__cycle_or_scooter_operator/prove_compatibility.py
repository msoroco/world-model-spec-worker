"""Run exact CPU compatibility on all nine source-gated signal cases."""

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
SCRATCH = ROOT / ".runtime-work" / "c229813-owner" / "compat-all-v2"
MANIFEST = PACKAGE / "execution-manifest.draft.json"
VALIDATOR = ROOT / ".runtime-work" / "c150911-decoder" / ".lake" / "build" / "bin" / "adapterCheck"


def main():
    manifest = json.loads(MANIFEST.read_text())
    results = []
    env = dict(os.environ)
    env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(ROOT / ".runtime-work" / "c229813-owner")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for case in manifest["cases"]:
        case_id = case["case_id"]
        suffix = case_id.removeprefix(manifest["assignment_id"] + "__")
        for candidate_id in ["primary"] + [c["id"] for c in case["candidates"]]:
            target = SCRATCH / (suffix + "-" + candidate_id)
            command = [str(ROOT / ".venv-cpu" / "bin" / "python"), str(ROOT / "runtime.py"),
                       "compatibility", "--manifest", str(MANIFEST), "--case", case_id,
                       "--candidate", candidate_id, "--output", str(target),
                       "--library", str(ROOT / "runtime" / "library"),
                       "--validator", str(VALIDATOR)]
            run = subprocess.run(command, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT)
            log = PACKAGE / f"proof-compatibility-{suffix}-{candidate_id}.log"
            log.write_text(run.stdout.rstrip() + "\n")
            receipt = target / "compatibility.json"
            passed = bool(run.returncode == 0 and receipt.is_file()
                          and json.loads(receipt.read_text()).get("passed"))
            results.append({"case_id": case_id, "candidate_id": candidate_id,
                            "passed": passed, "returncode": run.returncode,
                            "command": " ".join(command), "log": log.name,
                            "receipt": str(receipt.relative_to(ROOT))})
            print(suffix, candidate_id, "PASS" if passed else "FAIL", flush=True)
            if not passed:
                print(log.read_text()[-4000:], flush=True)
    (PACKAGE / "cpu-compatibility-proofs.json").write_text(
        json.dumps({"assignment_id": manifest["assignment_id"], "results": results}, indent=2) + "\n")
    return 0 if all(x["passed"] for x in results) else 1


if __name__ == "__main__":
    sys.exit(main())
