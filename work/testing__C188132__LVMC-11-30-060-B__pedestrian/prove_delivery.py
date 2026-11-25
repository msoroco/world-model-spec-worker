"""CPU fixture proof for production delivery rejection and review bindings."""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import unittest
from pathlib import Path

from delivery_audit import audit
from overpass_source import ASSIGNMENT, CASES

HERE = Path(__file__).resolve().parent
SAFE = (HERE.parents[1] / '.runtime-work').resolve()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--self-test', action='store_true')
    group.add_argument('--negative-missing-seal', action='store_true')
    args = parser.parse_args()
    if args.case not in {ASSIGNMENT + '__' + variant for variant in CASES}:
        raise ValueError('wrong exact case')
    output_root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
    if not output_root.is_relative_to(SAFE):
        raise ValueError('SCENARIO_PIPELINE_OUTPUT_ROOT must be under .runtime-work')
    if args.self_test:
        suite = unittest.defaultTestLoader.discover(str(HERE / 'tests'), pattern='test_delivery_audit.py')
        result = unittest.TextTestRunner(stream=sys.stdout, verbosity=1).run(suite)
        if not result.wasSuccessful():
            raise SystemExit(1)
        print('Exact case ' + args.case + ': synthetic CPU audit contract passed; no physical acceptance claimed')
        return
    with tempfile.TemporaryDirectory(dir=SAFE, prefix='c188132-negative-audit-') as temporary:
        root = Path(temporary)
        audit(root, pixel_review=root / 'original-pixel-review.json',
              processing_receipt=root / 'processing.json')


if __name__ == '__main__':
    main()
