"""Mock-only CPU check of exact original delivery audit wiring."""

import argparse
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from delivery_audit import audit_delivery


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def prove(case_id, negative):
    manifest = json.loads((HERE / 'execution-manifest.draft.json').read_text())
    if case_id not in {entry['case_id'] for entry in manifest['cases']}:
        raise ValueError('exact selected 777(1) case required')
    scratch = ROOT / '.runtime-work' / 'c229023-7771-owner-nov26' / 'delivery-mock'
    scratch.mkdir(parents=True, exist_ok=True)
    if negative:
        audit_delivery(scratch / 'absent-original-attempt',
                       scratch / 'absent-analysis-report.json')
        raise ValueError('missing original attempt was accepted')
    with tempfile.TemporaryDirectory(dir=scratch, prefix='mock-only-audit-') as tmp:
        root = Path(tmp)
        (root / 'original-sources.json').write_text('{"mock_only":true}\n')
        (root / 'video_frames.jsonl').write_text('{"mock_only":true}\n')
        measured = {'frame_count': 900, 'initial_relative_station_m': -10.0,
                    'terminal_relative_station_m': 8.0,
                    'minimum_surface_clearance_m': 0.25,
                    'minimum_right_edge_distance_m': 0.75}
        report = {'format': 'worker-analysis-report', 'case_id': case_id,
                  'analysis_complete': True, 'physical_acceptance_claimed': False,
                  'legal_verdict_claimed': False,
                  'measurements': {'right_side_req_0': {
                      'method': 'measure_case', 'sources': ['mock-only'],
                      'value': measured}}}
        path = root / 'analysis-report.json'
        path.write_text(json.dumps(report) + '\n')
        with patch('delivery_audit.original', return_value=(report, {})) as source, \
             patch('delivery_audit.decode_camera', return_value={
                 'frames': 900, 'rgb_sequence_sha256': 'MOCK ONLY'}) as decode:
            result = audit_delivery(root, path)
            source.assert_called_once()
            if (decode.call_count != 4 or result['original_frame_count'] != 900 or
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
