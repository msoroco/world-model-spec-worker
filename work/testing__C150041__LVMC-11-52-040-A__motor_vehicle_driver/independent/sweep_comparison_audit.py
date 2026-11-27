"""Audit additional exact orientation sweep pairs using the original audit path.

These pairs compare accepted original attempts. The engineering angles are
construction requests, not statutory thresholds or legal judgments.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from parking_comparison_audit import PAIRS


EXTRA_PAIRS = {
    "sweep_0_vs_20": ("orientation_sweep-0000", "orientation_sweep-0003", "orientation"),
    "sweep_10_vs_30": ("orientation_sweep-0005", "orientation_sweep-0006", "orientation"),
    "sweep_40_vs_60": ("orientation_sweep-0002", "orientation_sweep-0004", "orientation"),
    "sweep_30_vs_50": ("orientation_sweep-0006", "orientation_sweep-0007", "orientation"),
    "sweep_70_vs_90": ("orientation_sweep-0008", "orientation_sweep-0001", "orientation"),
    "sweep_60_vs_80": ("orientation_sweep-0004", "orientation_sweep-0009", "orientation"),
}

# The imported original audit owns the fixed-condition, measured-separation,
# delivery-receipt, and missing-original rejection rules. This standalone
# process extends only its exact-case identity table before the CLI parses it.
if set(PAIRS).intersection(EXTRA_PAIRS):
    raise ValueError("supplemental comparison ID overlaps existing audit")
PAIRS.update(EXTRA_PAIRS)

from comparison_audit import main


if __name__ == "__main__":
    main()
