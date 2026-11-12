"""Prepare a source-hashed seven-case CPU selection probe without changing delivery."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
selected = json.loads((HERE / "execution-manifest.json").read_text())
draft = json.loads((HERE / "draft-rail-at-execution-manifest.json").read_text())
assert len(selected["cases"]) == 6 and len(draft["cases"]) == 1
rail_at = deepcopy(draft["cases"][0])
assert rail_at["case_id"].endswith("__rail_at")
rail_at["kind"] = "delivery"
rail_at["preparation_status"] = "selected_cpu_proofs_pending"
probe = deepcopy(selected)
probe["status"] = "partial_seven_case_cpu_probe"
probe["cases"].append(rail_at)
probe["selection_review"]["selected_case_ids"].append(rail_at["case_id"])
path = HERE / "update035-seven-case-probe-manifest.json"
path.write_text(json.dumps(probe, indent=2) + "\n")
print(json.dumps({"cases": 7, "candidates": 28,
                  "manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
