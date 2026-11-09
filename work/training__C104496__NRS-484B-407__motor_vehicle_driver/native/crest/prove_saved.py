"""Check all eight saved measurements and tamper rejection."""
import copy
import json
import tempfile
from pathlib import Path
from build import CASES, HERE, POLICIES, put
from saved import build_saved, process


def prove():
    build_saved()
    positives = negatives = 0
    totals = {}
    for suffix in CASES:
        for candidate in POLICIES:
            bundle = HERE / "drafts" / suffix / candidate
            raw = HERE / "synthetic" / suffix / candidate / "raw.json"
            saved = json.loads((raw.parent / "saved.json").read_text())
            if process(bundle, raw) != saved:
                raise AssertionError("Saved measurement drift")
            positives += 1
            totals[suffix + "/" + candidate] = [saved["turn_frames"],
                                                   saved["analytic_both_clear_turn_frames"],
                                                   saved["analytic_road_above_ray_turn_frames"]]
            with tempfile.TemporaryDirectory() as tmp:
                bad_path = Path(tmp) / "raw.json"
                original = json.loads(raw.read_text())
                for field, value in (("synthetic", False), ("original_native_observed", True),
                                     ("human_visibility_reviewed", True), ("tracks_sha256", "bad")):
                    bad = copy.deepcopy(original); bad[field] = value; put(bad_path, bad)
                    try:
                        process(bundle, bad_path)
                    except ValueError:
                        negatives += 1
                    else:
                        raise AssertionError("Negative accepted: " + field)
                for field, value in (("frame", 99), ("requested_ego_xyz_m", [0, 0, 0]),
                                     ("analytic_road_above_ray_m", [0, 0])):
                    bad = copy.deepcopy(original); bad["rows"][100][field] = value; put(bad_path, bad)
                    try:
                        process(bundle, bad_path)
                    except ValueError:
                        negatives += 1
                    else:
                        raise AssertionError("Row mutation accepted: " + field)
    if totals["probe_01/primary"][2] != 0 or totals["probe_02/primary"][1] != 0:
        raise AssertionError("Synthetic grade contrast failed")
    proof = {"format": "c104496-synthetic-saved-proof-v1", "positive_count": positives,
             "negative_count": negatives, "turn_clear_blocked_counts": totals,
             "original_native_observed": False, "delivery_ready": False}
    put(HERE / "saved-proof.json", proof)
    return proof


if __name__ == "__main__":
    print(json.dumps(prove()))
