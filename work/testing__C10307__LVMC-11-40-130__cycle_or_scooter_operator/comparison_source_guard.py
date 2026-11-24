"""Independent source-value guard before the saved bicycle comparison audit."""
from __future__ import annotations

import json
import math
from pathlib import Path

from comparison_audit import audit_saved_pair


def check_record(record: dict) -> None:
    samples = record.get("samples")
    conditions = record.get("condition_samples")
    if not isinstance(samples, list) or not samples or not isinstance(conditions, list):
        raise ValueError("original speed and condition samples required")
    speeds = [row.get("speed_mps") for row in samples]
    times = [row.get("time_s") for row in samples]
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or
           not math.isfinite(value) or value < 0 for value in speeds):
        raise ValueError("invalid original speed history")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or
           not math.isfinite(value) for value in times) or any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("original speed time axis invalid")
    mean = record.get("summary", {}).get("mean_speed_mps")
    if isinstance(mean, bool) or not isinstance(mean, (int, float)) or not math.isfinite(mean) or abs(mean - sum(speeds) / len(speeds)) > 1e-8:
        raise ValueError("reported mean differs from original speed history")
    if [row.get("time_s") for row in conditions] != times:
        raise ValueError("condition source time axis differs")


def audit_guarded_pair(plan: dict, comparison_id: str, left: Path,
                       right: Path, left_audit: Path, right_audit: Path) -> dict:
    for path in (left, right):
        check_record(json.loads(Path(path).read_text(encoding="utf-8")))
    return audit_saved_pair(plan, comparison_id, left, right, left_audit, right_audit)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--left-delivery-audit", type=Path, required=True)
    parser.add_argument("--right-delivery-audit", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    print(json.dumps(audit_guarded_pair(plan, args.comparison, args.left,
                                        args.right, args.left_delivery_audit,
                                        args.right_delivery_audit), sort_keys=True))


if __name__ == "__main__":
    main()
