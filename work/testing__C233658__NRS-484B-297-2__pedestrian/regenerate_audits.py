"""Run independent delivery and comparison audits on current diagnostic attempts."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TAG = os.environ.get("PEDESTRIAN_PROOF_TAG", "current3")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(args, log, expected):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT / ".runtime-work" / "pedestrian-output"))
    cmd = [str(ROOT / ".venv-cpu/bin/python"), *map(str, args)]
    result = subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True)
    output = (result.stdout + result.stderr).rstrip() + "\n"
    log.write_text(output, encoding="utf-8")
    if result.returncode != expected:
        raise RuntimeError(f"unexpected exit {result.returncode}: {log}")
    return " ".join([".venv-cpu/bin/python", *map(str, args)])


def attempt(cid):
    return Path(".runtime-work") / f"pedestrian-compat-{cid.split('__')[-1]}-primary-{TAG}"


def main():
    plan = json.loads((HERE / "case-plan.json").read_text())
    delivery = []
    for case in plan["cases"]:
        cid = case["case_id"]
        short = cid.split("__")[-1]
        folder = HERE / "cases" / short
        report = Path(".runtime-work") / f"pedestrian-delivery-audit-{short}-{TAG}.json"
        args = [Path("work") / HERE.name / "delivery_audit.py", "--attempt", attempt(cid),
                "--case-id", cid, "--diagnostic", "--output", report]
        log = folder / "cpu-independent-positive.log"
        command = run(args, log, 0)
        receipt = folder / "cpu-independent-positive.json"
        receipt.write_bytes((ROOT / report).read_bytes())
        neg_attempt = ROOT / ".runtime-work" / f"pedestrian-delivery-negative-{short}-{TAG}"
        neg_attempt.mkdir(parents=True, exist_ok=True)
        for name in ("config.json", "case-spec.json"):
            (neg_attempt / name).write_bytes((ROOT / attempt(cid) / name).read_bytes())
        neg_report = Path(".runtime-work") / f"pedestrian-delivery-negative-result-{short}-{TAG}.json"
        neg_args = [Path("work") / HERE.name / "delivery_audit.py", "--attempt", neg_attempt,
                    "--case-id", cid, "--diagnostic", "--output", neg_report]
        neg_log = folder / "cpu-independent-negative.log"
        neg_command = run(neg_args, neg_log, 1)
        error = "Missing required source: original-walking-observations.json"
        if error not in neg_log.read_text():
            raise RuntimeError("negative delivery did not reject missing original source")
        delivery.append({"case_id": cid, "command": command, "exit_code": 0,
                         "log": str(log.relative_to(HERE)), "log_sha256": sha(log),
                         "receipt": str(receipt.relative_to(HERE)), "receipt_sha256": sha(receipt),
                         "negative_command": neg_command, "negative_exit_code": 1,
                         "negative_expected_error": error,
                         "negative_log": str(neg_log.relative_to(HERE)),
                         "negative_log_sha256": sha(neg_log)})
        print(short, "delivery audit passed", flush=True)
    write(HERE / "cpu-independent-proofs.json", delivery)
    comparisons = []
    for comp in plan["comparisons"]:
        comparison_id = comp["comparison_id"]
        first, second = map(attempt, comp["case_ids"])
        report = Path(".runtime-work") / f"pedestrian-comparison-{comparison_id}-{TAG}.json"
        args = [Path("work") / HERE.name / "comparison_audit.py", "--comparison", comparison_id,
                "--first-attempt", first, "--second-attempt", second,
                "--diagnostic-fixture", "--output", report]
        log = HERE / f"comparison-{comparison_id}.log"
        command = run(args, log, 0)
        receipt = HERE / f"comparison-{comparison_id}.json"
        receipt.write_bytes((ROOT / report).read_bytes())
        second_id = comp["case_ids"][1]
        neg_attempt = ROOT / ".runtime-work" / f"pedestrian-comparison-negative-{comparison_id}-{TAG}"
        neg_attempt.mkdir(parents=True, exist_ok=True)
        for name in ("config.json", "case-spec.json"):
            (neg_attempt / name).write_bytes((ROOT / attempt(second_id) / name).read_bytes())
        neg_report = Path(".runtime-work") / f"pedestrian-comparison-negative-result-{comparison_id}-{TAG}.json"
        neg_args = [Path("work") / HERE.name / "comparison_audit.py", "--comparison", comparison_id,
                    "--first-attempt", first, "--second-attempt", neg_attempt,
                    "--diagnostic-fixture", "--output", neg_report]
        neg_log = HERE / f"comparison-negative-{comparison_id}.log"
        neg_command = run(neg_args, neg_log, 1)
        error = "Missing required source: original-walking-observations.json"
        if error not in neg_log.read_text():
            raise RuntimeError("negative comparison did not reject missing original source")
        comparisons.append({"comparison_id": comparison_id, "case_ids": comp["case_ids"],
                            "command": command, "exit_code": 0,
                            "log": str(log.relative_to(HERE)), "log_sha256": sha(log),
                            "receipt": str(receipt.relative_to(HERE)), "receipt_sha256": sha(receipt),
                            "negative_command": neg_command, "negative_exit_code": 1,
                            "negative_expected_error": error,
                            "negative_log": str(neg_log.relative_to(HERE)),
                            "negative_log_sha256": sha(neg_log)})
        print(comparison_id, "comparison audit passed", flush=True)
    write(HERE / "cpu-comparison-proofs.json", comparisons)


if __name__ == "__main__":
    main()
