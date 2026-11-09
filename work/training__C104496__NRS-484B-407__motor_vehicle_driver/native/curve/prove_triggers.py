"""Exercise three distinct curve fallback predicates on saved diagnostics."""
import copy
import json
from prove import HERE, put


def triggers(saved):
    if (saved.get("format") != "c104496-curve-synthetic-saved-v1" or
            saved.get("synthetic") is not True or saved.get("delivery_ready") is not False):
        raise ValueError("Untrusted curve diagnostic")
    fraction = saved["minimum_clear_fraction"]
    return {"fallback1": fraction is None or fraction < saved["trigger_slow_if_clear_fraction_below"],
            "fallback2": not saved["human_visibility_reviewed"] and saved["trigger_overview_if_original_pixel_review_missing"],
            "fallback3": not saved["original_native_observed"] and saved["trigger_stop_if_original_500ft_body_rays_missing"]}


def prove():
    saved = json.loads((HERE / "synthetic" / "probe_03" / "primary" / "saved.json").read_text())
    baseline = triggers(saved)
    if baseline != {"fallback1": False, "fallback2": True, "fallback3": True}:
        raise AssertionError("Unexpected analytic curve baseline")
    switched = {}
    for field, value, fallback in (("minimum_clear_fraction", .5, "fallback1"),
                                   ("human_visibility_reviewed", True, "fallback2"),
                                   ("original_native_observed", True, "fallback3")):
        changed = copy.deepcopy(saved)
        changed[field] = value
        observed = triggers(changed)[fallback]
        if observed == baseline[fallback]:
            raise AssertionError("Fallback did not switch: " + fallback)
        switched[fallback] = observed
    result = {"format": "c104496-curve-trigger-proof-v1", "baseline": baseline,
              "switched_conditions": switched, "positive_count": 1, "negative_count": 3,
              "synthetic_only": True, "original_native_observed": False,
              "delivery_ready": False}
    put(HERE / "trigger-proof.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(prove()))
