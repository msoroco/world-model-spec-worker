"""Shared engineering fallback request for the two reciprocal-duty cases.

This does not change the later opponent's requested wait/proceed difference.
The slower subject target is selected only after a source-bound physical trigger.
"""

import argparse
import json
from pathlib import Path

from construction import build
from requirement_finalizer import ASSIGNMENT_ID

CASES = (ASSIGNMENT_ID + "__reciprocal_yield",
         ASSIGNMENT_ID + "__reciprocal_no_yield")
TRIGGER = {"source": "original Native actor trace and contact events",
           "metric": "ego physical clearance and actor contact before frame 900",
           "failure_condition": "ego did not clear reviewed intersection or any participant contact occurred"}


def fallback(case_id, packet):
    if case_id not in CASES:
        raise ValueError("fallback applies to both reciprocal cases only")
    request = build(case_id, packet)
    if request["controller"]["target_speed_mps"] != 5.0:
        raise ValueError("unexpected primary speed policy")
    request["controller"]["target_speed_mps"] = 3.0
    request["candidate_id"] = "fallback1"
    request["candidate_trigger"] = TRIGGER
    request["changed_knobs"] = ["ego controller target_speed_mps: 5.0 to 3.0"]
    request["physical_realization"] = "pending original Native execution"
    return request


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--map-packet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    request = fallback(args.case, json.loads(args.map_packet.read_text(encoding="utf-8")))
    args.output.write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")
