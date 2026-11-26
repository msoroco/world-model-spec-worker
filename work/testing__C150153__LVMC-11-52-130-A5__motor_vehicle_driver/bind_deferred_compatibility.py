"""Bind pinned positive and negative receipts to selected deferred candidates."""
from pathlib import Path

from bind_fallback_compatibility import HERE, bind


if __name__ == '__main__':
    bind(manifest_path=HERE / 'execution-manifest.json',
         expected_status='original_reviewed_site_required_at_capture',
         output_prefix='deferred-compat-', saved_prefix='cpu-deferred-')
