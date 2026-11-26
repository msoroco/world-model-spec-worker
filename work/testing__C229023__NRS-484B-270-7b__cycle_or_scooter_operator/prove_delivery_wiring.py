"""Mock-only CPU audit wiring for exact delivery and missing-source rejection."""

import argparse
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from audit import audit_delivery

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def prove(case_id, negative):
    manifest = json.loads((HERE / 'execution-manifest.draft.json').read_text())
    if case_id not in {entry['case_id'] for entry in manifest['cases']}:
        raise ValueError('exact selected cycle/motor case required')
    scratch = ROOT / '.runtime-work' / 'c229023-owner' / 'delivery-mock'
    scratch.mkdir(parents=True, exist_ok=True)
    if negative:
        audit_delivery(scratch / 'absent-original-attempt',
                       scratch / 'absent-analysis-report.json')
        raise ValueError('missing original attempt was accepted')
    with tempfile.TemporaryDirectory(dir=scratch, prefix='mock-only-audit-') as tmp:
        root = Path(tmp)
        (root / 'original-sources.json').write_text('{"mock_only":true}\n')
        (root / 'video_frames.jsonl').write_text('{"mock_only":true}\n')
        report = {'format': 'worker-analysis-report', 'case_id': case_id,
                  'physical_acceptance_claimed': False,
                  'legal_verdict_claimed': False,
                  'measurements': {'cycle_motor_pass': {'value': {
                      'frame_count': 900, 'initial_relative_station_m': -10,
                      'minimum_surface_clearance_m': 0.3}}}}
        path = root / 'analysis-report.json'
        path.write_text(json.dumps(report) + '\n')
        with patch('audit.build', return_value=(report, {})) as measured, \
             patch('audit.decode_camera', return_value={
                 'frames': 900, 'rgb_sequence_sha256': 'MOCK ONLY'}) as decoded:
            result = audit_delivery(root, path)
            measured.assert_called_once()
            if (decoded.call_count != 4 or result['original_frame_count'] != 900 or
                    result['physical_acceptance_claimed'] is not False or
                    result['legal_verdict_claimed'] is not False):
                raise ValueError('mock-only delivery audit wiring changed')
    return 'mock-only delivery audit wiring passed: ' + case_id


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--negative-missing-attempt', action='store_true')
    args = parser.parse_args()
    try:
        print(prove(args.case, args.negative_missing_attempt))
    except (ValueError, FileNotFoundError) as error:
        print(str(error))
        raise SystemExit(2)
