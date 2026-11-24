"""Exercise three exact comparisons and rejection paths on CPU diagnostics."""

import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKAGE))
from comparison_audit import CAMERAS, PAIRS, audit


def fixture(kind, destination):
    source = ROOT / ".runtime-work" / ("c158208-compatibility-" + kind + "-v4")
    destination.mkdir()
    for name in ("config.json", "analysis-report.json", "entry_history.jsonl",
                 "video_frames.jsonl", "intersection_context.json", "site_review.json", "road.xodr"):
        shutil.copy2(source / name, destination / name)
    for name in CAMERAS:
        (destination / name).symlink_to((source / name).resolve())


def rejected(left, right, comparison, fragment):
    try:
        audit((left, right), comparison, diagnostic_fixture=True)
    except ValueError as error:
        if fragment not in str(error):
            raise ValueError("Wrong comparison rejection: " + str(error)) from error
        return
    raise ValueError("Changed comparison source was accepted")


def main():
    scratch = ROOT / ".runtime-work"
    scratch.mkdir(exist_ok=True)
    results = []
    with tempfile.TemporaryDirectory(dir=scratch, prefix="c158208-comparison-") as directory:
        temp = Path(directory)
        for comparison, (first, second) in PAIRS.items():
            left, right = temp / (comparison + "-left"), temp / (comparison + "-right")
            fixture(first, left)
            fixture(second, right)
            result = audit((left, right), comparison, diagnostic_fixture=True)
            if result["physical_acceptance_claimed"] is not False:
                raise ValueError("Diagnostic comparison asserted physical acceptance")
            results.append({"comparison_id": comparison, "passed": True,
                            "analysis_sha256": result["analysis_sha256"]})
            try:
                audit((left, right), comparison)
            except ValueError as error:
                if "600-frame" not in str(error):
                    raise
            else:
                raise ValueError("Three-frame CPU diagnostic passed physical comparison gate")
            if comparison == "other_obligation":
                path = right / "config.json"
                config = json.loads(path.read_text())
                config["rate_hz"] = 10
                path.write_text(json.dumps(config) + "\n")
                rejected(left, right, comparison, "rate_hz")
            elif comparison == "other_presence":
                path = right / "analysis-report.json"
                report = json.loads(path.read_text())
                report["raw_observations"]["other_inside_at_ego_entry"] = True
                path.write_text(json.dumps(report) + "\n")
                rejected(left, right, comparison, "occupancy")
            else:
                path = right / "overview.mkv"
                path.unlink()
                path.write_text("changed diagnostic camera\n")
                rejected(left, right, comparison, "source hash changed")
    output = {"format": "c158208-comparison-cpu-check", "comparisons": results,
              "physical_acceptance_claimed": False}
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
