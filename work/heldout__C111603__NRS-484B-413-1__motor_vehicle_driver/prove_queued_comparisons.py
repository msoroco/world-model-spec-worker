"""Exercise every exact saved-comparison command in the assignment queue."""

import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    queue = json.loads((HERE / "gpu-queue.json").read_text())
    planned = {row["comparison_id"] for row in
               json.loads((HERE / "case-plan.json").read_text())["comparisons"]}
    rows = queue["comparisons"]
    if len(rows) != len(planned) or {row["comparison_id"] for row in rows} != planned:
        raise ValueError("Queued comparison coverage differs from selected plan")
    for row in rows:
        name = row["comparison_id"]
        expected = (f'.venv-cpu/bin/python work/{HERE.name}/saved_comparison_audit.py '
                    f'--comparison {name} --output "$COMPARISON_AUDIT_OUTPUT"')
        if row.get("audit_command") != expected:
            raise ValueError("Queued comparison command differs: " + name)
        output = ROOT / ".runtime-work" / (name + "-audit.json")
        run = subprocess.run([sys.executable, str(HERE / "saved_comparison_audit.py"),
                              "--comparison", name, "--output", str(output)],
                             cwd=ROOT, capture_output=True, text=True)
        print(name, run.returncode, run.stdout.strip(), run.stderr.strip(), flush=True)
        if run.returncode:
            raise ValueError("Queued comparison audit failed: " + name)
        proof = json.loads(output.read_text())
        if set(proof["comparisons"]) != {name} or proof["physical_acceptance_claimed"]:
            raise ValueError("Queued comparison selected wrong result: " + name)


if __name__ == "__main__":
    main()
