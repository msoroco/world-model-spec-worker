"""Exercise new sweep pairs against measured synthetic fixture positives and negatives."""
from __future__ import annotations

from pathlib import Path

from sweep_comparison_audit import EXTRA_PAIRS
from prove_comparison_audit import proof
from comparison_audit import verify_pair


def reject_unreviewed_fixture(comparison_id: str) -> None:
    first, second, _ = EXTRA_PAIRS[comparison_id]
    assignment_id = Path(__file__).resolve().parents[1].name
    left = {"case_id": assignment_id + '__' + first, "diagnostic_fixture": True}
    right = {"case_id": assignment_id + '__' + second, "diagnostic_fixture": False}
    try:
        verify_pair(comparison_id, left, right, {}, {})
    except ValueError as error:
        if 'original case acceptance missing' not in str(error):
            raise
    else:
        raise AssertionError('unreviewed synthetic source accepted as original')


if __name__ == "__main__":
    for comparison_id in EXTRA_PAIRS:
        proof(comparison_id)
        reject_unreviewed_fixture(comparison_id)
        print(comparison_id + ': unreviewed source rejected')
