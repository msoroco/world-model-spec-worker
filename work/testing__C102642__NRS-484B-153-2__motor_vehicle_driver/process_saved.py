"""Saved-only original door-interaction audit command.

This checks the Native acquisition and emits measurements. It does not call
CARLA, accept a recording, or decide legal interference.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from delivery_audit import audit_saved


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--trace-sha256", required=True)
    parser.add_argument("--survey", type=Path, required=True)
    parser.add_argument("--survey-sha256", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--act", choices=("open", "board", "alight"), required=True)
    parser.add_argument("--side", choices=("left", "right"), required=True)
    parser.add_argument("--dimensions", type=Path, required=True,
                        help="JSON object of expected [width,height] for each camera")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dimensions = json.loads(args.dimensions.read_text(encoding="utf-8"))
    result = audit_saved(args.attempt, trace_sha256=args.trace_sha256,
                         case_id=args.case_id, act=args.act, side=args.side,
                         expected_dimensions=dimensions, survey_path=args.survey,
                         survey_sha256=args.survey_sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")


if __name__ == "__main__":
    main()
