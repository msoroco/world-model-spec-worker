"""Bounded CPU physical checks; original Native realization remains unverified."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "native"))
from finalize import analyze
from measure_fixture import measure
from source_review import reviewed_context


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def main(attempts):
    result = {}
    for suffix, path in attempts.items():
        data = analyze(path)
        value = data["measurement"]
        if value["rest_interval_frames"] != [100, 599]:
            raise ValueError("Diagnostic rest interval differs")
        if value["within_five_foot_side_band_at_rest"] != (suffix in
                ("probe_2", "probe_4", "probe_5", "probe_6")):
            raise ValueError("Diagnostic side clearance differs")
        if (value["directly_in_front_frame_count_at_rest"] >= 100) != (suffix == "probe_3"):
            raise ValueError("Diagnostic front placement differs")
        context = reviewed_context(path)
        rows = read_rows(Path(path) / "vehicle-poses.jsonl")
        bad_motion = [dict(row, observed_vehicle_speed_mps=3.0) for row in rows]
        try:
            measure(context, bad_motion)
        except ValueError as error:
            if "five-second stop" not in str(error):
                raise
        else:
            raise AssertionError("Continuous movement accepted as stop")
        try:
            measure(context, rows[:-1])
        except ValueError as error:
            if "Incomplete 30-second" not in str(error):
                raise
        else:
            raise AssertionError("Missing frame accepted")
        result[suffix] = {"diagnostic_fixture": True,
            "source_frames": 600, "rest_frames": 500,
            "side_band": value["within_five_foot_side_band_at_rest"],
            "direct_front": value["directly_in_front_frame_count_at_rest"] >= 100,
            "no_stop_rejected": True, "missing_frame_rejected": True,
            "original_native_observed": False,
            "physical_acceptance_claimed": False}
    proof = {"format": "c150668-cpu-physical-proof-v1", "passed": True,
             "cases": result,
             "lifecycle_order": ["capture_finished", "encoders_closed",
                "restoration_verified", "native_exit", "owner_released",
                "saved_processing_started"],
             "lifecycle_original_verified": False,
             "legal_verdict_claimed": False}
    (HERE / "physical-diagnostic.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"passed": True, "original_native_observed": False}))


if __name__ == "__main__":
    if len(sys.argv) != 7:
        raise SystemExit("Usage: prove_physical.py PROBE1_ATTEMPT ... PROBE6_ATTEMPT")
    main({"probe_" + str(i): sys.argv[i] for i in range(1, 7)})
