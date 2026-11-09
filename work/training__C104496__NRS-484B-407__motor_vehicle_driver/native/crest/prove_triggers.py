"""Exercise three distinct fallback predicates on saved diagnostic measurements."""
import copy
import json
from build import CASES, HERE, put


def triggers(saved):
    if saved["format"] != "c104496-synthetic-saved-v1" or not saved["synthetic"] or saved["delivery_ready"]:
        raise ValueError("Untrusted or promoted saved measurement")
    clear_fraction = saved["minimum_clear_fraction"]
    return {
        "fallback1": clear_fraction is None or clear_fraction < saved["trigger_slow_if_clear_fraction_below"],
        "fallback2": not saved["human_visibility_reviewed"] and saved["trigger_overview_if_original_pixel_review_missing"],
        "fallback3": not saved["original_native_observed"] and saved["trigger_stop_if_original_500ft_body_rays_missing"],
    }


def prove():
    values = {}
    positive = negative = 0
    for suffix in CASES:
        path = HERE / "synthetic" / suffix / "primary" / "saved.json"
        saved = json.loads(path.read_text())
        result = triggers(saved)
        if result != {"fallback1": suffix == "probe_02", "fallback2": True, "fallback3": True}:
            raise AssertionError("Measured grade trigger mismatch")
        positive += 1
        values[suffix] = result
        changed = copy.deepcopy(saved)
        changed["minimum_clear_fraction"] = .5 if suffix == "probe_01" else 1.0
        if triggers(changed)["fallback1"] == result["fallback1"]:
            raise AssertionError("Clear-fraction trigger did not switch")
        negative += 1
        for field, fallback in (("human_visibility_reviewed", "fallback2"),
                                ("original_native_observed", "fallback3")):
            changed = copy.deepcopy(saved); changed[field] = True
            if triggers(changed)[fallback]:
                raise AssertionError("Evidence-trigger negative did not switch")
            negative += 1
    proof = {"format": "c104496-measured-trigger-proof-v1", "cases": values,
             "positive_count": positive, "negative_count": negative,
             "synthetic_only": True, "delivery_ready": False}
    put(HERE / "trigger-proof.json", proof)
    return proof


if __name__ == "__main__":
    print(json.dumps(prove()))
