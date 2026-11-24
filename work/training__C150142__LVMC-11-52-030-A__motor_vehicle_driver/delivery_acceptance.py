"""Independent CPU preparation check for all selected red-curb deliveries.

The source audit below uses synthetic saved samples. Original pixels and physical
completion must still be reviewed after a Native capture.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_audit():
    path = HERE / 'audit-current-all-selected-delivery.py'
    spec = importlib.util.spec_from_file_location('selected_delivery_source', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.audit()


def check(missing_source=False):
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    selected = {item['case_id'] for item in manifest['cases']}
    if len(selected) != 30:
        raise ValueError('Selected exact-case delivery coverage incomplete')
    report = source_audit()
    if not report['passed'] or report['selected_cases'] != len(selected) or \
            report['manifest_sha256'] != sha(manifest_path):
        raise ValueError('Independent selected source audit is stale or incomplete')
    if report['source_kind'] != 'synthetic_native_sample' or \
            report['original_native_observed'] or report['physical_acceptance_claimed'] or \
            report['legal_acceptance_claimed']:
        raise ValueError('Synthetic source cannot establish physical or legal acceptance')
    if missing_source:
        raise ValueError('Missing independent original Native and physical acceptance source')
    return {'format': 'c150142-delivery-acceptance-cpu-preparation-v1',
            'passed': True, 'selected_cases': len(selected),
            'checks': list(CHECKS), 'manifest_sha256': sha(manifest_path),
            'source_audit_sha256': sha(HERE / 'audit-current-all-selected-delivery.py'),
            'source_diagnostic_only': True, 'original_native_observed': False,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--missing-source', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.missing_source), sort_keys=True))
