"""Replay independent selected delivery and comparison audits at 600 frames."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / ".runtime-work/c111256-current"
CASES = ("witness_1", "witness_2", "exception_1_1", "exception_1_2")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(name, args, expected):
    log = HERE / name
    with log.open("w") as stream:
        code = subprocess.run([sys.executable, *map(str, args)], cwd=ROOT,
                              stdout=stream, stderr=subprocess.STDOUT).returncode
    if (code == 0) != (expected == 0):
        raise RuntimeError(f"{name}: received exit {code}, expected {expected}")
    return {"log": name, "log_sha256": sha(log), "exit_code": code}


def main():
    matrix = json.loads((HERE / "current-selected-matrix-proof.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    outcomes = {"delivery": {}, "comparisons": {}}
    for case in CASES:
        selected = matrix["paths"][case + "-primary"]
        attempt = ROOT / selected["attempt"]
        processing = ROOT / selected["saved"] / "v0001/processing.json"
        args = [HERE / "delivery_audit.py", "--case", HERE.name + "__" + case,
                "--candidate", "primary", "--attempt", attempt,
                "--processing", processing]
        positive = SCRATCH / ("delivery-" + case + "-positive.json")
        negative = SCRATCH / ("delivery-" + case + "-negative.json")
        outcomes["delivery"][case] = {
            "positive": run("current-delivery-" + case + "-positive.log",
                            args + ["--output", positive, "--diagnostic"], 0),
            "negative": run("current-delivery-" + case + "-negative.log",
                            args + ["--output", negative], 1),
            "diagnostic_receipt_sha256": sha(positive)}
        if "Original Native source required" not in (HERE / outcomes["delivery"][case]["negative"]["log"]).read_text():
            raise ValueError("Negative original-source rejection absent: " + case)
    for comparison in plan["comparisons"]:
        suffixes = [case.rsplit("__", 1)[1] for case in comparison["case_ids"]]
        attempts = [ROOT / matrix["paths"][suffix + "-primary"]["attempt"]
                    for suffix in suffixes]
        name = comparison["comparison_id"].rsplit("__", 1)[1]
        args = [HERE / "comparison_audit.py", "--comparison", comparison["comparison_id"],
                "--left", attempts[0], "--right", attempts[1]]
        positive = SCRATCH / ("comparison-" + name + "-positive.json")
        negative = SCRATCH / ("comparison-" + name + "-negative.json")
        outcomes["comparisons"][name] = {
            "positive": run("current-comparison-" + name + "-positive.log",
                            args + ["--output", positive, "--diagnostic"], 0),
            "negative": run("current-comparison-" + name + "-negative.log",
                            args + ["--output", negative], 1),
            "diagnostic_receipt_sha256": sha(positive)}
        if "Original Native comparison sources required" not in (HERE / outcomes["comparisons"][name]["negative"]["log"]).read_text():
            raise ValueError("Negative comparison rejection absent: " + name)
    proof = {"format": "c111256-current-delivery-comparison-v1", "passed": True,
             "matrix_proof_sha256": sha(HERE / "current-selected-matrix-proof.json"),
             "delivery_script_sha256": sha(HERE / "delivery_audit.py"),
             "comparison_script_sha256": sha(HERE / "comparison_audit.py"),
             "outcomes": outcomes, "original_native_or_legal_claimed": False}
    target = HERE / "current-delivery-comparison-proof.json"
    target.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"proof_sha256": sha(target), "cases": len(CASES),
                      "comparisons": len(plan["comparisons"])}))


if __name__ == "__main__":
    main()
