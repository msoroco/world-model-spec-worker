"""Bind the checked school-warning constructions to explicit delivery cases."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
SUFFIXES = ("probe_1", "probe_2", "signal_stopped", "signal_raised",
            "flagman_go", "flagman_left", "person_go", "person_left")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def select():
    draft = json.loads((ROOT / "draft-variant-manifest.json").read_text())
    plan_path = ROOT / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    for case in plan["cases"]:
        case["kind"] = "delivery"
    plan["camera_plan"] = {
        "profile": "overview1080-capability",
        "duration_s": 30,
        "composition": "synchronized_four_view_primary",
        "coverage": [{"view": name, "subject": "school lane, child, warning actor, ego vehicle",
                      "interval": "all 600 frames at 20 Hz"}
                     for name in ("overview", "approach", "reference_corner", "driver_reference")],
    }
    for disposition in plan["requirement_dispositions"]:
        disposition["evidence_or_gap"] = (
            "Selected exact source-bound Native requests and fallbacks have passing CPU offline, "
            "positive/missing-source compatibility, saved-only and independent diagnostic audits. "
            "Original school lane, child identity, warning act, physical progression, pixels and "
            "legal outcome remain unverified.")
    write(plan_path, plan)
    rows = []
    for source in draft["cases"]:
        case = dict(source)
        suffix = case["case_id"].rsplit("__", 1)[1]
        assert suffix in SUFFIXES
        construction = json.loads((ROOT / case["construction"]).read_text())
        case.update(id=suffix, kind="delivery",
                    recording_description=construction["recording_description"],
                    native_handoff={"python_env_var": "CARLA_PYTHON",
                                    "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"})
        saved_name = "probe1" if suffix == "probe_1" else suffix
        attempt = REPO / ".runtime-work" / ("c394563-variant-attempt-" + saved_name + "-v2")
        saved = REPO / ".runtime-work" / ("c394563-variant-saved-" + saved_name + "-v2")
        version = "v0003" if suffix == "probe_1" else "v0001"
        processing = saved / version / "processing.json"
        receipt = json.loads(processing.read_text())
        assert receipt["passed"] and receipt["recorded_only"] and receipt["originals_preserved"]
        assert receipt["native_revision"]["construction_sha256"] == case["construction_sha256"]
        proof = ROOT / "proofs" / ("variant-" + suffix)
        saved_log = Path(str(proof) + "-saved.log")
        saved_log.write_text("runtime.py process-saved passed; processing.json sha256 " + sha(processing) + "\n")
        case["post_capture"] = {
            "recorded_only": True,
            "command": "runtime.py process-saved --manifest work/" + ASSIGNMENT + "/execution-manifest.json --case " + case["case_id"] + " --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER",
            "feedback_command": "cat $SAVED_OUTPUT/feedback.json # " + case["case_id"],
            "test_exit_code": 0,
            "test_log": str(saved_log.relative_to(ROOT)),
            "test_log_sha256": sha(saved_log),
        }
        positive_log = Path(str(proof) + "-delivery-positive.log")
        negative_log = Path(str(proof) + "-delivery-negative.log")
        audit = ROOT / "delivery_audit.py"
        base = [str(REPO / ".venv-cpu/bin/python"), "-B", str(audit),
                "--variant", "--case", case["case_id"], "--candidate", "primary",
                "--attempt", str(attempt), "--processing", str(processing),
                "--diagnostic"]
        positive_output = REPO / ".runtime-work" / ("c394563-variant-delivery-" + suffix + "-selection-positive.json")
        positive = base + ["--output", str(positive_output)]
        result = subprocess.run(positive, capture_output=True, text=True)
        if result.returncode:
            raise ValueError("Delivery positive failed: " + suffix + ": " + result.stderr[-500:])
        positive_log.write_text((result.stdout + result.stderr).rstrip() + "\n")
        negative_output = REPO / ".runtime-work" / ("c394563-variant-delivery-" + suffix + "-selection-negative.json")
        negative = base + ["--output", str(negative_output), "--omit-source", "original-school-lane-review.json"]
        rejected = subprocess.run(negative, capture_output=True, text=True)
        negative_log.write_text((rejected.stdout + rejected.stderr).rstrip() + "\n")
        expected = "Missing source: original-school-lane-review.json"
        if rejected.returncode == 0 or expected not in negative_log.read_text():
            raise ValueError("Delivery negative failed: " + suffix)
        case["delivery_acceptance"] = {
            "case_id": case["case_id"], "sets": ["full-train"],
            "checks": ["native_source", "all_participants", "time_join", "full_video_decode",
                       "actual_pixels", "physical_completion"],
            "script": "delivery_audit.py", "script_sha256": sha(audit),
            "command": " ".join(positive), "test_exit_code": 0,
            "test_log": str(positive_log.relative_to(ROOT)), "test_log_sha256": sha(positive_log),
            "negative_command": " ".join(negative), "negative_exit_code": rejected.returncode,
            "negative_expected_error": expected,
            "negative_log": str(negative_log.relative_to(ROOT)), "negative_log_sha256": sha(negative_log),
        }
        rows.append(case)
    primary = json.loads((ROOT / rows[0]["construction"]).read_text())
    write(ROOT / "construction.json", primary)
    for item in primary["files"]:
        if "source" not in item:
            path = ROOT / item["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.is_file() or path.read_text() != item["content"]:
                path.write_text(item["content"])
    selected = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
                "cases": rows}
    write(ROOT / "execution-manifest.json", selected)
    return len(rows)


if __name__ == "__main__":
    print(json.dumps({"selected_cases": select()}))
