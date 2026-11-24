"""Exercise retained-source stop measurements; generated traces are diagnostics only."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

from measure import measure

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ASSIGNMENT = HERE.parent.name
FRAMES = 600
RATE = 20


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def make_sources(directory, case_suffix, halt, reference):
    directory.mkdir(parents=True, exist_ok=True)
    config = json.loads((HERE / "config.json").read_text())
    config["case_id"] = ASSIGNMENT + "__" + case_suffix
    config_path = directory / "config.json"
    write_json(config_path, config)
    geometry = {"source_kind": "synthetic_native_sample", "lane_enters_intersection": True,
                "signal_head_faces_subject": True, "flashing_red_source": "synthetic_native_sample",
                "limit_line_x_m": 48.0 if reference == "limit_line" else None,
                "crosswalk_near_x_m": 50.0 if reference != "intersection" else None,
                "intersection_near_x_m": 52.0}
    geometry_path = directory / "geometry.json"
    write_json(geometry_path, geometry)
    native_path, frame_path = directory / "native.jsonl", directory / "frame-map.jsonl"
    x = 0.0
    with native_path.open("w") as nout, frame_path.open("w") as fout:
        for i in range(FRAMES):
            # The stopped case holds immediately before the first marked reference.
            waiting = halt and 176 <= i < 216
            speed = 0.0 if waiting else 5.0
            x += speed / RATE
            source = {"source_kind": "synthetic_native_sample", "native_frame": 1000 + i,
                      "time_s": (i + 1) / RATE, "front_x_m": round(x, 6), "speed_mps": speed,
                      "flashing_red_observed": True, "signal_faces_ego_observed": True,
                      "conflict_occupied": 170 <= i < 190}
            frame = {"video_frame": i, "native_frame": 1000 + i,
                     "time_s": (i + 1) / RATE}
            nout.write(json.dumps(source, sort_keys=True) + "\n")
            fout.write(json.dumps(frame, sort_keys=True) + "\n")
    return [config_path, native_path, frame_path, geometry_path]


def rejects(paths, expected):
    try:
        measure(*paths)
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError(f"Expected {expected!r}, got {error!r}") from error
        return str(error)
    raise AssertionError("Damaged retained source was accepted")


def run():
    scratch = ROOT / ".runtime-work" / "c111271-source-measurement"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    observations = {}
    for ref in ("limit_line", "crosswalk", "intersection"):
        for suffix, halt in (("probe_a", True), ("probe_b", False)):
            paths = make_sources(scratch / ref / suffix, suffix, halt, ref)
            result = measure(*paths)
            if result["frames"] != FRAMES or result["stopping_reference"] != ref:
                raise AssertionError("Reference hierarchy or frame count differs")
            if result["conflict_occupied_after_crossing_frames"]:
                raise AssertionError("Comparison controls changed conflict occupancy at crossing")
            if halt:
                if result["longest_pre_reference_halt_frames"] != 40:
                    raise AssertionError("The controlled stop was not measured")
            elif result["longest_pre_reference_halt_frames"] != 0:
                raise AssertionError("Nonstop control acquired a false halt")
            observations[f"{ref}/{suffix}"] = result
    positive = list(make_sources(scratch / "negative-base", "probe_a", True, "limit_line"))
    missing = scratch / "negative-base" / "missing-native.jsonl"
    bad = list(positive)
    bad[1] = missing
    negative = {"missing_source": rejects(bad, "Missing retained source")}
    frame_lines = positive[2].read_text().splitlines()
    altered = [json.loads(line) for line in frame_lines]
    altered[200]["native_frame"] += 1
    positive[2].write_text("\n".join(json.dumps(row, sort_keys=True) for row in altered) + "\n")
    negative["frame_join"] = rejects(positive, "Native/video frame-time join differs")
    positive = list(make_sources(scratch / "negative-base", "probe_a", True, "limit_line"))
    native_lines = positive[1].read_text().splitlines()
    altered = [json.loads(line) for line in native_lines]
    altered[200]["flashing_red_observed"] = False
    positive[1].write_text("\n".join(json.dumps(row, sort_keys=True) for row in altered) + "\n")
    negative["missing_flashing_phase"] = rejects(positive, "Facing flashing-red source incomplete")
    positive = list(make_sources(scratch / "negative-base", "probe_a", True, "limit_line"))
    native_lines = positive[1].read_text().splitlines()
    altered = [json.loads(line) for line in native_lines]
    altered[200]["front_x_m"] = -99
    positive[1].write_text("\n".join(json.dumps(row, sort_keys=True) for row in altered) + "\n")
    negative["body_discontinuity"] = rejects(positive, "Native body motion differs")
    return {"format": "c111271-source-measurement-diagnostic-v1", "passed": True,
            "assignment_id": ASSIGNMENT, "synthetic_only": True,
            "original_native_verified": False, "physical_legal_verdict": None,
            "positive_checks": observations, "negative_checks": negative,
            "measure_sha256": sha(HERE / "measure.py"),
            "script_sha256": sha(HERE / "prove_source_measurement.py")}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--proof", type=Path, required=True)
    args = parser.parse_args()
    proof = run()
    write_json(args.proof, proof)
    print(json.dumps({"passed": True, "positive": len(proof["positive_checks"]),
                      "negative": len(proof["negative_checks"]),
                      "proof_sha256": sha(args.proof)}, sort_keys=True))


if __name__ == "__main__":
    main()
