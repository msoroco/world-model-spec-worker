"""Exercise new sweep pairs against measured synthetic fixture positives and negatives."""
from __future__ import annotations

from sweep_comparison_audit import EXTRA_PAIRS
from prove_comparison_audit import proof


if __name__ == "__main__":
    for comparison_id in EXTRA_PAIRS:
        proof(comparison_id)
