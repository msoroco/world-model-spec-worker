"""CPU-only proof for the proposed original delivery auditor.

The fixture video is generated in a temporary directory. This never creates
an original Native capture, canonical audit, or accepted recording.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
AUDITOR = ROOT / "native/delivery_audit.py"
ASSIGNMENT = ROOT.name
CASES = ("reference", "contrast", "divided_reference", "divided_opening")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(case, negative):
    command = [sys.executable, str(AUDITOR), "--case", ASSIGNMENT + "__" + case,
               "--negative-selftest" if negative else "--selftest"]
    completed = subprocess.run(command, capture_output=True, text=True)
    folder = ROOT / "proof-delivery-audit" / case
    folder.mkdir(parents=True, exist_ok=True)
    log = folder / ("negative.log" if negative else "positive.log")
    log.write_text(completed.stdout + completed.stderr)
    if negative:
        if completed.returncode == 0 or "Reviewed pixel box exceeds decoded video" not in completed.stderr:
            raise ValueError("Changed pixel box was not rejected for " + case)
        return {"case_id": ASSIGNMENT + "__" + case, "rejected": True,
                "failure": "Reviewed pixel box exceeds decoded video",
                "command": command, "exit_code": completed.returncode,
                "log": str(log.relative_to(ROOT)), "log_sha256": sha(log)}
    if completed.returncode:
        raise ValueError("Auditor fixture failed for " + case + ": " + completed.stderr)
    value = json.loads(completed.stdout)
    if (value.get("passed") is not True or value.get("accepted") is not False or
            value.get("original_native_observed") is not False or
            value.get("internal_negative_checks") != 8):
        raise ValueError("Auditor selftest made an unsupported claim")
    value.update({"command": command, "exit_code": completed.returncode,
                  "log": str(log.relative_to(ROOT)), "log_sha256": sha(log)})
    return value


positives = [run(case, False) for case in CASES]
negatives = [run(case, True) for case in CASES]
proof = {"format": "c111662-delivery-auditor-cpu-proof-v1", "passed": True,
         "auditor": str(AUDITOR.relative_to(ROOT)), "auditor_sha256": sha(AUDITOR),
         "positive_full_decode_fixtures": len(positives),
         "explicit_pixel_negative_rejections": len(negatives),
         "internal_negative_rejections": sum(row["internal_negative_checks"] for row in positives),
         "positive_cases": positives, "negative_cases": negatives,
         "fixture_only": True, "original_native_observed": False,
         "canonical_delivery_audits": 0, "accepted_recordings": 0}
output = ROOT / "update015-delivery-auditor-cpu-proof.json"
output.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps({"proof": str(output.relative_to(ROOT)),
                  "sha256": sha(output), "positive": len(positives),
                  "negative": len(negatives) + proof["internal_negative_rejections"]}))
