"""Positive and switched negative CPU proof of three quality trigger rules."""
import json

from build import CASE, HERE, write
from fallback_quality import decide, request_measurements


def prove():
    records = []
    positive = negative = 0
    for suffix in ("witness_1", "witness_2"):
        bundles = {candidate: HERE / "drafts" / suffix / candidate
                   for candidate in ("primary", "fallback1", "fallback2", "fallback3")}
        measured = {candidate: request_measurements(bundle) for candidate, bundle in bundles.items()}
        baseline = decide(measured["primary"], allow_synthetic=True)
        assert baseline["triggers"] == {"fallback1": True, "fallback2": False,
                                        "fallback3": False}
        assert measured["fallback1"]["approach_speed_mps"] < 7
        assert measured["fallback2"]["camera_policy"] == "elevated_overview"
        assert measured["fallback3"]["signal_to_entry_window_s"] > baseline["metrics"]["signal_to_entry_window_s"]
        cases = [
            ("fallback1", {**measured["primary"], "approach_speed_mps": 8.0},
             {**measured["primary"], "approach_speed_mps": 5.0}),
            ("fallback2", {**measured["primary"], "signal_and_other_visible_fraction": .8},
             {**measured["primary"], "signal_and_other_visible_fraction": .95}),
            ("fallback3", {**measured["primary"], "signal_to_entry_window_s": 2.5},
             {**measured["primary"], "signal_to_entry_window_s": 4.5})]
        for candidate, on, off in cases:
            on_decision = decide(on, allow_synthetic=True)
            off_decision = decide(off, allow_synthetic=True)
            assert on_decision["triggers"][candidate]
            assert not off_decision["triggers"][candidate]
            assert on_decision["selected_candidate"] is None
            assert not on_decision["original_native_observed"]
            positive += 1
            negative += 1
        try:
            decide(measured["primary"])
        except ValueError:
            negative += 1
        else:
            raise AssertionError("Synthetic request accepted as original quality")
        records.append({"case_id": suffix, "measured_requests": measured,
                        "primary_trigger_diagnostic": baseline})
    result = {"format": "c111603-3079a-fallback-quality-proof-v1",
              "assignment_id": CASE.name, "positive_count": positive,
              "negative_count": negative, "records": records,
              "synthetic_preflight_only": True, "original_native_observed": False,
              "delivery_ready": False}
    write(HERE / "fallback-quality-proof.json", result)
    return {k: result[k] for k in ("format", "positive_count", "negative_count",
                                   "synthetic_preflight_only", "delivery_ready")}


if __name__ == "__main__":
    print(json.dumps(prove(), sort_keys=True))
