"""Run exact-case saved measurement CLI on labeled synthetic protocols."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from build_case_plan import AID, KINDS
from tests.test_saved_measurement import protocol

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    base = REPO / ".runtime-work" / ("c153046-measurement-" +
           datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f"))
    results = []
    all_passed = True
    for suffix in KINDS:
        folder = base / suffix
        folder.mkdir(parents=True)
        site, trace, case_id, rows = protocol(folder, suffix=suffix)
        output = folder / "measurement.json"
        command = [sys.executable, str(ROOT / "saved_measurement.py"),
                   "--packet", str(site), "--trace", str(trace),
                   "--case", case_id, "--output", str(output)]
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        positive = subprocess.run(command, cwd=REPO, env=env,
                                  text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        passed = positive.returncode == 0 and output.is_file()
        if passed:
            measured = json.loads(output.read_text())
            passed = (measured["case_id"] == case_id and
                      measured["engineering_stop_observed"] == (KINDS[suffix][0] == "complete_stop") and
                      measured["first_approach_lane_id"] == measured["selected_approach_lane_id"] and
                      measured["physical_acceptance_claimed"] is False)
            if suffix.endswith("pedestrian_advance"):
                passed = passed and measured["conflicts_at_first_boundary_crossing"]["pedestrian"] is True
            if suffix.endswith("traffic_advance"):
                passed = passed and measured["conflicts_at_first_boundary_crossing"]["other_traffic"] is True
        rows[0]["case_id"] = "wrong-case"
        trace.write_text("".join(json.dumps(row) + "\n" for row in rows))
        negative = subprocess.run(command[:-1] + [str(folder / "rejected.json")], cwd=REPO,
                                  env=env, text=True, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT)
        rejected = negative.returncode != 0 and "trace lacks exact original case/source join" in negative.stdout
        all_passed = all_passed and passed and rejected
        results.append({"case_id": case_id, "positive_exit_code": positive.returncode,
                        "positive_output": positive.stdout.strip(),
                        "measurement_sha256": sha(output) if output.is_file() else None,
                        "negative_exit_code": negative.returncode,
                        "negative_expected_error": "trace lacks exact original case/source join",
                        "negative_rejected": rejected,
                        "measurement_status": "synthetic_protocol_only"})
        print(suffix, "positive", passed, "wrong-case rejected", rejected)
    receipt = {"format": "c153046-exact-saved-measurement-cpu-proof",
               "all_passed": all_passed, "physical_acceptance_claimed": False,
               "cases": results}
    (ROOT / "cpu-measurement-proof.json").write_text(json.dumps(receipt, indent=2) + "\n")
    if not all_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
