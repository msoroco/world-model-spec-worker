"""Independent beam-only contrast positive and changed-fixed-source negative."""
import json
import os
from pathlib import Path
import runpy
import shutil

from compare_beam import compare
from saved_beam import load_rows, sha


def reject(action, phrase):
    try:
        action()
    except ValueError as error:
        assert phrase in str(error), str(error)
    else:
        raise AssertionError("expected rejection: " + phrase)


here = Path(__file__).resolve().parent
runpy.run_path(str(here / "prove_saved_beam.py"))
scratch = Path(os.environ["TMPDIR"]).resolve()
a = scratch / "saved-beam-proof"
b = scratch / "comparison-high"
if b.exists():
    shutil.rmtree(b)
frames = load_rows(a / "video_frames.jsonl")
frames[10]["native_frame"] = 1010
(a / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in frames))
context = json.loads((a / "beam-context.json").read_text())
context["source_sha256"]["video_frames.jsonl"] = sha(a / "video_frames.jsonl")
(a / "beam-context.json").write_text(json.dumps(context) + "\n")
shutil.copytree(a, b)
rows = load_rows(b / "beam-rows.jsonl")
for row in rows:
    row["requested_beam_state"] = "high_beam"
(b / "beam-rows.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
context["case_id"] = context["case_id"].replace("__condition_a", "__condition_b")
context["source_sha256"]["beam-rows.jsonl"] = sha(b / "beam-rows.jsonl")
(b / "config.json").write_text(json.dumps({"selected_case_id": context["case_id"]}) + "\n")
(b / "beam-context.json").write_text(json.dumps(context) + "\n")
result = compare(a, b)
assert result["contrasting_within_500_feet_frames"] > 0
assert result["physical_glare_conclusion"] is None
road = b / "road.xodr"
road.write_text(road.read_text().replace('183394', '999999'))
context["source_sha256"]["road.xodr"] = sha(road)
(b / "beam-context.json").write_text(json.dumps(context) + "\n")
reject(lambda: compare(a, b), "fixed source differs")
print("PASS: 600-frame beam-only contrast and changed-road negative")
