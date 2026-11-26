"""Write the six exact draft construction bundles from current reviewed code.

These bundles bind case identity and source text. They remain drafts until the
official signal, legal highway boundary and camera source reviews are supplied.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

from build_construction import ROOT, build
from selected_source_gate import diagnostic_assets


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
        map_text = (ROOT / 'candidate-corridor.xodr').read_text()
        for name, content in diagnostic_assets(plan, case_id, 'primary', map_text).items():
            construction['files'].append({'path': name, 'content': content})
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
        fallback = deepcopy(construction)
        for item in fallback['files']:
            if item['path'] == 'config.json':
                value = json.loads(item['content'])
                value['source_variant'] = 'fallback1'
                item['content'] = json.dumps(value, indent=2) + '\n'
        assets = diagnostic_assets(plan, case_id, 'fallback1', map_text)
        for item in fallback['files']:
            if item['path'] in assets:
                item['content'] = assets[item['path']]
        fallback_dir = target / 'fallback1'
        fallback_dir.mkdir(exist_ok=True)
        fallback_path = fallback_dir / 'construction.json'
        fallback_path.write_text(json.dumps(fallback, indent=2) + '\n')
        result[-1]['fallback1'] = str(fallback_path.relative_to(ROOT))
        result[-1]['fallback1_sha256'] = hashlib.sha256(fallback_path.read_bytes()).hexdigest()
    if len(result) != 9 or len({row["case_id"] for row in result}) != 9:
        raise ValueError("six branch cases and three exact sweep cases required")
    (ROOT / "selected-constructions.json").write_text(
        json.dumps({"format": "worker-selected-draft-constructions",
                    "assignment_id": plan["assignment_id"], "cases": result}, indent=2) + "\n")
    return result


if __name__ == "__main__":
    print(json.dumps({"selected": len(write_selected()), "status": "draft"}))
