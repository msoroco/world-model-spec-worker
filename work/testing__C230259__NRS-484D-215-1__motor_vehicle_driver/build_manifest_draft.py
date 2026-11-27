"""Build exact eight-case draft for offline and compatibility CPU proofs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PLAN = json.loads((ROOT / "case-plan.json").read_text())
BATCH = json.loads((REPO / "batch.json").read_text())
CHANNELS = ("original_actor_state", "original_four_view_frame_map",
            "original_beam_pixels", "original_oncoming_distance")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    cases = []
    for case in PLAN["cases"]:
        suffix = case["case_id"].split("__")[-1]
        construction = ROOT / "cases" / suffix / "construction.json"
        fallback = ROOT / "cases" / suffix / "construction-fallback1.json"
        cases.append({"case_id": case["case_id"], "kind": "delivery",
                      "construction": construction.relative_to(ROOT).as_posix(),
                      "construction_sha256": sha(construction),
                      "measurement_contract": "measurement-contract-" + suffix + ".json",
                      "measurement_procedure": {"entrypoint": "analysis.py"},
                      "fixture_recipe": (ROOT / "cases" / suffix / "fixture-recipe.json").relative_to(REPO).as_posix(),
                      "acquisition": {name: {"entrypoint": "beam_publication.py",
                                             "evidence": name + ".jsonl",
                                             "method": "source-joined original Native 20 Hz frame projection"}
                                      for name in CHANNELS},
                      "candidate_risk": {"status": "physical",
                          "reason": "Reviewed primary camera pose may fail to resolve distant persons or an oncoming driver's eye ROI."},
                      "candidates": [{"id": "fallback1",
                          "construction": fallback.relative_to(ROOT).as_posix(),
                          "construction_sha256": sha(fallback),
                          "changed_knobs": ["camera pose source: reviewed alternate_cameras in source-sealed site packet"],
                          "trigger": {"source": "original approach and driver-reference RGB frames",
                                      "metric": "frame-specific target and oncoming-eye ROI pixel resolvability",
                                      "failure_condition": "primary reviewed camera pose does not resolve a required person, vehicle or oncoming-eye ROI"}}]})
    return {"format": "worker-execution-manifest", "assignment_id": PLAN["assignment_id"],
            "runtime_manifest_sha256": BATCH["runtime"]["source_manifest_sha256"],
            "status": "selected_cpu_proofs_in_progress", "cases": cases}


if __name__ == "__main__":
    (ROOT / "execution-manifest.draft.json").write_text(json.dumps(build(), indent=2) + "\n")
