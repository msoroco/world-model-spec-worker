"""600-frame synthetic positive/negative proof for saved_entry_measurement."""

import copy
import hashlib
import json
from pathlib import Path

from saved_entry_measurement import measure


HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_source(contrary=False):
    frames = []
    for i in range(600):
        x = -1.0 if i < 200 else (7.0 if i >= 321 else (i - 200) * 0.05)
        frames.append({
            "frame": i,
            "time_s": i / 20,
            "pedestrian_id": "walker.subject",
            "pedestrian_xy": [x, 1.0],
            "traffic_signal": {"id": "signal.vehicle.approach", "state": "circular_green"},
            "pedestrian_signal": {"id": "signal.pedestrian.crosswalk", "state": "dont_walk" if contrary else "walk"},
        })
    return {
        "format": "pedestrian-entry-raw-v1",
        "hz": 20,
        "frame_count": 600,
        "camera_ids": ["overview", "approach", "reference_corner", "driver_reference"],
        "pedestrian_id": "walker.subject",
        "crosswalk": {"id": "crosswalk.1", "bounds_xy": [0.0, 0.0, 6.0, 2.0]},
        "governing_devices": {"traffic_head": "signal.vehicle.approach", "pedestrian_head": "signal.pedestrian.crosswalk"},
        "frames": frames,
    }


def main():
    positives = {}
    for name, contrary in (("permitted_entry", False), ("contrary_device", True)):
        result = measure(make_source(contrary))
        assert result["entry_frame"] == 200 and result["exit_frame"] == 321
        assert result["permission_branch_307_2b_observed"] is (not contrary)
        assert result["deferred_to_484b_283_observed"] is contrary
        assert result["legal_verdict"] is None and not result["native_provenance"]
        positives[name] = result
    changed_after_entry = make_source()
    for frame in changed_after_entry["frames"][240:]:
        frame["traffic_signal"]["state"] = "circular_yellow"
    after_result = measure(changed_after_entry)
    assert after_result["permission_branch_307_2b_observed"] is True
    positives["signal_changes_after_entry"] = after_result
    red_at_entry = make_source()
    red_at_entry["frames"][200]["traffic_signal"]["state"] = "circular_red"
    red_result = measure(red_at_entry)
    assert red_result["circular_green_at_entry"] is False
    assert red_result["permission_branch_307_2b_observed"] is False
    positives["red_at_entry_no_permission_branch"] = red_result
    negatives = {}
    base = make_source()
    mutations = {
        "missing_raw_frame": lambda x: x["frames"].pop(240),
        "wrong_time_join": lambda x: x["frames"][200].update(time_s=11.0),
        "missing_ped_signal": lambda x: x["frames"][200].pop("pedestrian_signal"),
        "wrong_governing_head": lambda x: x["frames"][200]["traffic_signal"].update(id="signal.other"),
        "missing_crosswalk_geometry": lambda x: x.pop("crosswalk"),
        "missing_camera_identity": lambda x: x["camera_ids"].pop(),
        "no_observed_entry": lambda x: [f.update(pedestrian_xy=[-1.0, 1.0]) for f in x["frames"]],
    }
    for name, mutation in mutations.items():
        changed = copy.deepcopy(base)
        mutation(changed)
        try:
            measure(changed)
        except ValueError as exc:
            negatives[name] = str(exc)
        else:
            raise AssertionError(name + " was accepted")
    receipt = {
        "format": "pedestrian-entry-cpu-diagnostic-v1",
        "assignment_id": "training__C111331__NRS-484B-307-2b__pedestrian",
        "script_sha256": sha(HERE / "saved_entry_measurement.py"),
        "positive_results": positives,
        "negative_rejections": negatives,
        "source_type": "synthetic raw packets; no Native source or camera pixels",
        "limitations": ["No pinned runtime offline or compatibility proof", "No process-saved adapter proof", "No physical or legal acceptance"],
    }
    out = HERE / "saved-entry-diagnostic.json"
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"positive": len(positives), "negative": len(negatives), "receipt_sha256": sha(out)}, sort_keys=True))


if __name__ == "__main__":
    main()
