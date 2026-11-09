"""Saved-processing negatives, controlled pairs and fallback trigger proof."""
import json
from pathlib import Path
import tempfile

from build import POLICIES, put, sha
from divided_opening import BRANCH, CENTERS
from prove_triggers import trigger
from saved_divided import process


def prove():
    positive = negative = joined = trigger_positive = trigger_negative = 0
    details = {}
    for suffix in CENTERS:
        saved_by_candidate = {}
        cfg_by_candidate = {}
        for candidate in POLICIES:
            bundle = BRANCH / "drafts" / suffix / candidate
            path = BRANCH / "synthetic" / suffix / candidate / "raw.json"
            saved_path = path.parent / "saved.json"
            measured = process(bundle, path)
            if (measured != json.loads(saved_path.read_text()) or
                    measured["raw_sha256"] != sha(path) or
                    measured["frames_joined"] != 800):
                raise ValueError("Saved divided branch measurement mismatch")
            positive += 1
            joined += 800
            saved_by_candidate[candidate] = measured
            cfg_by_candidate[candidate] = json.loads((bundle / "config.json").read_text())
            baseline = json.loads(path.read_text())
            for mutation in ("case", "config", "frame", "video", "actor", "body"):
                raw = json.loads(json.dumps(baseline))
                if mutation == "case":
                    raw["case_id"] += "-other"
                elif mutation == "config":
                    raw["config_sha256"] = "0" * 64
                elif mutation == "frame":
                    raw["rows"][3]["frame"] = 4
                elif mutation == "video":
                    raw["rows"][3]["video_frame"] = 4
                elif mutation == "actor":
                    raw["rows"][3]["ego"]["actor_id"] = 11
                else:
                    raw["rows"][3]["ego"]["body_xyz_m"][0][0] += 1
                with tempfile.TemporaryDirectory() as temporary:
                    mutated = Path(temporary) / "raw.json"
                    put(mutated, raw)
                    try:
                        process(bundle, mutated)
                    except ValueError:
                        negative += 1
                    else:
                        raise AssertionError("Saved divided mutation accepted: " + mutation)
        base = trigger(saved_by_candidate["primary"], cfg_by_candidate["primary"])
        if base != {"fallback1": True, "fallback2": True, "fallback3": True}:
            raise ValueError("Divided primary fallback triggers changed")
        switched = (
            ("fallback1", trigger(saved_by_candidate["fallback1"],
                                  cfg_by_candidate["fallback1"],
                                  original_pixels=True, reversal_proven=True)),
            ("fallback2", trigger(saved_by_candidate["primary"],
                                  cfg_by_candidate["primary"],
                                  original_pixels=True, reversal_proven=True)),
            ("fallback3", trigger(saved_by_candidate["fallback3"],
                                  cfg_by_candidate["fallback3"],
                                  original_pixels=True, reversal_proven=True)),
        )
        trigger_positive += 1
        for key, result in switched:
            if result[key]:
                raise ValueError("Divided fallback switched-condition negative failed")
            trigger_negative += 1
        details[suffix] = {
            "crossing_x_m": saved_by_candidate["primary"]["crossing_x_m"],
            "crossing_in_authored_opening":
                saved_by_candidate["primary"]["crossing_in_authored_opening"],
            "primary_stationary_frames":
                saved_by_candidate["primary"]["pre_turn_stationary_frames"],
            "fallback3_stationary_frames":
                saved_by_candidate["fallback3"]["pre_turn_stationary_frames"]}
    if (details["divided_reference"]["crossing_in_authored_opening"] or
            not details["divided_opening"]["crossing_in_authored_opening"] or
            abs(details["divided_opening"]["crossing_x_m"] -
                details["divided_reference"]["crossing_x_m"] - 45) > .0002):
        raise ValueError("Saved divided opening controlled comparison changed")
    result = {"format": "c111662-4033-divided-saved-proof-v1",
              "positive_count": positive, "negative_count": negative,
              "frames_joined": joined, "controlled_pairs": len(POLICIES),
              "trigger_positive_count": trigger_positive,
              "trigger_negative_count": trigger_negative,
              "cases": details, "synthetic_only": True,
              "original_native_observed": False, "delivery_ready": False}
    put(BRANCH / "saved-proof.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(prove()))
