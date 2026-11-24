"""Run 600-frame source-meter positive and rejection checks."""
import hashlib
import json
import tempfile
from pathlib import Path
from crossing_meter import measure


def write(folder, rows, *, marked=None, intersection=None, ids=None, designated=None):
    trace = folder / "post-tick.jsonl"
    trace.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    context = {
        "frozen_cell": {"layout": "road", "maneuver": "travel", "control": "other_vehicle"},
        "source_kind": "synthetic_scene_request", "pedestrian_id": 5,
        "vehicle_ids": ids if ids is not None else [9, 12],
        "marked_crosswalk_intervals_y_m": marked if marked is not None else [[-2, 2]],
        "intersection_intervals_y_m": intersection if intersection is not None else [[-5, 5]],
        "designated_place_prohibition": designated,
        "trace_sha256": hashlib.sha256(trace.read_bytes()).hexdigest(),
    }
    (folder / "crossing-context.json").write_text(json.dumps(context, sort_keys=True) + "\n")


def rows_for(entry):
    rows = []
    for i in range(600):
        x = -5 if i < entry else min(5, -3.6 + .06 * (i - entry))
        y = 10
        rows.append({"native_frame": 1000+i, "time_s": i*.05, "pedestrian_id": 5,
                     "pedestrian_footprint_xy_m": [[x-.2,y-.2],[x+.2,y-.2],[x+.2,y+.2],[x-.2,y+.2]],
                     "vehicles": [
                         {"id": 9, "x_m": -1.75, "y_m": min(30,-20+.11*i), "speed_mps": 2.2},
                         {"id": 12, "x_m": 1.75, "y_m": min(30,-30+.09*i), "speed_mps": 1.8}]})
    return rows


def reject(folder, rows, message, **kwargs):
    write(folder, rows, **kwargs)
    try:
        measure(folder)
    except ValueError as exc:
        if message not in str(exc):
            raise
        return str(exc)
    raise AssertionError("Expected rejection: " + message)


def main():
    with tempfile.TemporaryDirectory(prefix="c230259-meter-") as temporary:
        folder = Path(temporary)
        good = rows_for(330)
        write(folder, good)
        waiting = measure(folder)
        assert waiting["outside_both_crosswalk_categories_at_entry"]
        assert waiting["roadway_entry_frame"] > 1000
        assert waiting["precedence_at_entry"] == {"9": "vehicle_first", "12": "pedestrian_first_or_vehicle_unobserved"}
        early = rows_for(145)
        write(folder, early)
        entering = measure(folder)
        assert entering["roadway_entry_frame"] < waiting["roadway_entry_frame"]
        assert entering["vehicles_on_roadway_at_entry"] == [9,12]
        assert entering["precedence_at_entry"] == {"9": "pedestrian_first_or_vehicle_unobserved", "12": "pedestrian_first_or_vehicle_unobserved"}
        marked = rows_for(145)
        for row in marked:
            row["pedestrian_footprint_xy_m"] = [[x,0] for x,_ in row["pedestrian_footprint_xy_m"]]
        write(folder, marked)
        assert not measure(folder)["outside_both_crosswalk_categories_at_entry"]
        errors = {}
        errors["missing_frame"] = reject(folder, early[:-1], "600 original")
        bad_time = rows_for(145)
        bad_time[300]["time_s"] += .05
        errors["time_discontinuity"] = reject(folder, bad_time, "continuity")
        errors["inventory_mismatch"] = reject(folder, early, "complete vehicle inventory", ids=[9])
        write(folder, early)
        with (folder / "post-tick.jsonl").open("a") as stream:
            stream.write(" ")
        try:
            measure(folder)
        except ValueError as exc:
            assert "hash differs" in str(exc)
            errors["stale_hash"] = str(exc)
        else:
            raise AssertionError("Stale source hash accepted")
        out = Path(__file__).resolve().parent / "source-meter-proof.json"
        out.write_text(json.dumps({"format": "c230259-meter-proof-v1", "passed": True,
                                   "waiting_request": waiting, "early_entry_request": entering,
                                   "negative_rejections": errors,
                                   "fixture_is_original_native": False,
                                   "legal_conclusion": None}, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"passed": True, "positive_cases": 3,
                          "negative_cases": len(errors), "proof": str(out)}, sort_keys=True))


if __name__ == "__main__":
    main()
