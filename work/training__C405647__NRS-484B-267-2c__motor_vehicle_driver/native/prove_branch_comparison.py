"""Check fixed source conditions in both draft law-branch response pairs."""

import json
import os
from pathlib import Path
import shutil
import tempfile

from audit_comparison import audit
from branch_variants import RESPONSES, VARIANTS, variant_request
from measure_readiness import CAMERAS, measure


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def expect_rejection(roots, reports, variant, message):
    try:
        audit(roots, reports, variant)
    except ValueError as error:
        if message not in str(error):
            raise
    else:
        raise AssertionError("Changed branch source accepted: " + message)


def main():
    if ".runtime-work" not in Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).parts:
        raise ValueError("Export output root under .runtime-work before importing runtime")
    scratch = REPO / ".runtime-work"
    source = scratch / "C405647-readiness-proof"
    with tempfile.TemporaryDirectory(dir=scratch, prefix="c405647-branch-compare-") as temporary:
        work = Path(temporary)
        for variant in VARIANTS:
            roots, reports = {}, {}
            for response in RESPONSES:
                root = work / (variant + "__" + response)
                root.mkdir()
                roots[response] = root
                reports[response] = work / (variant + "__" + response + "-observed.json")
                for name in ("video_frames.jsonl", *(camera + ".mkv" for camera in CAMERAS)):
                    shutil.copyfile(source / name, root / name)
                review = json.loads((source / "emergency_review.json").read_text())
                review["officer_direction_present"] = variant == "officer_directed_otherwise"
                if variant == "visible_driver_hand_signal":
                    review.update({"source_driver_identity": "same_emergency_vehicle_driver",
                                   "source_driver_identity_source": "synthetic_fixture_only",
                                   "hand_signal_source": "synthetic_fixture_only"})
                else:
                    review.update({"officer_identity": "law_enforcement_officer",
                                   "officer_identity_source": "synthetic_fixture_only",
                                   "officer_direction_source": "synthetic_fixture_only",
                                   "officer_direction_applies_to_ego": True})
                write_json(root / "emergency_review.json", review)
                rows = [json.loads(line) for line in
                        (source / "approach_trace.jsonl").read_text().splitlines()]
                for index, row in enumerate(rows):
                    row["ego_brake"] = .8 if response == RESPONSES[0] and index >= 180 else 0.0
                    if response == RESPONSES[1] and index > 150:
                        row["ego_speed_mps"] = 5.5
                    if variant == "visible_driver_hand_signal":
                        row["emergency_speed_mps"] = 0.0 if index < 240 else .5
                        row["emergency_motion_visible"] = index >= 240
                        row["hand_signal_visible"] = 150 <= index <= 199
                write_rows(root / "approach_trace.jsonl", rows)
                write_json(root / "native-request.json", variant_request(variant, response))
                write_json(reports[response], measure(root))
            positive = audit(roots, reports, variant)
            if positive["branch"] != variant or positive["physical_acceptance_claimed"]:
                raise AssertionError("Branch comparison made a false claim")
            negative = roots[RESPONSES[1]]
            path = negative / "approach_trace.jsonl"
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            rows[120]["emergency_speed_mps"] += .25
            write_rows(path, rows)
            write_json(reports[RESPONSES[1]], measure(negative))
            expect_rejection(roots, reports, variant, "changed emergency trajectory")
            rows[120]["emergency_speed_mps"] -= .25
            write_rows(path, rows)
            write_json(reports[RESPONSES[1]], measure(negative))
            wrong = variant_request(variant, RESPONSES[1])
            wrong["case_id"] = "wrong-case"
            write_json(negative / "native-request.json", wrong)
            expect_rejection(roots, reports, variant, "differs from exact construction")
    print(json.dumps({"passed": True, "branch_pairs": 2,
                      "changed_source_rejections": 2,
                      "wrong_request_rejections": 2,
                      "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
