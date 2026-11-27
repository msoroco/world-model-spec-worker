"""Exercise four exact branch constructions against independent saved fixtures."""

import json
import os
from pathlib import Path
import shutil
import sys
import tempfile


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PACKAGE = HERE.parent


def main():
    scratch = REPO / ".runtime-work"
    output_root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if scratch not in output_root.parents:
        raise ValueError("Runtime output must stay under .runtime-work")
    sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
    from worker_exchange.fixture_recipe import materialize as fixture_materialize
    from worker_exchange.runtime_cli import materialize as case_materialize
    from worker_exchange.saved_processing import run as process_saved

    manifest = PACKAGE / "branch-native-manifest.json"
    entries = json.loads(manifest.read_text())["cases"]
    with tempfile.TemporaryDirectory(dir=scratch, prefix="c405647-branch-saved-") as temporary:
        work = Path(temporary)
        for entry in entries:
            case_id = entry["case_id"]
            label = case_id.split(PACKAGE.name + "__", 1)[1]
            fixture = work / (label + "-fixture")
            fixture_materialize(REPO, REPO / entry["fixture_recipe"], fixture)
            for negative in (False, True):
                suffix = "-negative" if negative else "-positive"
                attempt = work / (label + suffix + "-attempt")
                case_materialize(manifest, case_id, attempt, "primary")
                for source in fixture.iterdir():
                    if negative and source.name == "emergency_review.json":
                        continue
                    target = attempt / source.name
                    if target.exists():
                        raise ValueError("Fixture shadows construction: " + source.name)
                    if source.is_dir():
                        shutil.copytree(source, target)
                    else:
                        shutil.copyfile(source, target)
                before = {p.relative_to(attempt).as_posix(): p.read_bytes()
                          for p in attempt.rglob("*") if p.is_file()}
                output = work / (label + suffix + "-saved")
                receipt = process_saved(
                    manifest, case_id, attempt, output, REPO / "runtime/library",
                    REPO / ".runtime-work/c136495-5a-build/validator/.lake/build/bin/adapterCheck")
                after = {p.relative_to(attempt).as_posix(): p.read_bytes()
                         for p in attempt.rglob("*") if p.is_file()}
                if before != after or not receipt["passed"] or not receipt["recorded_only"] or not receipt["originals_preserved"]:
                    raise ValueError("Branch saved processing changed originals or failed")
                if negative:
                    feedback = json.loads((output / "v0001/feedback.json").read_text())
                    if (not receipt["missing_evidence"] or
                            feedback.get("classification") != "incomplete_or_unavailable_law_evidence" or
                            "Missing required source: emergency_review.json" not in feedback.get("error", "")):
                        raise ValueError("Missing branch source feedback absent")
                elif receipt["missing_evidence"] or not receipt["final_video_checks"]:
                    raise ValueError("Positive branch saved processing incomplete")
                print(label + suffix + ": saved sources preserved; " +
                      ("missing-source feedback passed" if negative else "selected analysis and final decode passed"), flush=True)


if __name__ == "__main__":
    main()
