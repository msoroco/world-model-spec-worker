"""Run exact offline checks for selected source-deferred production candidates."""
from pathlib import Path

from prove_fallback_offline import HERE, ROOT, prove


if __name__ == '__main__':
    prove(manifest_path=HERE / 'execution-manifest.json',
          scratch=ROOT / '.runtime-work/c150153-owner/deferred-offline',
          prefix='cpu-deferred-offline-',
          expected_status='original_reviewed_site_required_at_capture')
