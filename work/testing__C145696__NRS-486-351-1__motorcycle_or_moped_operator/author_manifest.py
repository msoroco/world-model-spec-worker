"""Initialize exact manifest and measurement contract; later bind CPU proofs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from author_semantics import CHANNELS

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    disposition = plan["requirement_dispositions"][0]
    contract = {"format": "worker-measurement-contract",
                "requirements": [{"disposition_index": 0,
                                  "requirement": disposition["requirement"],
                                  "source": disposition["source"],
                                  "output_key": "adjacent_lane_passage", "method": "analyze",
                                  "value_type": "object", "kind": "measured",
                                  "inputs": ["lane-split-history.jsonl", "lane-split-scene.json",
                                             "trace.jsonl", "video_frames.jsonl"]}],
                "negative": {"remove": ["lane-split-scene.json"],
                             "error_contains": "Missing required source: lane-split-scene.json"}}
    write(ROOT / "measurement-contract.json", contract)
    entries = []
    for index, item in enumerate(plan["cases"]):
        cid = item["case_id"]
        suffix = cid.split("__")[-1]
        path = ROOT / ("construction.json" if index == 0 else
                       "cases/" + suffix + "/construction.json")
        alternate = ROOT / "cases" / suffix / "fallback1" / "construction.json"
        entries.append({"case_id": cid, "kind": "delivery",
                        "construction": str(path.relative_to(ROOT)),
                        "construction_sha256": sha(path),
                        "fixture_recipe": str((ROOT / ("diagnostic-" + suffix + "-recipe.json")).relative_to(REPO)),
                        "measurement_contract": "measurement-contract.json",
                        "measurement_procedure": {"entrypoint": "analysis.py"},
                        "source_gate": "original reviewed one-way map, adjacent lane pair, body clearance, participant blueprints, chapter vehicle class and independent operator-duty sources required",
                        "acquisition": {name: {"entrypoint": "original_capture.py",
                                               "method": "run_native original 900-frame map and three actor readback",
                                               "evidence": "lane-split-history.jsonl and channel-" + name + ".jsonl"}
                                        for name in CHANNELS},
                        "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                           "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
                        "candidate_risk": {"status": "physical",
                                           "reason": "Narrow between-body passage or ego spawn collision can prevent a complete original 45s trajectory even after surveyed static clearance; upstream staging may give the controller room to settle."},
                        "candidates": [{"id": "fallback1",
                                        "construction": str(alternate.relative_to(ROOT)),
                                        "construction_sha256": sha(alternate),
                                        "trigger": {"source": "native-run-status.json and original lane-split-history.jsonl",
                                                    "metric": "ego spawn collision or observed longitudinal/lateral body-clearance and incomplete passage",
                                                    "failure_condition": "Original source reports ego spawn failure or collision/incomplete passage after a reviewed primary attempt"},
                                        "changed_knobs": ["ego_start_shift_m: 0 to -3 metres upstream"]}]})
    write(ROOT / "execution-manifest.json", {"format": "worker-execution-manifest",
                                              "assignment_id": AID,
                                              "status": "source_gated_draft",
                                              "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
                                              "cases": entries})


if __name__ == "__main__":
    main()
