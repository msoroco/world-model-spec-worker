"""Exercise all four draft branch finalizers with synthetic saved sources."""

import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from branch_variants import RESPONSES, VARIANTS, variant_request
from finalize import finalize
from measure_readiness import CAMERAS


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def source_rows(source, attempt, variant, response):
    rows = [json.loads(line) for line in (source / "approach_trace.jsonl").read_text().splitlines()]
    for index, row in enumerate(rows):
        if variant == "visible_driver_hand_signal":
            row["emergency_speed_mps"] = 0.0 if index < 240 else 0.5
            row["emergency_motion_visible"] = False if index < 240 else True
            row["hand_signal_visible"] = 150 <= index <= 199
        if response == "not_available":
            row["ego_brake"] = 0.0
            row["ego_speed_mps"] = 15.0
    (attempt / "approach_trace.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows))
    shutil.copyfile(attempt / "approach_trace.jsonl", attempt / "trace.jsonl")


def main():
    if ".runtime-work" not in Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).parts:
        raise ValueError("Export output root under .runtime-work before importing runtime")
    sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
    scratch = REPO / ".runtime-work"
    source = scratch / "C405647-readiness-proof"
    count = 0
    with tempfile.TemporaryDirectory(dir=scratch, prefix="c405647-branch-finalize-") as root:
        for variant in VARIANTS:
            for response in RESPONSES:
                exact = variant_request(variant, response)
                case_key = variant + "__" + response
                attempt = Path(root) / case_key
                attempt.mkdir()
                construction = json.loads((HERE / "branch-constructions" /
                                           (case_key + ".json")).read_text())
                files = {item["path"]: item["content"] for item in construction["files"]}
                write_json(attempt / "config.json", json.loads(files["config.json"]))
                write_json(attempt / "construction.json", construction)
                write_json(attempt / "native-request.json", exact)
                for name in ("video_frames.jsonl", "emergency_review.json",
                             *(camera + ".mkv" for camera in CAMERAS)):
                    shutil.copyfile(source / name, attempt / name)
                review = json.loads((attempt / "emergency_review.json").read_text())
                review["officer_direction_present"] = variant == "officer_directed_otherwise"
                if variant == "visible_driver_hand_signal":
                    review["hand_signal_source"] = "synthetic_fixture_only"
                write_json(attempt / "emergency_review.json", review)
                source_rows(source, attempt, variant, response)
                output = attempt / "saved-analysis.json"
                wrong = dict(exact, case_id="wrong-case")
                write_json(attempt / "native-request.json", wrong)
                try:
                    finalize(attempt, output)
                except ValueError as exc:
                    if "Exact saved case or candidate differs" not in str(exc):
                        raise
                else:
                    raise AssertionError("Wrong branch request accepted")
                write_json(attempt / "native-request.json", exact)
                report = finalize(attempt, output)
                result = json.loads((attempt / "result.json").read_text())
                if (report["case_id"] != exact["case_id"] or
                        result["case_id"] != exact["case_id"] or
                        report["physical_acceptance_claimed"] or
                        report["legal_verdict_claimed"] or
                        result["accepted"] or
                        len(list((attempt / "channels").glob("*.jsonl"))) != 6):
                    raise AssertionError("Branch saved result lost exact binding or claimed acceptance")
                count += 1
    print(json.dumps({"passed": True, "synthetic_branch_cases": count,
                      "wrong_request_rejections": count,
                      "physical_acceptance_claimed": False,
                      "legal_verdict_claimed": False}))


if __name__ == "__main__":
    main()
