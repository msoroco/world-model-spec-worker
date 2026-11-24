"""Source-only emergency call versus ordinary travel measurement diagnostic."""
import json
from pathlib import Path
import tempfile

from measure import measure

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BRANCHES = {
    "probe_a": {"call": True, "pursuit": False, "siren": True, "lamp": True},
    "probe_b": {"call": False, "pursuit": False, "siren": True, "lamp": True},
    "pursuit": {"call": False, "pursuit": True, "siren": True, "lamp": True},
    "call_lamps_only": {"call": True, "pursuit": False, "siren": False, "lamp": True},
    "ordinary_lamps_only": {"call": False, "pursuit": False, "siren": False, "lamp": True},
}


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def make_source(base, case):
    if case not in BRANCHES:
        raise ValueError("Unknown exact branch: " + case)
    branch = BRANCHES[case]
    config = json.loads((HERE / "config.json").read_text())
    config["case_id"] = config["case_id"].rsplit("__", 1)[0] + "__" + case
    config["emergency_call_requested"] = branch["call"]
    config["immediate_pursuit_requested"] = branch["pursuit"]
    config["siren_requested"] = branch["siren"]
    config["warning_lamps_requested"] = branch["lamp"]
    (base / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    native, mapping, dispatch = [], [], []
    for i in range(600):
        frame = i + 1000
        time_s = (i + 1) / 20
        x = 5 + 2 * time_s
        native.append({"source_kind": "synthetic_native_sample", "native_frame": frame,
                       "time_s": time_s, "vehicle_actor_id": 101,
                       "other_vehicle_actor_id": 202, "ego_x_m": x,
                       "ego_speed_mps": 2.0,
                       "siren_observed": branch["siren"] and 100 <= i < 300,
                       "warning_lamp_observed": branch["lamp"] and 80 <= i < 330})
        mapping.append({"video_frame": i, "native_frame": frame, "time_s": time_s})
        dispatch.append({"native_frame": frame, "time_s": time_s,
                         "emergency_call_documented": branch["call"],
                         "immediate_pursuit_documented": branch["pursuit"]})
    for name, rows in (("native.jsonl", native), ("video_frames.jsonl", mapping),
                       ("dispatch.jsonl", dispatch)):
        write_rows(base / name, rows)
    return [base / item for item in ("config.json", "native.jsonl",
                                      "video_frames.jsonl", "dispatch.jsonl")]


def run():
    ROOT.joinpath(".runtime-work").mkdir(exist_ok=True)
    positives, negatives = [], []
    with tempfile.TemporaryDirectory(dir=ROOT / ".runtime-work", prefix="c109028-") as folder:
        for case in ("probe_a", "probe_b"):
            base = Path(folder) / case
            base.mkdir()
            config, native, mapping, dispatch = make_source(base, case)
            result = measure(config, native, mapping, dispatch)
            if result["frames"] != 600 or result["siren_observed_frames"] != 200 or \
                    result["siren_outside_documented_response_frames"] != (0 if case == "probe_a" else 200):
                raise AssertionError("Controlled siren/dispatch contrast differs")
            positives.append(result)
            baseline = mapping.read_text()
            mapping.write_text(baseline.replace('"native_frame": 1000', '"native_frame": 999', 1))
            try:
                measure(config, native, mapping, dispatch)
            except ValueError as exc:
                if "join" not in str(exc):
                    raise
                negatives.append({"case": case, "mutation": "frame_join", "error": str(exc)})
            else:
                raise AssertionError("Altered frame join accepted")
            mapping.write_text(baseline)
            baseline = dispatch.read_text()
            dispatch.write_text(baseline.replace('"native_frame": 1000', '"native_frame": 999', 1))
            try:
                measure(config, native, mapping, dispatch)
            except ValueError as exc:
                if "join" not in str(exc):
                    raise
                negatives.append({"case": case, "mutation": "dispatch_join", "error": str(exc)})
            else:
                raise AssertionError("Altered dispatch join accepted")
    receipt = {"format": "c109028-source-measurement-proof-v1", "positives": positives,
               "negatives": negatives, "original_native_observed": False,
               "legal_verdict_claimed": False}
    (HERE / "source-proof.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return {"positives": len(positives), "negatives": len(negatives)}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
