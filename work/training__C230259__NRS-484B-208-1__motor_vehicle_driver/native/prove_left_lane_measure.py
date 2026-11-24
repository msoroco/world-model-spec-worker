"""Run a two-case source-bound CPU lane relation and comparison diagnostic."""

import copy
import json
import os
import tempfile
from pathlib import Path

from left_lane_measure import FRAMES, RATE, measure, sha


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def reject(label, trace, context, hashes, contains):
    try:
        measure(trace, context, hashes)
    except ValueError as error:
        assert contains in str(error), (label, str(error))
        return {"mutation": label, "error": str(error)}
    raise AssertionError("Invalid source accepted: " + label)


def main():
    scratch = REPO / ".runtime-work"
    scratch.mkdir(exist_ok=True)
    assert Path(os.environ["TMPDIR"]).resolve().is_relative_to(scratch.resolve())
    with tempfile.TemporaryDirectory(prefix="c230259-lane-measure-", dir=scratch) as temporary:
        root = Path(temporary)
        context = {"source_kind": "synthetic_native_sample", "capture_hz": RATE,
                   "frames": FRAMES, "same_direction_marked_lane_count": 2,
                   "extreme_left_lane_id": 1, "right_lane_id": 0,
                   "posted_speed_limit_mps": 25.0,
                   "controlled_access_original_verified": False,
                   "posted_limit_original_verified": False}
        context_path = root / "native-road-context.json"
        write_json(context_path, context)
        base = []
        for frame in range(FRAMES):
            time = frame / RATE
            base.append({"frame": frame, "native_frame": 800 + frame,
                         "time_s": time, "source_kind": "synthetic_native_sample",
                         "ego_longitudinal_m": 20.0 * time,
                         "rear_longitudinal_m": -70.0 + 27.0 * time,
                         "ego_speed_mps": 20.0, "rear_speed_mps": 27.0,
                         "ego_lane_id": 1, "rear_lane_id": 1})
        measured = {}
        paths = {}
        for group in ("reference", "contrast"):
            rows = copy.deepcopy(base)
            if group == "contrast":
                for row in rows[140:]:
                    row["ego_lane_id"] = 0
            path = root / f"{group}" / "native-actors.jsonl"
            path.parent.mkdir()
            path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
            hashes = {path.name: sha(path), context_path.name: sha(context_path)}
            measured[group] = measure(path, context_path, hashes)
            paths[group] = (path, hashes)
        ref, contrast = measured["reference"], measured["contrast"]
        assert ref["overtake_crossing_frame"] == contrast["overtake_crossing_frame"] == 200
        assert ref["slow_extreme_left_after_overtake_frames"] == 400
        assert contrast["slow_extreme_left_after_overtake_frames"] == 0
        assert not ref["ego_exited_left_before_crossing"] and contrast["ego_exited_left_before_crossing"]
        assert all(not item["controlled_access_verified"] and not item["posted_limit_original_verified"]
                   and item["driver_knowledge_or_reasonable_notice"] is None
                   and item["subsection_2_exception_review"] is None and item["legal_verdict"] is None
                   for item in measured.values())
        ref_rows = [json.loads(line) for line in paths["reference"][0].read_text().splitlines()]
        contrast_rows = [json.loads(line) for line in paths["contrast"][0].read_text().splitlines()]
        assert all({key: value for key, value in left.items() if key != "ego_lane_id"} ==
                   {key: value for key, value in right.items() if key != "ego_lane_id"}
                   for left, right in zip(ref_rows, contrast_rows))
        negatives = []
        path, hashes = paths["reference"]
        with path.open("a") as stream:
            stream.write("\n")
        negatives.append(reject("changed_sealed_source", path, context_path, hashes,
                                "Sealed Native source differs"))
        path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in base))
        bad = copy.deepcopy(base)
        bad[201]["native_frame"] = bad[200]["native_frame"]
        path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in bad))
        bad_hashes = {path.name: sha(path), context_path.name: sha(context_path)}
        negatives.append(reject("broken_native_frame_join", path, context_path, bad_hashes,
                                "Native frame/time join differs"))
        bad = copy.deepcopy(base)
        bad[50]["rear_lane_id"] = 0
        path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in bad))
        bad_hashes = {path.name: sha(path), context_path.name: sha(context_path)}
        negatives.append(reject("rear_not_in_left_lane", path, context_path, bad_hashes,
                                "Lane identity differs"))
    print(json.dumps({"format": "c230259-lane-measure-comparison-cpu-v1",
                      "passed": True, "diagnostic_only": True,
                      "source_kind": "synthetic_native_sample",
                      "reference": ref, "contrast": contrast,
                      "fixed_source_fields_except_lane": True,
                      "negative_rejections": negatives,
                      "original_native_observed": False,
                      "physical_or_legal_completion_claimed": False}, indent=2))


if __name__ == "__main__":
    main()
