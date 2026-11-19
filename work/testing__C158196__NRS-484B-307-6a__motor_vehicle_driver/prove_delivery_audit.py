"""Run four exact-case diagnostic audits and a missing-governance negative test."""

import hashlib
import json
import shutil
from pathlib import Path

from delivery_audit import HERE, REPO, audit

ATTEMPTS = {
    "entry_before_red": ".runtime-work/c158196-yellow-red-four-camera-validation/attempt",
    "entry_at_red": ".runtime-work/c158196-yellow-red-at-red-four-camera/attempt",
    "entry_after_red": ".runtime-work/c158196-yellow-red-after-red-four-camera/attempt",
    "stops_on_yellow": ".runtime-work/c158196-yellow-red-yellow-stop-four-camera/attempt",
}
EXPECTED = "Original governed signal or lane differs"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    reports = {}
    for suffix, rel in ATTEMPTS.items():
        case_id = HERE.name + "__" + suffix
        report = audit(REPO / rel, case_id, diagnostic_selftest=True)
        if (report["format"] != "worker-delivery-audit-diagnostic" or
                report["passed"] is not False or report["software_checks_passed"] is not True or
                report["physical_acceptance_claimed"] is not False):
            raise ValueError("Synthetic source audit made a physical claim")
        reports[suffix] = {"red_onset_frame": report["red_onset_frame"],
                           "first_body_entry_frame": report["first_body_entry_frame"],
                           "camera_audits": report["camera_audits"],
                           "source_sha256": report["source_sha256"]}
    source = REPO / ATTEMPTS["entry_before_red"]
    negative = REPO / ".runtime-work/c158196-delivery-audit-negative-replay"
    negative.mkdir(parents=True, exist_ok=True)
    for name in ("junction_context.json", "acquisition-provenance.json",
                 "video_frames.jsonl", "signal_vehicle_history.jsonl"):
        shutil.copyfile(source / name, negative / name)
    history = negative / "signal_vehicle_history.jsonl"
    rows = history.read_text().splitlines()
    first = json.loads(rows[0]); first["lane_id"] += 1
    rows[0] = json.dumps(first, separators=(",", ":"))
    history.write_text("\n".join(rows) + "\n")
    try:
        audit(negative, HERE.name + "__entry_before_red", diagnostic_selftest=True)
    except ValueError as exc:
        if EXPECTED not in str(exc):
            raise
    else:
        raise ValueError("Missing governance negative was accepted")
    return {"format": "worker-cpu-delivery-audit-proof", "passed": True,
            "scope": "Synthetic software diagnostics only; no Native pixel or physical acceptance",
            "auditor": "delivery_audit.py", "auditor_sha256": sha(HERE / "delivery_audit.py"),
            "positive_cases": reports, "negative_expected_error": EXPECTED}


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True))
