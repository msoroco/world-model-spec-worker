"""Synthetic measured entry-gap and missing-original-evidence fallback switches."""
import copy
import json
from build import CASES, HERE, put


def triggers(saved):
    if (saved.get("format") != "c111294-2502-synthetic-saved-v1" or
            saved.get("synthetic") is not True or saved.get("delivery_ready") is not False):
        raise ValueError("Untrusted entry measurement")
    gap = saved["ego_minus_other_front_entry_s"]
    return {"fallback1": gap is None or abs(gap) < saved["trigger_slow_if_abs_entry_gap_below_s"],
            "fallback2": not saved.get("original_pixel_reviewed", False) and saved["trigger_overview_if_original_review_missing"],
            "fallback3": not saved.get("original_device_and_yield_evidence", False) and saved["trigger_stop_if_original_device_or_yield_evidence_missing"]}


def prove():
    cases = {}
    positives = negatives = 0
    for suffix in CASES:
        primary = json.loads((HERE / "synthetic" / suffix / "primary" / "saved.json").read_text())
        slower = json.loads((HERE / "synthetic" / suffix / "fallback1" / "saved.json").read_text())
        observed = triggers(primary)
        if observed != {"fallback1": True, "fallback2": True, "fallback3": True} or \
                triggers(slower)["fallback1"]:
            raise AssertionError("Measured slowdown mitigation failed")
        cases[suffix] = {"primary_gap_s": primary["ego_minus_other_front_entry_s"],
                         "slower_gap_s": slower["ego_minus_other_front_entry_s"],
                         "triggers": observed}
        positives += 1
        for field, value, fallback in (("ego_minus_other_front_entry_s", 3, "fallback1"),
                                       ("original_pixel_reviewed", True, "fallback2"),
                                       ("original_device_and_yield_evidence", True, "fallback3")):
            changed = copy.deepcopy(primary)
            changed[field] = value
            if triggers(changed)[fallback]:
                raise AssertionError("Switched trigger remained on")
            negatives += 1
    result = {"format": "c111294-2502-trigger-proof-v1", "cases": cases,
              "positive_count": positives, "negative_count": negatives,
              "synthetic_only": True, "delivery_ready": False}
    put(HERE / "trigger-proof.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(prove()))
