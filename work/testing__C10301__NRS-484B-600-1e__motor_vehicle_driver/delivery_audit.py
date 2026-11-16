"""Independent CPU boundary proof for C10301 saved diagnostic sources.

This validates source integrity and physical-check provenance. A diagnostic
fixture can pass this software audit while its physical checks remain not_met.
"""

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
sys.path.insert(0, str(HERE))

from diagnostic_comparison_audit import _check_trace_dynamics
from source_delivery_audit import CAMERAS, audit as audit_sources


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(case_id, attempt):
    attempt = Path(attempt)
    result_path = attempt / 'result.json'
    if not result_path.is_file():
        raise ValueError('Missing sealed result')
    result = json.loads(result_path.read_text())
    if result.get('case_id') != case_id:
        raise ValueError('Saved result case identity differs')
    source = audit_sources(attempt, case_id)
    _check_trace_dynamics(attempt)
    checks = result.get('physical_checks')
    if not isinstance(checks, dict) or not {'setup', 'target', 'maneuver', 'attempt'} <= checks.keys():
        raise ValueError('Missing independent physical checks')
    for name, check in checks.items():
        if check.get('status') not in ('met', 'not_met', 'unverified'):
            raise ValueError('Invalid physical check status: ' + name)
        for ref, digest in check.get('sources', {}).items():
            path = attempt / ref
            if not path.is_file() or sha(path) != digest:
                raise ValueError('Physical completion source changed: ' + ref)
    if result.get('physical_acceptance_claimed') or result.get('legal_acceptance_claimed'):
        raise ValueError('Diagnostic asserted physical or legal acceptance')
    return {'format': 'worker-c10301-delivery-diagnostic-audit',
            'case_id': case_id, 'software_source_integrity_passed': True,
            'source_frame_count': source['source_frame_count'],
            'sampled_peak_speed_mph': source['sampled_peak_speed_mph'],
            'physical_check_statuses': {name: check['status'] for name, check in checks.items()},
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--mode', choices=('positive', 'negative'), required=True)
    args = parser.parse_args()
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next((row for row in manifest['cases'] if row['case_id'] == args.case), None)
    if entry is None:
        raise ValueError('Unknown selected case')
    receipt_path = HERE / entry['saved_processing']['receipt']
    if sha(receipt_path) != entry['saved_processing']['sha256']:
        raise ValueError('Saved processing receipt changed')
    receipt = json.loads(receipt_path.read_text())
    if (receipt.get('case_id') != args.case or not receipt.get('passed')
            or not receipt.get('recorded_only') or not receipt.get('originals_preserved')):
        raise ValueError('Saved processing boundary differs')
    attempt = Path(receipt['analysis_directory'])
    if sha(attempt / 'result.json') != receipt['result_sha256']:
        raise ValueError('Saved result hash changed')
    if args.mode == 'positive':
        print(json.dumps(audit(args.case, attempt), sort_keys=True))
        return
    with tempfile.TemporaryDirectory(prefix='c10301-delivery-negative-') as temporary:
        altered = Path(temporary)
        for name in ('config.json', 'result.json', 'subject_motion.jsonl',
                     'video_frames.jsonl', 'trace.jsonl', 'road_context.json',
                     'capture/evidence.jsonl', *CAMERAS):
            path = altered / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if name != 'overview.mkv':
                path.symlink_to(attempt / name)
        audit(args.case, altered)
    raise AssertionError('Missing source camera was accepted')


if __name__ == '__main__':
    main()
