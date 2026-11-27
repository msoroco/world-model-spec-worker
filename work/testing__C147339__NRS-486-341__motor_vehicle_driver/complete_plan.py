"""Bind exact selected requirement, sources and camera contract to planned cases."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
SOURCE = "inputs/" + AID + "/assignment.json"
REQUIREMENT = ("Every motorcycle or moped when being driven on the highway is entitled to full "
               "use of the traffic lane it is occupying, and a person shall not drive another "
               "motor vehicle in a manner which would deprive any such motorcycle or moped of such use.")


def main():
    path = ROOT / "case-plan.json"
    plan = json.loads(path.read_text(encoding="utf-8"))
    ids = [case["case_id"] for case in plan["cases"]]
    plan["requirement_dispositions"] = [{"requirement": REQUIREMENT, "source": SOURCE,
                                          "status": "selected_required",
                                          "evidence_or_gap": "no_accepted_original_protected_lane_evidence",
                                          "case_ids": ids}]
    plan["source_observation_mapping"] = {}
    plan["camera_plan"] = {"profile": "overview1080-capability", "duration_s": 45,
                           "composition": "synchronized_four_view_primary",
                           "coverage": [{"view": view, "subject": subject,
                                         "interval": "entire original 45s"}
                                        for view, subject in (
                                            ("overview", "both vehicles and occupied lane"),
                                            ("approach", "ego approach and original protected motion"),
                                            ("reference_corner", "body-box relation to occupied lane"),
                                            ("driver_reference", "ego-mounted forward perspective"))]}
    plan["planning_status"] = "source_gated_exact_delivery_in_progress"
    plan["runtime_uncertainties"] = [
        "Original public highway, lane boundaries, vehicle classifications, motion and pixels need Native review.",
        "Legal full-use/deprivation interpretation is unresolved; body intrusion is physical context.",
    ]
    path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    contract = {"format": "worker-measurement-contract",
                "requirements": [{"disposition_index": 0, "requirement": REQUIREMENT,
                                  "source": SOURCE, "output_key": "protected_lane_use",
                                  "method": "analyze", "value_type": "object", "kind": "measured",
                                  "inputs": ["protected-lane-history.jsonl", "protected-lane-scene.json",
                                             "trace.jsonl", "video_frames.jsonl"]}],
                "negative": {"remove": ["protected-lane-scene.json"],
                             "error_contains": "Missing required source: protected-lane-scene.json"}}
    (ROOT / "measurement-contract.json").write_text(json.dumps(contract, indent=2) + "\n",
                                                     encoding="utf-8")


if __name__ == "__main__":
    main()
