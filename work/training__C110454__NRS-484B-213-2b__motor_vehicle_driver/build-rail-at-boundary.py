"""Derive four unselected exact-100-foot rail candidates from the proven rail family.

The original selected manifest is left intact. This draft is for CPU proof before
any selected-manifest change and never claims a Native observation.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path


HERE = Path(__file__).resolve().parent
MANIFEST = json.loads((HERE / "execution-manifest.json").read_text())
SOURCE = next(e for e in MANIFEST["cases"] if e["case_id"].endswith("__rail_contrast"))
OLD_ID = SOURCE["case_id"]
NEW_ID = OLD_ID.removesuffix("rail_contrast") + "rail_at"
target = HERE / "draft-rail-at-candidates"


def modify(path: str, content: str) -> str:
    if path == "geometry_statutory.py":
        anchor = " 'rail_contrast':{'zone':'railroad_crossing','boundary_x_m':-20.0,'window':(-55.0,-35.0),'one_way':False},"
        assert content.count(anchor) == 1
        content = content.replace(anchor, anchor + "\n 'rail_at':{'zone':'railroad_crossing','boundary_x_m':-20.0,'window':(-65.0,-49.44),'one_way':False},")
        content = content.replace("    for index in range(round((12-start)/.1)+1):\n        x=round(start+index*.1,4)",
                                  "    step=.02 if case=='rail_at' else .1\n    for index in range(round((12-start)/step)+1):\n        x=round(start+index*step,4)")
        content = content.replace("nearest<STATUTORY_APPROACH_M", "nearest<=STATUTORY_APPROACH_M")
        assert "step=.02 if case=='rail_at'" in content
        return content
    if path == "engineering.py":
        return content.replace('"rail_contrast", "oneway_absent"', '"rail_contrast", "rail_at", "oneway_absent"')
    if path == "statutory_context.py":
        anchor = " 'rail_contrast':('railroad_crossing',False,-20.0,True),"
        assert content.count(anchor) == 1
        return content.replace(anchor, anchor + "\n 'rail_at':('railroad_crossing',False,-20.0,True),")
    if path == "finalize.py":
        return content.replace("'rail_contrast':'within_100_ft',", "'rail_contrast':'within_100_ft','rail_at':'within_100_ft',")
    if path == "tests/test_bundle_statutory_context.py":
        content = content.replace("self.assertEqual(result['case_results']['rail_contrast']['sampled_relation'],'within_100_ft')",
                                  "self.assertEqual(result['case_results']['rail_contrast']['sampled_relation'],'within_100_ft')\n        self.assertEqual(result['case_results']['rail_at']['nearest_full_body_front_distance_m'],30.48)")
        return content.replace("else -20\n", "else -53.08 if case=='rail_at' else -20\n")
    if path == "config.json":
        return content.replace(OLD_ID, NEW_ID).replace('"case_suffix": "rail_contrast"', '"case_suffix": "rail_at"')
    return content.replace(OLD_ID, NEW_ID)


draft = deepcopy(MANIFEST)
new_entry = deepcopy(SOURCE)
new_entry["case_id"] = NEW_ID
new_entry["kind"] = "statutory_numeric_boundary_draft"
new_entry["preparation_status"] = "draft_offline_proof_pending"
for key in ("offline", "compatibility", "negative", "post_capture", "native_handoff", "acquisition", "physical_preparation", "delivery_acceptance"):
    new_entry.pop(key, None)
new_entry["candidates"] = []
for candidate_id in ("primary", "fallback1", "fallback2", "fallback3"):
    source_ref = SOURCE if candidate_id == "primary" else next(c for c in SOURCE["candidates"] if c["id"] == candidate_id)
    source = json.loads((HERE / source_ref["construction"]).read_text())
    construction = deepcopy(source)
    construction["case_id"] = NEW_ID
    for f in construction["files"]:
        f["content"] = modify(f["path"], f["content"])
    construction["status"] = "draft_exact_100_ft_cpu_candidate"
    out = target / candidate_id / "construction.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(construction, indent=2) + "\n")
    ref = {"construction": str(out.relative_to(HERE)), "construction_sha256": hashlib.sha256(out.read_bytes()).hexdigest()}
    if candidate_id == "primary":
        new_entry.update(ref)
    else:
        c = deepcopy(source_ref)
        for key in ("offline", "compatibility"):
            c.pop(key, None)
        c.update(ref)
        new_entry["candidates"].append(c)
draft["status"] = "draft_unselected_rail_at_boundary"
draft["cases"] = [new_entry]
path = HERE / "draft-rail-at-execution-manifest.json"
path.write_text(json.dumps(draft, indent=2) + "\n")
print(json.dumps({"case_id": NEW_ID, "draft_manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                  "candidate_count": 4}, indent=2))
