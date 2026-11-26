"""Run independent selected delivery and comparison CPU positive/negative audits."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path):
    return str(Path(path).relative_to(HERE))


def run(command, log):
    completed = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
    lines = [line.rstrip() for line in (completed.stdout + completed.stderr).splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    Path(log).write_text("\n".join(lines) + "\n")
    return completed.returncode


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    script = HERE / "delivery_audit.py"
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.rsplit("__", 1)[-1]
        proof = HERE / "proofs" / suffix
        attempt = REPO / ".runtime-work" / f"c24758-{suffix}-final2-saved-attempt-20261125"
        processing = REPO / ".runtime-work" / f"c24758-{suffix}-final2-saved-20261125/v0001/processing.json"
        base = [sys.executable, str(script), "--case", case, "--candidate", "primary",
                "--attempt", str(attempt), "--processing", str(processing),
                "--output", str(REPO / ".runtime-work" / f"c24758-{suffix}-delivery-audit-final2.json"),
                "--diagnostic"]
        positive = proof / "delivery-positive.log"
        negative = proof / "delivery-negative.log"
        positive_exit = run(base, positive)
        negative_command = base + ["--omit-source", "review.json"]
        negative_exit = run(negative_command, negative)
        if (positive_exit != 0 or negative_exit == 0 or
                "Missing source: review.json" not in negative.read_text()):
            raise ValueError("Independent delivery audit proof failed: " + case)
        entry["delivery_acceptance"] = {"case_id": case, "sets": ["full-train"],
            "checks": ["native_source", "all_participants", "time_join", "full_video_decode",
                       "actual_pixels", "physical_completion", "independent_sight_and_exception_review"],
            "script": rel(script), "script_sha256": sha(script),
            "command": " ".join(base), "test_exit_code": positive_exit,
            "test_log": rel(positive), "test_log_sha256": sha(positive),
            "negative_command": " ".join(negative_command),
            "negative_exit_code": negative_exit,
            "negative_expected_error": "Missing source: review.json",
            "negative_log": rel(negative), "negative_log_sha256": sha(negative)}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    compare_script = HERE / "comparison_audit.py"
    for comparison in plan["comparisons"]:
        ident = comparison["comparison_id"]
        command = [sys.executable, str(compare_script), "--comparison", ident]
        for case in comparison["case_ids"]:
            suffix = case.rsplit("__", 1)[-1]
            processing = REPO / ".runtime-work" / f"c24758-{suffix}-final2-saved-20261125/v0001/processing.json"
            command.extend(["--processing", case + "=" + str(processing)])
        command.extend(["--output", str(REPO / ".runtime-work/c24758-comparison-final2.json")])
        positive = HERE / "proofs/comparison-positive.log"
        negative = HERE / "proofs/comparison-negative.log"
        positive_exit = run(command, positive)
        negative_command = command + ["--omit-case", comparison["case_ids"][-1]]
        negative_exit = run(negative_command, negative)
        if (positive_exit != 0 or negative_exit == 0 or
                "Missing comparison case:" not in negative.read_text()):
            raise ValueError("Independent comparison audit proof failed")
        comparison["audit"] = {"script": rel(compare_script), "script_sha256": sha(compare_script),
            "command": " ".join(command), "test_log": rel(positive),
            "test_log_sha256": sha(positive), "test_exit_code": positive_exit,
            "negative_command": " ".join(negative_command), "negative_log": rel(negative),
            "negative_log_sha256": sha(negative), "negative_exit_code": negative_exit}
    plan_path.write_text(json.dumps(plan, indent=2) + "\n")
    print(json.dumps({"delivery_cases": len(manifest["cases"]), "comparisons": len(plan["comparisons"])}))


if __name__ == "__main__":
    main()
