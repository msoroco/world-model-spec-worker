"""Execute the linked queue's exact local comparison commands on saved fixtures."""

from hashlib import sha256
import json
from pathlib import Path
import shlex
import subprocess
import sys
from tempfile import TemporaryDirectory

from prove_comparison_dispatch import sources

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def prove():
    queue = json.loads((HERE / "gpu-queue.json").read_text())
    by_case = sources()
    rows = []
    with TemporaryDirectory() as temporary:
        for comparison in queue["comparisons"]:
            name = comparison["comparison_id"]
            command = comparison["audit_command"]
            for index, case in enumerate(comparison["case_ids"], 1):
                command = command.replace(f'"$ATTEMPT_{index}"',
                                          shlex.quote(str(by_case[case][0])))
            report = Path(temporary) / (name + ".json")
            command = command.replace('"$COMPARISON_REPORT"', shlex.quote(str(report)))
            tokens = shlex.split(command)
            if tokens[0] != ".venv-cpu/bin/python":
                raise ValueError("Queue comparison uses an unexpected interpreter")
            completed = subprocess.run(tokens, cwd=ROOT, text=True,
                                       capture_output=True, check=False)
            if completed.returncode != 0 or not report.is_file():
                raise ValueError(name + ": " + completed.stderr)
            result = json.loads(report.read_text())
            if result["comparison_id"] != name or result["case_ids"] != comparison["case_ids"]:
                raise ValueError("Queue returned another comparison: " + name)
            rows.append({"comparison_id": name, "case_ids": comparison["case_ids"],
                         "exit_code": 0, "source_report_sha256": digest(report)})
    return {"format": "worker-linked-queued-comparison-proof",
            "assignment_id": queue["assignment_id"],
            "queue_sha256": digest(HERE / "gpu-queue.json"),
            "comparisons": rows, "physical_or_legal_acceptance_claimed": False}


if __name__ == "__main__":
    proof = prove()
    path = HERE / "queued-comparison-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"comparisons": len(proof["comparisons"]), "sha256": digest(path)}))
