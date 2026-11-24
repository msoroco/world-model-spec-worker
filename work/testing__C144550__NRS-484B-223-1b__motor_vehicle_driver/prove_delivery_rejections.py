"""CPU-test independent delivery rejection of missing Native and altered actors."""

import json
import os
import shutil
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
output = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
if not output or not Path(output).resolve().is_relative_to(ROOT / ".runtime-work"):
    raise ValueError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
from delivery_acceptance import audit_sources, verify_review, verify_seal  # noqa: E402
from prove_delivery_acceptance import source_for  # noqa: E402


case = HERE.name + "__left_signal_before_clear_gap"
source = source_for("left_signal_before_clear_gap")
attempt = Path(output) / "delivery-rejections"
if attempt.exists():
    shutil.rmtree(attempt)
(attempt / "capture").mkdir(parents=True)
for name in ("result.json", "video_frames.jsonl", "lane_history.jsonl", "trace.jsonl",
             "capture/evidence.jsonl"):
    shutil.copyfile(source / name, attempt / name)
assert audit_sources(attempt, case)["original_frame_count"] == 900
rejected = []
for label, action, expected in (
    ("unsealed_native", lambda: verify_seal(attempt), "Missing original source: capture-seal.json"),
    ("missing_pixel_review", lambda: verify_review(source, case, attempt / "review.json", 900),
     "Missing original source: review.json"),
):
    try:
        action()
    except ValueError as error:
        if expected not in str(error):
            raise
        rejected.append(label)
    else:
        raise AssertionError("Delivery auditor accepted " + label)
history = attempt / "lane_history.jsonl"
lines = history.read_text().splitlines()
first = json.loads(lines[0])
first["ego_body_vertices_xy_m"] = []
lines[0] = json.dumps(first)
history.write_text("\n".join(lines) + "\n")
try:
    audit_sources(attempt, case)
except ValueError as error:
    if "Original ego or target body source missing" not in str(error):
        raise
    rejected.append("missing_ego_body")
else:
    raise AssertionError("Delivery auditor accepted missing ego body")
print(json.dumps({"diagnostic_fixture": True, "case_id": case,
                  "rejected": rejected, "native_or_pixel_acceptance_claimed": False}))
