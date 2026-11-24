"""Review exact draft fallback knobs before any delivery selection."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CASES = (("crest", "probe_01"), ("crest", "probe_02"), ("curve", "probe_03"))
CHOICES = ("primary", "fallback1", "fallback2", "fallback3")
FIXED = ("assignment_id", "case_id", "assignment_sha256", "frames", "rate_hz",
         "source_text", "ego_blueprint", "other_vehicle_blueprint", "grade_height_m",
         "road_sha256")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def examine(configs: dict[str, dict]) -> dict:
    primary = configs["primary"]
    assert primary["frames"] == 700 and primary["rate_hz"] == 20
    assert primary["stop_before_crest"] is False
    for choice, config in configs.items():
        for key in FIXED:
            if config.get(key) != primary.get(key):
                raise ValueError(f"{choice} changed fixed {key}")
        if config["candidate_id"] != choice:
            raise ValueError(f"{choice} candidate identity differs")
    slower = configs["fallback1"]
    overview = configs["fallback2"]
    stop = configs["fallback3"]
    if not (slower["stop_before_crest"] is False and
            slower["camera_policy"] == primary["camera_policy"] and
            0 < slower["requested_speed_mps"] < primary["requested_speed_mps"]):
        raise ValueError("Slower fallback changed reversal or camera policy")
    if not (overview["stop_before_crest"] is False and
            overview["requested_speed_mps"] == primary["requested_speed_mps"] and
            overview["camera_policy"] == "elevated_overview"):
        raise ValueError("Overview fallback changed reversal or speed")
    if stop["stop_before_crest"] is not True:
        raise ValueError("Stop diagnostic no longer exercises nonreversal")
    return {"case_id": primary["case_id"], "selected_candidate_ids": ["fallback1", "fallback2"],
            "excluded_diagnostic_candidate": "fallback3",
            "excluded_reason": "Stops before crest and has no reversal turn frames; changes the required case maneuver",
            "fallback1_changed_knobs": ["requested_speed_mps"],
            "fallback2_changed_knobs": ["camera_policy"],
            "fixed": list(FIXED), "duration_s": 35}


def prove() -> dict:
    reviews = []
    config_hashes = {}
    all_configs = {}
    for branch, case in CASES:
        configs = {}
        for choice in CHOICES:
            path = HERE / branch / "drafts" / case / choice / "config.json"
            configs[choice] = json.loads(path.read_text())
            config_hashes[f"{branch}/{case}/{choice}"] = sha(path)
        reviews.append(examine(configs))
        all_configs[case] = configs
    # Linked cases use the same controller and camera alternatives; only the
    # deliberate grade/curvature comparison variables may differ.
    policies = {(case, choice): (configs[choice]["requested_speed_mps"],
                                configs[choice]["camera_policy"],
                                configs[choice]["stop_before_crest"])
                for case, configs in all_configs.items() for choice in CHOICES}
    for choice in CHOICES:
        if len({policies[case, choice] for case in all_configs}) != 1:
            raise ValueError("Linked comparison candidate policies differ")
    mutations = 0
    for case, configs in all_configs.items():
        for choice, field, value in (("fallback1", "grade_height_m", 999),
                                     ("fallback1", "stop_before_crest", True),
                                     ("fallback2", "requested_speed_mps", 99),
                                     ("fallback2", "frames", 699),
                                     ("fallback2", "road_sha256", "0" * 64)):
            changed = {key: dict(item) for key, item in configs.items()}
            changed[choice][field] = value
            try:
                examine(changed)
            except ValueError:
                mutations += 1
            else:
                raise AssertionError(f"Accepted changed {case}/{choice}/{field}")
    proof = {"format": "c104496-draft-candidate-risk-review-v1",
             "assignment_id": ROOT.name, "status": "draft_review_only",
             "source_config_sha256": config_hashes, "case_reviews": reviews,
             "linked_policy_checks": len(CHOICES), "rejected_mutations": mutations,
             "selected_delivery_cases": 0, "physical_outcomes_observed": False,
             "next_cpu_actions": ["Qualify accepted evidence and select exact uncovered cases",
                                  "Build source-only current-v2 fixture and primary compatibility/process-saved proof",
                                  "Retest two retained fallback constructions after selected manifest binding"]}
    path = HERE / "candidate-risk-review.json"
    path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
    return proof


if __name__ == "__main__":
    print(json.dumps(prove(), sort_keys=True))
