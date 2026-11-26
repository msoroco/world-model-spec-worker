"""CPU positive/negative isolation proofs for all eight exact comparisons."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from package_spec import AID


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPT = HERE / "comparison_audit.py"
SCRATCH = ROOT / ".runtime-work" / "c228989-owner-nov26" / "comparison-diagnostic-v2"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def run():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    plan = json.loads((HERE / "case-plan.json").read_text())
    need = plan["assignment_id"] == AID and len(plan["comparisons"]) == 8
    if not need:
        raise ValueError("eight exact comparison plans required")
    map_sha = hashlib.sha256(b"reviewed map protocol fixture").hexdigest()
    reports = []
    for comparison in plan["comparisons"]:
        cid = comparison["comparison_id"]
        root = SCRATCH / cid
        if root.exists():
            raise ValueError("retain prior comparison diagnostic fixture")
        root.mkdir()
        records = {}
        for case_id in comparison["case_ids"]:
            records[case_id] = {"case_id": case_id, "frame_count": 900,
                                "full_decode": True, "actual_pixels": True,
                                "physical_status": "met", "legal_verdict": None,
                                "receipt_sha256": hashlib.sha256(case_id.encode()).hexdigest(),
                                "native_map_sha256": map_sha,
                                "measurements": {key: {"source": "synthetic CPU protocol"}
                                                 for key in ("activation", "due_care_sources",
                                                             "lane_topology", "lane_movement")}}
        positive = root / "records.json"
        write(positive, records)
        negative = root / "wrong-map.json"
        changed = json.loads(positive.read_text())
        changed[comparison["case_ids"][-1]]["native_map_sha256"] = hashlib.sha256(cid.encode()).hexdigest()
        write(negative, changed)
        base = [sys.executable, str(SCRIPT), "--comparison", cid, "--records"]
        env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH), TMPDIR=str(SCRATCH))
        good = subprocess.run(base + [str(positive)], cwd=ROOT, env=env, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        bad = subprocess.run(base + [str(negative)], cwd=ROOT, env=env, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        good_log = HERE / ("proof-comparison-positive-" + cid + ".log")
        bad_log = HERE / ("proof-comparison-negative-" + cid + ".log")
        good_log.write_text(good.stdout.rstrip() + "\n")
        bad_log.write_text(bad.stdout.rstrip() + "\n")
        if good.returncode or bad.returncode == 0 or \
                "comparison source map differs across fixed road context" not in bad.stdout:
            raise ValueError("comparison isolation proof failed: " + cid)
        output = json.loads(good.stdout)
        if output.get("diagnostic_fixture") is not True or output.get("source_verified") is not False:
            raise ValueError("comparison diagnostic cannot claim Native acceptance")
        reports.append({"comparison_id": cid, "case_ids": comparison["case_ids"],
                        "script": SCRIPT.name, "script_sha256": sha(SCRIPT),
                        "positive_command": " ".join(base + [str(positive)]),
                        "positive_exit_code": 0, "positive_log": good_log.name,
                        "positive_log_sha256": sha(good_log),
                        "negative_command": " ".join(base + [str(negative)]),
                        "negative_exit_code": bad.returncode, "negative_log": bad_log.name,
                        "negative_log_sha256": sha(bad_log),
                        "negative_expected_error": "comparison source map differs across fixed road context",
                        "scope": "synthetic CPU protocol; original cases require independent saved audits"})
    write(HERE / "comparison-proposal.json",
          {"format": "pass-exact-comparison-proposal", "assignment_id": AID,
           "comparisons": reports, "legal_verdict": None})
    return len(reports)


if __name__ == "__main__":
    print("independent comparison CPU proofs:", run())
