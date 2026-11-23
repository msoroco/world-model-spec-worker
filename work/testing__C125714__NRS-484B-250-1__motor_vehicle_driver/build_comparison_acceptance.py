"""Record the five exact comparison CPU contracts without physical claims."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from independent.comparison_audit import SPECS

ROOT = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    script = ROOT / "independent/comparison_audit.py"
    proof = ROOT / "independent/prove_comparison_commands.py"
    log = ROOT / "independent/comparison-commands.log"
    lines = log.read_text().splitlines()
    rows = []
    for comparison_id, (left, right, differences) in SPECS.items():
        message = comparison_id + ": exact CLI positive and reused-attempt negative passed"
        if lines.count(message) != 1:
            raise ValueError("missing exact comparison CPU proof: " + comparison_id)
        rows.append({
            "comparison_id": comparison_id,
            "case_ids": [ROOT.name + "__" + left, ROOT.name + "__" + right],
            "declared_differences": sorted(differences),
            "auditor": "independent/comparison_audit.py",
            "auditor_sha256": sha(script),
            "proof_script": "independent/prove_comparison_commands.py",
            "proof_script_sha256": sha(proof),
            "proof_command": ("SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c125714-comparison-runtime-output-v2 "
                              "PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python "
                              "work/" + ROOT.name + "/independent/prove_comparison_commands.py "
                              "--compat-root .runtime-work/c125714-pair-alignment-compat-v1 "
                              "--output-root .runtime-work/c125714-comparison-cli-v2"),
            "proof_exit_code": 0,
            "proof_log": "independent/comparison-commands.log",
            "proof_log_sha256": sha(log),
            "diagnostic_fixture": True,
            "physical_acceptance_claimed": False,
            "legal_verdict_claimed": False,
        })
    if "separate_roadway_intersection: changed-source negative passed" not in lines:
        raise ValueError("missing changed-source negative proof")
    result = {
        "format": "worker-exact-comparison-acceptance-cpu-draft",
        "assignment_id": ROOT.name,
        "comparisons": rows,
        "original_attempts_reviewed": False,
        "canonical_execution_manifest_bound": False,
    }
    (ROOT / "comparison-acceptance.partial.json").write_text(json.dumps(result, indent=2) + "\n")
    print("five exact comparison CPU contracts recorded; original review remains open")


if __name__ == "__main__":
    main()
