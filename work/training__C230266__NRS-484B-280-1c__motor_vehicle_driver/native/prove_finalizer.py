"""CPU proof of the selected saved-only measurement boundary.

The source packets are synthetic. The proof checks software joins and negative
source handling; it does not claim physical, perceptual or legal success.
"""

import copy
import hashlib
import json
import os
from pathlib import Path

from branch_meter import BRANCH_SOURCES
from finalize import analysis_report
from prove_branch_constructions import synthetic_survey
from prove_branch_meter import packet as synthetic_packet


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def fixture(folder, branch, suffix):
    folder.mkdir(parents=True, exist_ok=True)
    survey = synthetic_survey(branch, BRANCH_SOURCES[branch])
    survey_path = folder / "context-survey.json"
    survey_path.write_text(json.dumps(survey, sort_keys=True) + "\n")
    source_hash = sha(survey_path)
    trace = copy.deepcopy(synthetic_packet(branch)["trace"])
    for row in trace:
        row.update(source_kind="synthetic_capture_fixture", branch=branch,
                   ego_actor_id=101, pedestrian_actor_id=102,
                   context_survey_sha256=source_hash,
                   line_of_sight_clear=None, branch_position_evidenced=None,
                   driver_observed_pedestrian=None, driver_observation_source=None)
    write_rows(folder / "pedestrian-caution-trace.jsonl", trace)
    review = [{"source_kind": "original_saved_source_review", "frame": n,
               "native_frame": row["native_frame"], "video_frame": n,
               "context_survey_sha256": source_hash,
               "line_of_sight_clear": n >= 50,
               "branch_position_evidenced": n >= 30,
               "driver_observed_pedestrian": None,
               "driver_observation_source": None} for n, row in enumerate(trace)]
    write_rows(folder / "pedestrian-source-review.jsonl", review)
    config = json.loads((HERE / "branch-cases" / suffix / "config.json").read_text())
    (folder / "config.json").write_text(json.dumps(config, sort_keys=True) + "\n")
    return review


def main():
    scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) / "finalizer-proof"
    scratch.mkdir(parents=True, exist_ok=True)
    positives, negatives = {}, {}
    for branch in BRANCH_SOURCES:
        suffix = "probe_1" if branch == "road" else branch + "_caution"
        folder = scratch / suffix
        review = fixture(folder, branch, suffix)
        report = analysis_report(folder)
        observed = report["measurements"]["caution_observation"]
        assert report["case_id"].endswith("__" + suffix)
        assert observed["value"]["branch"] == branch
        assert observed["value"]["actual_driver_observation_unverified"]
        assert set(observed["sources"]) == {
            "pedestrian-caution-trace.jsonl", "pedestrian-source-review.jsonl",
            "context-survey.json"}
        positives[branch] = {"case_id": report["case_id"], "frames": 600,
                             "legal_verdict_claimed": False}
        review_path = folder / "pedestrian-source-review.jsonl"
        review_path.unlink()
        try:
            analysis_report(folder)
        except ValueError as exc:
            assert str(exc) == "Missing required source: pedestrian-source-review.jsonl"
            negatives[branch + "_missing_source"] = str(exc)
        else:
            raise AssertionError("Missing review source was accepted")
        write_rows(review_path, review)
    proof = {"format": "worker-nrs280-finalizer-cpu-proof-v1",
             "positive": positives, "negative_rejections": negatives,
             "positive_count": len(positives), "negative_count": len(negatives),
             "diagnostic_fixture": True, "physical_execution_proven": False,
             "actual_driver_observation_proven": False,
             "legal_verdict": None}
    path = HERE / "finalizer-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"positive": len(positives), "negative": len(negatives),
                      "proof_sha256": sha(path)}))


if __name__ == "__main__":
    main()
