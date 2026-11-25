"""Check selected paired observations with independent source-bound summaries."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from test_saved_attempt import packet
from saved_attempt import process_saved
from comparison_audit import PAIRS, audit_pair, ComparisonError


def run(comparison, scratch, output, negative):
    if comparison not in PAIRS:
        raise ValueError('unknown exact comparison')
    left, right = PAIRS[comparison][:2]
    summaries = []
    for suffix in (left, right):
        base = scratch / suffix
        base.mkdir(parents=True, exist_ok=False)
        source = packet(base, suffix)
        summaries.append(process_saved(source, base))
    if negative:
        summaries[1]['signal_source_sha256'] = 'stale-original-signal'
    receipt = audit_pair(comparison, *summaries)
    output.write_text(json.dumps({'comparison_id': comparison, 'receipt': receipt,
                                   'provenance_kind': 'synthetic_fixture',
                                   'physical_acceptance_claimed': False}, sort_keys=True) + '\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    run(args.comparison, args.scratch, args.output, args.negative)
