"""Exercise the portable comparison CLI on saved diagnostic originals."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from independent_cpu_delivery import probe_media

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[1]
SCRATCH = WORKSPACE / ".runtime-work" / "c150911-comparison-cli"
FIXTURES = WORKSPACE / ".runtime-work" / "c150911-compat-selected"
PAIRS = {"forward_half": ("forward_right", "forward_left"),
         "reverse_half": ("reverse_right", "reverse_left"),
         "directional_right": ("forward_right", "reverse_right"),
         "right_half_obstruction": ("forward_right", "forward_right_obstructed")}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(name, first, second, output, diagnostic):
    args = [sys.executable, str(ROOT / "comparison_audit.py"), "--comparison", name,
            "--first-attempt", str(first), "--second-attempt", str(second),
            "--output", str(output)]
    if diagnostic:
        args.append("--diagnostic-fixture")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(WORKSPACE / ".runtime-work" / "c150911-output"))
    return subprocess.run(args, capture_output=True, text=True, env=env, timeout=180)


def rejected(name, first, second, label, expected, diagnostic):
    output = SCRATCH / (name + "-negative-" + label + ".json")
    run = command(name, first, second, output, diagnostic)
    if run.returncode == 0 or expected not in run.stderr or output.exists():
        raise AssertionError(label + " failed to reject: " + run.stderr)
    log = ROOT / ("cpu-comparison-negative-" + label + ".log")
    log.write_text(run.stderr)
    return {"rejected": True, "reason": expected, "log": log.name, "sha256": sha(log)}


def copy_fixture(name, source="forward_left"):
    target = SCRATCH / name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(FIXTURES / source / "primary", target)
    return target


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    proofs = {"format": "c150911-portable-comparison-cli-proof", "diagnostic_only": True,
              "physical_acceptance": False, "legal_practicability": "unresolved", "comparisons": {}}
    for name, (left, right) in PAIRS.items():
        first, second = [FIXTURES / item / "primary" for item in (left, right)]
        output = SCRATCH / (name + ".json")
        output.unlink(missing_ok=True)
        run = command(name, first, second, output, True)
        if run.returncode or not output.is_file():
            raise AssertionError(name + " positive failed: " + run.stderr)
        report = json.loads(output.read_text())
        if not report["passed"] or not report["diagnostic_only"] or report["original_frame_counts"] != [9, 9]:
            raise AssertionError(name + " diagnostic provenance differs")
        proofs["comparisons"][name] = {"passed": True, "case_ids": report["case_ids"],
            "report_sha256": sha(output), "original_frame_counts": report["original_frame_counts"]}
    first = FIXTURES / "forward_right" / "primary"
    missing = copy_fixture("missing-site")
    (missing / "original-site.json").unlink()
    proofs["missing_original_source"] = rejected("forward_half", first, missing,
        "missing-site", "Missing required original source: original-site.json", True)
    changed = copy_fixture("changed-fixed-crosswalk")
    site_path = changed / "original-site.json"
    site = json.loads(site_path.read_text())
    site["crosswalk_id"] += "-changed"
    site_path.write_text(json.dumps(site, sort_keys=True) + "\n")
    receipt_path = changed / "original-receipt.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["sources"]["original-site.json"] = sha(site_path)
    receipt_path.write_text(json.dumps(receipt, sort_keys=True) + "\n")
    proofs["changed_rehashed_fixed_source"] = rejected("forward_half", first, changed,
        "changed-crosswalk", "fixed site differs: crosswalk_id", True)
    for count in (2, 600):
        shortened = copy_fixture("short-" + str(count), "forward_right")
        receipt_path = shortened / "original-receipt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["diagnostic_fixture"] = False
        receipt["frame_count"] = count
        receipt_path.write_text(json.dumps(receipt, sort_keys=True) + "\n")
        proofs["short_production_" + str(count)] = rejected("forward_half", shortened,
            FIXTURES / "forward_left" / "primary", "short-" + str(count),
            "original 900-frame passage required", False)
    wrong_media = SCRATCH / "wrong-overview.mkv"
    encode = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(first / "overview.mkv"), "-vf", "scale=640:360", "-c:v", "ffv1",
        str(wrong_media)], capture_output=True, text=True, timeout=120)
    if encode.returncode:
        raise AssertionError("wrong-media fixture failed: " + encode.stderr)
    try:
        probe_media(wrong_media, "overview", 9, False)
    except ValueError as error:
        if "original Native media codec/rate/dimensions differ" not in str(error):
            raise
        proofs["changed_media_header"] = {"rejected": True, "reason": str(error),
            "video_sha256": sha(wrong_media)}
    else:
        raise AssertionError("production media profile accepted a changed dimension")
    output = ROOT / "cpu-original-comparison-proofs.json"
    output.write_text(json.dumps(proofs, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"comparisons": len(PAIRS), "negative_checks": 5, "passed": True}))


if __name__ == "__main__":
    main()
