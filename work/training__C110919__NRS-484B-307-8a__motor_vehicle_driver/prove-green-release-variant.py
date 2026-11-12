"""CPU proof for two right-turn releases after the same red-signal halt.

Reuses marked-reference synthetic motion only as diagnostic source rows. No
original Native action or accepted recording is inferred from this proof.
"""
import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
NATIVE = HERE / "native"
sys.path.insert(0, str(NATIVE))
from engineering import CANDIDATES, parameters
from runner import check as runner_check
from variant_geometry import check_for

spec = importlib.util.spec_from_file_location("c110919_green_finalize", NATIVE / "finalize.py")
finalize = importlib.util.module_from_spec(spec)
spec.loader.exec_module(finalize)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reject(action):
    try:
        action()
    except ValueError:
        return
    raise AssertionError("Damaged green-release evidence was accepted")


def main():
    template = json.loads((NATIVE / "config.json").read_text())
    baseline = json.loads((HERE / "update015-reference-diagnostic.json").read_text())
    source = [json.loads(line) for line in baseline["files"]["native_samples.jsonl"].splitlines()]
    assert len(source) == 480 and all(row.get("synthetic_diagnostic") is True for row in source)
    summary = {}
    with tempfile.TemporaryDirectory(prefix="c110919-green-release-") as temp:
        attempt = Path(temp)
        geometry = json.loads(baseline["files"]["road_geometry.json"])
        (attempt / "road_geometry.json").write_text(json.dumps(geometry) + "\n")
        for suffix in ("green_release_wait", "green_release_red_turn"):
            geom = check_for(suffix)
            assert geom["stopping_reference_kind"] == "marked_stop_line"
            assert geom["stopping_reference_y_m"] == -14.0
            checked = []
            for candidate in CANDIDATES:
                config = copy.deepcopy(template)
                config.update(case_id=HERE.name + "__" + suffix, case_suffix=suffix,
                              candidate_id=candidate, knobs=parameters(suffix, candidate)["knobs"])
                result = runner_check(config)
                assert result["camera_count"] == 4 and result["native_imported"] is False
                checked.append(candidate)
            wait = suffix == "green_release_wait"
            samples = []
            for i in range(480):
                motion = source[min(i, 129) if wait and i <= 160 else
                                i - 31 if wait and i > 160 else i]
                row = copy.deepcopy(motion)
                row["native_frame"] = source[i]["native_frame"]
                row["time_s"] = source[i]["time_s"]
                row["walker_center_xy_m"] = source[i]["walker_center_xy_m"]
                row["walker_conflict_occupied"] = source[i]["walker_conflict_occupied"]
                row["signal_state_observed"] = "Red" if i < 160 else "Green"
                if wait and 130 <= i <= 160:
                    row["speed_mps"] = 0.0
                samples.append(row)
            (attempt / "native_samples.jsonl").write_text(
                "".join(json.dumps(row, allow_nan=False) + "\n" for row in samples))
            signal = finalize.measure_signal(attempt, samples, geometry, suffix)
            stop = finalize.measure_stop(attempt, samples, geometry)
            release = finalize.measure_green_release(attempt, samples, signal, stop)
            actual = release["value"]
            assert actual["remain_stopped_until_green"] is wait
            assert actual["first_green_frame"] == 160
            assert actual["stationary_pre_crossing_frames"] >= 30
            assert actual["first_front_crossing_frame"] >= 160 if wait else actual["first_front_crossing_frame"] < 160
            damaged = copy.deepcopy(samples)
            damaged[159]["signal_state_observed"] = "Green"
            reject(lambda: finalize.measure_signal(attempt, damaged, geometry, suffix))
            damaged = copy.deepcopy(samples)
            damaged[160]["signal_state_observed"] = "Red"
            reject(lambda: finalize.measure_signal(attempt, damaged, geometry, suffix))
            reject(lambda: finalize.measure_signal(attempt, samples, geometry, "reference"))
            summary[suffix] = {"candidates_checked": checked, **actual,
                               "synthetic_source_only": True,
                               "original_native_accepted": False}
    proof = {"format": "c110919-green-release-variant-cpu-proof-v1",
             "source_sha256": sha(HERE / "update015-reference-diagnostic.json"),
             "runner_sha256": sha(NATIVE / "runner.py"),
             "finalizer_sha256": sha(NATIVE / "finalize.py"),
             "engineering_sha256": sha(NATIVE / "engineering.py"),
             "cases": summary, "physical_motion_verified": False,
             "original_recordings_accepted": 0}
    path = HERE / "update026-green-release-variant-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"cases": 2, "candidate_checks": 8,
                      "release": {key: value["remain_stopped_until_green"] for key, value in summary.items()},
                      "proof_sha256": sha(path)}))


if __name__ == "__main__":
    main()
