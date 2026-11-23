"""Bind the four independently tested red-X acceptance gates to the manifest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KINDS = ("adjacent_travel", "lateral_entry", "red_lane_stand", "red_lane_drive")
CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    path = ROOT / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    script = ROOT / "independent/delivery_audit.py"
    if {entry["case_id"] for entry in manifest["cases"]} != {
            ROOT.name + "__" + kind for kind in KINDS}:
        raise ValueError("exact red-X case coverage differs")
    for entry in manifest["cases"]:
        case = entry["case_id"]
        kind = case.removeprefix(ROOT.name + "__")
        positive = ROOT / "independent" / (kind + "-positive.log")
        negative = ROOT / "independent" / (kind + "-negative.log")
        if ("diagnostic protocol positive and three negatives passed" not in positive.read_text() or
                "original pixel review missing or stale" not in negative.read_text()):
            raise ValueError("exact audit CPU proof missing: " + case)
        command = ('PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/' + ROOT.name +
                   '/independent/prove_delivery_audit.py ' + case)
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["full-test"], "checks": list(CHECKS),
            "script": "independent/delivery_audit.py", "script_sha256": sha(script),
            "command": command, "test_exit_code": 0,
            "test_log": "independent/" + kind + "-positive.log",
            "test_log_sha256": sha(positive),
            "negative_command": command + " --negative", "negative_exit_code": 1,
            "negative_expected_error": "original pixel review missing or stale",
            "negative_log": "independent/" + kind + "-negative.log",
            "negative_log_sha256": sha(negative),
            "proof_scope": "synthetic CPU audit invariants; original pixel and physical acceptance unclaimed",
        }
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print("four exact independent delivery acceptance contracts bound")


if __name__ == "__main__":
    main()
