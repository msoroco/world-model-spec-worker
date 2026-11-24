"""Pin source-bound independent comparison commands for local production use."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

OWN = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    plan = json.loads((OWN / "case-plan.json").read_text())
    script = OWN / "comparison_source_guard.py"
    entries = []
    for comparison in plan["comparisons"]:
        left, right = comparison["case_ids"]
        ident = comparison["comparison_id"]
        entries.append({
            "comparison_id": ident, "case_ids": [left, right],
            "deliberate_differences": comparison["deliberate_differences"],
            "fixed_conditions": comparison["fixed_conditions"],
            "script": "comparison_source_guard.py", "script_sha256": sha(script),
            "command": (f".venv-cpu/bin/python {script.relative_to(OWN.parents[1])} "
                        f"--plan {(OWN / 'case-plan.json').relative_to(OWN.parents[1])} "
                        f"--comparison {ident} --left /external/archive/{left}/result.json "
                        f"--right /external/archive/{right}/result.json "
                        f"--left-delivery-audit /external/archive/{left}/delivery-audit.json "
                        f"--right-delivery-audit /external/archive/{right}/delivery-audit.json"),
            "required_delivery_checks": ["native_source", "all_participants", "time_join",
                                         "full_video_decode", "actual_pixels", "physical_completion"],
            "source_policy": "Recompute original mean speed and join condition times; both independent delivery audits must bind exact saved Native result hashes; reject diagnostic fixtures and stale sources.",
            "legal_prudence": "unresolved"
        })
    output = {"format": "c10307-source-bound-comparison-contracts-v1", "assignment_id": plan["assignment_id"],
              "comparisons": entries}
    (OWN / "comparison-delivery-contracts.json").write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
