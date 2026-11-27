"""Prove fourteen 600-frame source joins and missing-source rejection in scratch."""

import copy
import hashlib
import json
import tempfile
from pathlib import Path

from saved_hydrant import ASSIGNMENT, FT_PER_M, join

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def write_rows(path, values):
    path.write_text("".join(json.dumps(value, separators=(",", ":")) + "\n"
                            for value in values))


def fixture(folder, config):
    survey = {"source_kind": "synthetic_native_sample",
              "map_name": "synthetic_hydrant_geometry",
              "premises_access_source": "synthetic_public_access_declaration",
              "parking_permission_source": "synthetic_parking_permission_declaration",
              "parking_permission": config["parking_permission"],
              "hydrant_identity_source": "synthetic_hydrant_inventory",
              "hydrant_xyz_m": [0, 0, 0], "distance_uncertainty_ft": 0.1}
    (folder / "hydrant_survey.json").write_text(json.dumps(survey) + "\n")
    target = config["requested_clearance_ft"]
    x = 2 + target / FT_PER_M
    trace, mapping = [], []
    for frame in range(600):
        native = frame + 1500
        trace.append({"source_kind": "synthetic_native_sample",
                      "frame": frame, "native_frame": native,
                      "video_frame": frame, "time_s": frame / 20,
                      "ego_actor_id": 1, "hydrant_actor_id": 2,
                      "ego_xyz_m": [x, 0, 0],
                      "ego_extent_xyz_m": [2, 1, 0.8], "ego_yaw_deg": 0,
                      "ego_speed_mps": 0,
                      "hydrant_xyz_m": survey["hydrant_xyz_m"],
                      "parking_permission_source": survey["parking_permission_source"],
                      "hydrant_identity_source": survey["hydrant_identity_source"],
                      "exception_context": config["exception_context"],
                      "exception_source_verified": False})
        mapping.append({"video_frame": frame, "native_frame": native,
                        "carla_frame": native, "time_s": frame / 20})
    write_rows(folder / "hydrant-trace.jsonl", trace)
    write_rows(folder / "video_frames.jsonl", mapping)
    return survey, trace, mapping


def reject(folder, config, file, mutate, expected):
    path = folder / file
    prior = path.read_text()
    data = json.loads(prior) if file.endswith(".json") else [
        json.loads(line) for line in prior.splitlines()]
    mutate(data)
    if data is None:
        path.unlink()
    else:
        path.write_text(json.dumps(data) + "\n" if file.endswith(".json") else
                        "".join(json.dumps(row) + "\n" for row in data))
    try:
        join(folder, config, allow_fixture=True)
    except ValueError as error:
        assert expected in str(error), str(error)
        outcome = str(error)
    else:
        raise AssertionError("Invalid source accepted: " + expected)
    finally:
        path.write_text(prior)
    return outcome


def main():
    plan = json.loads((HERE.parent / "case-plan.json").read_text())
    summary = {}
    with tempfile.TemporaryDirectory(dir=ROOT / ".runtime-work",
                                     prefix="c200568-saved-") as temporary:
        scratch = Path(temporary)
        for case in plan["cases"]:
            case_id = case["case_id"]
            suffix = case_id.split("__")[-1]
            construction = json.loads((HERE / ("selected-" + suffix + "-construction.json")).read_text())
            config = json.loads(next(row["content"] for row in construction["files"]
                                     if row["path"] == "config.json"))
            folder = scratch / suffix
            folder.mkdir()
            survey, trace, mapping = fixture(folder, config)
            value = join(folder, config, allow_fixture=True)
            assert value["frames"] == 600 and value["requested_target_confirmed"]
            assert value["original_native_observed"] is False
            expected = 15 if config["parking_permission"] == "parallel_permitted" else 20
            assert value["applicable_threshold_ft"] == expected
            summary[suffix] = {"relation": value["threshold_relation"],
                               "threshold_ft": expected,
                               "distance_ft": value["closest_footprint_distance_ft"],
                               "source_hashes": value["source_hashes"]}
            if suffix == "witness_2":
                negatives = {}
                path = folder / "hydrant_survey.json"
                prior = path.read_text()
                path.unlink()
                try:
                    join(folder, config, allow_fixture=True)
                except ValueError as error:
                    assert "Missing required source" in str(error)
                    negatives["missing_survey"] = str(error)
                else:
                    raise AssertionError("Missing survey accepted")
                path.write_text(prior)
                negatives["permission_provenance"] = reject(folder, config,
                    "hydrant_survey.json", lambda x: x.pop("parking_permission_source"),
                    "Original parking permission")
                negatives["frame_join"] = reject(folder, config,
                    "video_frames.jsonl", lambda x: x[35].update(native_frame=999),
                    "Original Native, video")
                negatives["body_extent"] = reject(folder, config,
                    "hydrant-trace.jsonl", lambda x: x[35].pop("ego_extent_xyz_m"),
                    "Vehicle body extent")
                negatives["exception_inference"] = reject(folder, config,
                    "hydrant-trace.jsonl", lambda x: x[35].update(exception_source_verified=True),
                    "Exception context")
    result = {"format": "worker-hydrant-saved-join-proof-v1", "passed": True,
              "cases": summary, "negative_rejections": negatives,
              "source_kind": "synthetic_native_sample",
              "original_native_observed": False, "legal_verdict": None}
    proof = HERE / "saved-join-proof.json"
    proof.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"cases": len(summary), "negative_rejections": len(negatives),
                      "proof_sha256": hashlib.sha256(proof.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
