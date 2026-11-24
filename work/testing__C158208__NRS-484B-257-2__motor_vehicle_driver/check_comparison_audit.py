"""Exercise three exact comparisons and rejection paths on CPU diagnostics."""

import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKAGE))
from comparison_audit import CAMERAS, PAIRS, audit, sha
from check_source_fixture import build


def fixture(source, destination):
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
        sources = {kind: build(kind, temp / ("source-" + kind))
                   for kind in {name for pair in PAIRS.values() for name in pair}}
        for comparison, (first, second) in PAIRS.items():
            left, right = temp / (comparison + "-left"), temp / (comparison + "-right")
            fixture(sources[first], left)
            fixture(sources[second], right)
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
                rejected(left, right, comparison, "other_inside_at_ego_entry")
            else:
                independent = temp / "independent-camera-right"
                fixture(sources[second], independent)
                camera = independent / "overview.mkv"
                camera.unlink()
                camera.write_bytes((sources[second] / "overview.mkv").read_bytes() + b"independent diagnostic pixels")
                review_path = independent / "site_review.json"
                review = json.loads(review_path.read_text())
                review["camera_sha256"]["overview"] = sha(camera)
                review_path.write_text(json.dumps(review) + "\n")
                report_path = independent / "analysis-report.json"
                report = json.loads(report_path.read_text())
                report["raw_observations"]["sources"]["overview.mkv"] = sha(camera)
                report["raw_observations"]["sources"]["site_review.json"] = sha(review_path)
                report_path.write_text(json.dumps(report) + "\n")
                audit((left, independent), comparison, diagnostic_fixture=True)
                history_path = independent / "entry_history.jsonl"
                frame_path = independent / "video_frames.jsonl"
                history = [json.loads(line) for line in history_path.read_text().splitlines()]
                frames = [json.loads(line) for line in frame_path.read_text().splitlines()]
                for row in history:
                    row["frame"] += 1000
                for row in frames:
                    row["carla_frame"] += 1000
                    row["camera_frame_ids"] = {name: value + 1000
                                               for name, value in row["camera_frame_ids"].items()}
                history_path.write_text("".join(json.dumps(row) + "\n" for row in history))
                frame_path.write_text("".join(json.dumps(row) + "\n" for row in frames))
                review["reviewed_carla_frames"] = [row["carla_frame"] for row in frames]
                review_path.write_text(json.dumps(review) + "\n")
                report["raw_observations"]["first_ego_entry"]["frame"] += 1000
                for row in report["raw_observations"]["samples"]:
                    row["frame"] += 1000
                for name, path in (("entry_history.jsonl", history_path),
                                   ("video_frames.jsonl", frame_path),
                                   ("site_review.json", review_path)):
                    report["raw_observations"]["sources"][name] = sha(path)
                report_path.write_text(json.dumps(report) + "\n")
                audit((left, independent), comparison, diagnostic_fixture=True)
                path = right / "overview.mkv"
                path.unlink()
                path.write_text("changed diagnostic camera\n")
                rejected(left, right, comparison, "source hash changed")
    output = {"format": "c158208-comparison-cpu-check", "comparisons": results,
              "physical_acceptance_claimed": False}
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
