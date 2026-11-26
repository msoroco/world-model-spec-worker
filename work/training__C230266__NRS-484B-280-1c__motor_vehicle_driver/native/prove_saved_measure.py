"""Exercise saved-source joins without claiming original motion or perception."""

import copy
import hashlib
import json
import os
from pathlib import Path

from branch_meter import BRANCH_SOURCES
from prove_branch_constructions import synthetic_survey
from prove_branch_meter import packet as synthetic_packet
from saved_measure import reviewed_measurement


HERE = Path(__file__).resolve().parent
BRANCHES = tuple(BRANCH_SOURCES)


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def rejected(function, phrase):
    try:
        function()
    except ValueError as exc:
        assert phrase in str(exc), (phrase, str(exc))
        return str(exc)
    raise AssertionError("Missing expected rejection: " + phrase)


def fixture(folder, branch):
    folder.mkdir(parents=True, exist_ok=True)
    survey = synthetic_survey(branch, BRANCH_SOURCES[branch])
    survey_path = folder / "context-survey.json"
    survey_path.write_text(json.dumps(survey, sort_keys=True) + "\n")
    survey_hash = hashlib.sha256(survey_path.read_bytes()).hexdigest()
    trace = copy.deepcopy(synthetic_packet(branch)["trace"])
    for row in trace:
        row.update(source_kind="synthetic_capture_fixture", branch=branch,
                   ego_actor_id=101, pedestrian_actor_id=102,
                   context_survey_sha256=survey_hash,
                   line_of_sight_clear=None, branch_position_evidenced=None,
                   driver_observed_pedestrian=None, driver_observation_source=None)
    write_rows(folder / "pedestrian-caution-trace.jsonl", trace)
    review = [{"source_kind": "original_saved_source_review", "frame": n,
               "native_frame": row["native_frame"], "video_frame": n,
               "context_survey_sha256": survey_hash,
               "line_of_sight_clear": n >= 50,
               "branch_position_evidenced": n >= 30,
               "driver_observed_pedestrian": None,
               "driver_observation_source": None} for n, row in enumerate(trace)]
    write_rows(folder / "pedestrian-source-review.jsonl", review)
    return review


def main():
    scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) / "saved-source-proof"
    scratch.mkdir(parents=True, exist_ok=True)
    positives, negatives = {}, {}
    for branch in BRANCHES:
        folder = scratch / branch
        review = fixture(folder, branch)
        result = reviewed_measurement(folder, branch, "101", "102")
        measured = result["measurement"]
        assert measured["branch"] == branch and measured["frames"] == 600
        assert measured["actual_driver_observation_unverified"]
        positives[branch] = {"frames": 600, "actual_observation_unverified": True,
                             "source_count": len(result["sources"])}
        (folder / "pedestrian-source-review.jsonl").unlink()
        negatives[branch + "_missing_review"] = rejected(
            lambda: reviewed_measurement(folder, branch, "101", "102"),
            "Missing required source: pedestrian-source-review.jsonl")
        write_rows(folder / "pedestrian-source-review.jsonl", review)
        if branch == "road":
            broken = copy.deepcopy(review)
            broken[0]["native_frame"] += 1
            write_rows(folder / "pedestrian-source-review.jsonl", broken)
            negatives["bad_join"] = rejected(
                lambda: reviewed_measurement(folder, branch, "101", "102"),
                "Capture/review frame join failed")
            broken = copy.deepcopy(review)
            broken[100]["driver_observed_pedestrian"] = True
            write_rows(folder / "pedestrian-source-review.jsonl", broken)
            negatives["unsupported_observation"] = rejected(
                lambda: reviewed_measurement(folder, branch, "101", "102"),
                "Actual observation provenance missing")
    proof = {"format": "worker-nrs280-saved-source-cpu-proof-v1",
             "positive": positives, "negative_rejections": negatives,
             "positive_count": len(positives), "negative_count": len(negatives),
             "diagnostic_fixture": True, "physical_execution_proven": False,
             "legal_verdict": None}
    path = HERE / "saved-source-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"positive": len(positives), "negative": len(negatives),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
