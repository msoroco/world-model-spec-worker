"""Write the six exact draft construction bundles from current reviewed code.

These bundles bind case identity and source text. They remain drafts until the
official signal, legal highway boundary and camera source reviews are supplied.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_construction import ROOT, build


def write_selected():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    prefix = plan["assignment_id"] + "__"
    result = []
    for case in plan["cases"]:
        case_id = case["case_id"]
        if not case_id.startswith(prefix):
            raise ValueError("selected case escaped assignment")
        suffix = case_id[len(prefix):]
        if not suffix or "/" in suffix or ".." in suffix:
            raise ValueError("invalid exact case suffix")
        target = ROOT / "cases" / suffix
        target.mkdir(parents=True, exist_ok=True)
        config, measurement, construction = build(case_id)
        for name, value in (("config.json", config),
                            ("measurement-contract.json", measurement),
                            ("construction.json", construction)):
            path = target / name
            path.write_text(json.dumps(value, indent=2) + "\n")
        path = target / "construction.json"
        result.append({"case_id": case_id,
                       "construction": str(path.relative_to(ROOT)),
                       "construction_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                       "status": "draft"})
    if len(result) != 6 or len({row["case_id"] for row in result}) != 6:
        raise ValueError("exact six selected cases required")
    (ROOT / "selected-constructions.json").write_text(
        json.dumps({"format": "worker-selected-draft-constructions",
                    "assignment_id": plan["assignment_id"], "cases": result}, indent=2) + "\n")
    return result


if __name__ == "__main__":
    print(json.dumps({"selected": len(write_selected()), "status": "draft"}))
