"""Prove two saved-only exact-case primary source finalizations on CPU."""

import copy
import json
import os
import tempfile
from pathlib import Path

from left_lane_measure import FRAMES, RATE, sha
from saved_left_lane_finalizer import ASSIGNMENT, SOURCES, finalize


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def require_rejected(label, attempt, seal, text):
    try:
        finalize(attempt, seal)
    except ValueError as error:
        assert text in str(error), (label, str(error))
        return {"mutation": label, "error": str(error)}
    raise AssertionError("Invalid saved source accepted: " + label)


def main():
    scratch = REPO / ".runtime-work"
    scratch.mkdir(exist_ok=True)
    assert Path(os.environ["TMPDIR"]).resolve().is_relative_to(scratch.resolve())
    results = {}
    negatives = []
    with tempfile.TemporaryDirectory(prefix="c230259-saved-left-", dir=scratch) as temporary:
        root = Path(temporary)
        for group in ("reference", "contrast"):
            attempt = root / group
            attempt.mkdir()
            context = {"source_kind": "synthetic_native_sample", "capture_hz": RATE,
                       "frames": FRAMES, "same_direction_marked_lane_count": 2,
                       "extreme_left_lane_id": 1, "right_lane_id": 0,
                       "posted_speed_limit_mps": 25.0,
                       "controlled_access_original_verified": False,
                       "posted_limit_original_verified": False}
            (attempt / SOURCES[1]).write_text(json.dumps(context, sort_keys=True) + "\n")
            with (attempt / SOURCES[0]).open("w") as trace:
                for frame in range(FRAMES):
                    time = frame / RATE
                    row = {"frame": frame, "native_frame": 1000 + frame,
                           "time_s": time, "source_kind": "synthetic_native_sample",
                           "ego_longitudinal_m": 20.0 * time,
                           "rear_longitudinal_m": -70.0 + 27.0 * time,
                           "ego_speed_mps": 20.0, "rear_speed_mps": 27.0,
                           "ego_lane_id": 1 if group == "reference" or frame < 140 else 0,
                           "rear_lane_id": 1}
                    trace.write(json.dumps(row, sort_keys=True) + "\n")
            seal = {"case_id": ASSIGNMENT + "__" + group,
                    "candidate_id": "primary", "native_exit_code": 0,
                    "source_kind": "synthetic_native_sample",
                    "source_sha256": {name: sha(attempt / name) for name in SOURCES}}
            results[group] = finalize(attempt, seal)
            if group == "reference":
                with (attempt / SOURCES[0]).open("ab") as trace:
                    trace.write(b"\n")
                negatives.append(require_rejected("changed_native_trace", attempt, seal,
                                                  "Sealed Native source differs"))
                negatives.append(require_rejected("wrong_exact_case", attempt,
                                                  dict(seal, case_id=ASSIGNMENT + "__other"),
                                                  "Exact left-lane case required"))
                incomplete = copy.deepcopy(seal)
                del incomplete["source_sha256"][SOURCES[1]]
                negatives.append(require_rejected("missing_context_seal", attempt, incomplete,
                                                  "Complete saved source inventory required"))
    assert results["reference"]["measurements"]["slow_extreme_left_after_overtake_frames"] == 400
    assert results["contrast"]["measurements"]["slow_extreme_left_after_overtake_frames"] == 0
    assert all(item["recorded_only"] and not item["accepted"] and
               item["legal_verdict"] is None and not item["physical_completion_claimed"]
               for item in results.values())
    print(json.dumps({"format": "c230259-saved-left-lane-primary-cpu-proof-v1",
                      "passed": True, "diagnostic_only": True,
                      "exact_primary_cases": results,
                      "negative_rejections": negatives,
                      "runtime_process_saved_connected": False,
                      "four_camera_capture_connected": False,
                      "original_native_observed": False,
                      "physical_or_legal_completion_claimed": False}, indent=2))


if __name__ == "__main__":
    main()
