"""Compare two reviewed original Native attempts without assigning a legal verdict."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from saved_attempt import process_saved
from comparison_audit import audit_pair


def read_summary(attempt):
    attempt = attempt.resolve()
    packet = json.loads((attempt / 'original-green-packet.json').read_text())
    summary = process_saved(packet, attempt)
    if packet.get('duration_frames') != 900:
        raise ValueError('production comparison requires 900 original frames')
    return summary


def run(comparison, left, right):
    result = audit_pair(comparison, read_summary(left), read_summary(right))
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left', type=Path, required=True)
    parser.add_argument('--right', type=Path, required=True)
    args = parser.parse_args()
    run(args.comparison, args.left, args.right)
