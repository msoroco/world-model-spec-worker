"""Record exact CPU comparison positives and fixed-source negatives."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "comparison_audit_full.py"
PLAN = json.loads((ROOT / "case-plan.json").read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean(text):
    return "\n".join(line.rstrip() for line in text.rstrip().splitlines()) + "\n"


proofs = []
for comparison in PLAN["comparisons"]:
    cid = comparison["comparison_id"]
    suffix = cid.removeprefix(ROOT.name + "__")
    target = ROOT / "comparison-proofs" / suffix
    target.mkdir(parents=True, exist_ok=True)
    items = {}
    for negative in (False, True):
        argv = [sys.executable, "-B", str(SCRIPT), "--comparison-id", cid, "--self-test"]
        if negative:
            argv.append("--negative")
        result = subprocess.run(argv, cwd=ROOT.parents[1], text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, env=os.environ.copy(), timeout=120)
        log = target / ("negative.log" if negative else "positive.log")
        log.write_text(clean(result.stdout))
        if negative:
            assert result.returncode != 0 and "Comparison fixed source identity changed" in result.stdout
        else:
            assert result.returncode == 0, result.stdout
        items["negative" if negative else "positive"] = {
            "command": " ".join(argv), "exit_code": result.returncode,
            "log": str(log.relative_to(ROOT)), "log_sha256": sha(log),
        }
    proofs.append({"comparison_id": cid, "case_ids": comparison["case_ids"],
                   "script_sha256": sha(SCRIPT), **items,
                   "original_capture_attested": False})

output = ROOT / "comparison-proofs" / "index.json"
output.write_text(json.dumps({"format": "c179824-comparison-cpu-v1", "proofs": proofs,
                              "all_passed": True, "original_capture_attested": False}, indent=2) + "\n")
print(json.dumps({"comparisons": len(proofs), "all_passed": True}))
