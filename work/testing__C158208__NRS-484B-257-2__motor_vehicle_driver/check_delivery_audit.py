"""Run the independent delivery-source audit against five CPU fixtures."""

import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKAGE))
from delivery_audit import CAMERAS, KINDS, PREFIX, audit
from check_source_fixture import build


def expect_rejection(root, case, fragment, *, diagnostic_fixture=True):
    try:
        audit(root, case, diagnostic_fixture=diagnostic_fixture)
    except ValueError as error:
        if fragment not in str(error):
            raise ValueError("Wrong delivery rejection: " + str(error)) from error
        return
    raise ValueError("Invalid delivery source was accepted: " + fragment)


def copy_fixture(source, target):
    target.mkdir()
    for name in ("config.json", "result.json", "analysis-report.json", "entry_history.jsonl",
                 "video_frames.jsonl", "intersection_context.json", "site_review.json"):
        shutil.copy2(source / name, target / name)
    if (source / "officer_review.json").is_file():
        shutil.copy2(source / "officer_review.json", target / "officer_review.json")
    for name in CAMERAS:
        (target / (name + ".mkv")).symlink_to((source / (name + ".mkv")).resolve())


def main():
    scratch = ROOT / ".runtime-work"
    scratch.mkdir(exist_ok=True)
    passed = []
    with tempfile.TemporaryDirectory(dir=scratch, prefix="c158208-delivery-") as directory:
        temp = Path(directory)
        for kind in sorted(KINDS):
            case = PREFIX + kind
            source = build(kind, temp / ("source-" + kind))
            target = temp / kind
            copy_fixture(source, target)
            result = audit(target, case, diagnostic_fixture=True)
            if (result["original_frames"] != 3 or result["physical_acceptance_claimed"] is not False):
                raise ValueError("Diagnostic audit made an acceptance claim")
            expect_rejection(target, case, "600-frame", diagnostic_fixture=False)
            passed.append({"case_id": case, "software_source_audit_passed": True,
                           "full_camera_decodes": 4, "physical_acceptance_claimed": False})
            if kind == "yield_other_inside":
                path = target / "entry_history.jsonl"
                path.write_text(path.read_text() + "{}\n")
                expect_rejection(target, case, "Original analysis source changed: entry_history.jsonl")
            if kind == "yield_other_approaching":
                path = target / "video_frames.jsonl"
                path.write_text(path.read_text().replace('"video_frame": 1', '"video_frame": 9'))
                expect_rejection(target, case, "Original analysis source changed: video_frames.jsonl")
            if kind == "yield_no_slow":
                path = target / "overview.mkv"
                path.unlink()
                path.write_text("changed synthetic camera\n")
                expect_rejection(target, case, "Original analysis source changed: overview.mkv")
            if kind == "officer_control_exception":
                (target / "officer_review.json").unlink()
                expect_rejection(target, case, "Missing original source: officer_review.json")
    print(json.dumps({"format": "c158208-delivery-source-cpu-check", "cases": passed},
                     sort_keys=True))


if __name__ == "__main__":
    main()
