"""Run exact offline checks for selected source-deferred production candidates."""
import argparse
from pathlib import Path

from prove_fallback_offline import HERE, ROOT, prove


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--proof-only', action='store_true')
    args = parser.parse_args()
    prove(manifest_path=HERE / 'execution-manifest.json',
          scratch=ROOT / '.runtime-work/c150153-owner/deferred-offline',
          prefix='cpu-deferred-offline-',
          expected_status='original_reviewed_site_required_at_capture',
          proof_only=args.proof_only, reuse=not args.proof_only)
