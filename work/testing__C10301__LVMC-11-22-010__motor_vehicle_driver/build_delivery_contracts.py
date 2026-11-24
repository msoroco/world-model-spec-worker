"""Record diagnostic CPU audit and production diagnostic-source refusal."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
AID = HERE.name


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> None:
    script = HERE / "prove_delivery_audit.py"
    for kind, attempt in (("steady_travel", "full900-attempt"),
                          ("steering_variation", "full900-variation-attempt")):
        short = "steady" if kind == "steady_travel" else "variation"
        case = AID + "__" + kind
        positive = HERE / ("cpu-delivery-" + short + "-positive.log")
        negative = HERE / ("cpu-delivery-" + short + "-negative.log")
        observation = json.loads(positive.read_text())
        if (observation.get("case_id") != case or observation.get("source_audit_passed") is not True
                or observation.get("delivery_accepted") is not False
                or observation.get("decoded_original_pngs") != 3600
                or "diagnostic capture cannot be delivered" not in negative.read_text()):
            raise ValueError("Independent diagnostic audit outcome differs")
        args = " --case " + case + " --attempt .runtime-work/c10301-010-nov24b/" + attempt
        base = ".venv-cpu/bin/python work/" + AID + "/prove_delivery_audit.py" + args
        receipt = {
            "case_id": case, "sets": ["full-test"],
            "checks": ["native_source", "all_participants", "time_join", "full_video_decode",
                       "actual_pixels", "physical_completion"],
            "scope": "CPU diagnostic source-audit exercise; no production delivery accepted",
            "diagnostic_fixture": True, "physical_acceptance_claimed": False,
            "command": base + " --mode diagnostic-positive",
            "test_exit_code": 0, "test_log": positive.name, "test_log_sha256": sha(positive),
            "negative_command": base + " --mode delivery-negative",
            "negative_exit_code": 1, "negative_expected_error": "diagnostic capture cannot be delivered",
            "negative_log": negative.name, "negative_log_sha256": sha(negative),
            "script": script.name, "script_sha256": sha(script),
        }
        (HERE / ("delivery-acceptance-" + kind + ".json")).write_text(
            json.dumps(receipt, indent=2) + "\n")
    print("Bound exact diagnostic audit positives and production refusals")


if __name__ == "__main__":
    build()
