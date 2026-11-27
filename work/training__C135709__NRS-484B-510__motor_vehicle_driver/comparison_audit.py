"""Independent exact-case controlled-request and source-proof comparison audit."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from capture_plan import build


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(comparison_id, tamper=False):
    plan = json.loads((HERE / 'case-plan.json').read_text())
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    matches = [c for c in plan['comparisons'] if c['comparison_id'] == comparison_id]
    if len(matches) != 1 or len(matches[0]['case_ids']) != 2:
        raise ValueError('Select one exact two-case comparison')
    case_ids = matches[0]['case_ids']
    entries = [next(e for e in manifest['cases'] if e['case_id'] == cid) for cid in case_ids]
    suffixes = [cid.rsplit('__', 1)[-1] for cid in case_ids]
    requests = [build(s) for s in suffixes]
    if tamper:
        requests[1]['parking_target_center_x_m'] += 1.0
    variable = {'witness_comparison': 'requested_purpose',
                'exception_1_comparison': 'waiting_vehicle_request',
                'stop_stand_comparison': 'departure_frame',
                'stand_park_comparison': 'departure_frame'}[comparison_id.rsplit('__', 1)[-1]]
    shared = ('frozen_cell', 'actor', 'frames', 'fps', 'duration_s', 'camera_sizes',
              'zone_x0_m', 'zone_x1_m', 'requested_zone_bounds_m', 'requested_sign_id',
              'requested_open_drive_sha256', 'parking_target_center_x_m',
              'passenger_exchange_request', 'waiting_vehicle_request', 'requested_purpose',
              'departure_frame')
    if requests[0][variable] == requests[1][variable]:
        raise ValueError('Comparison did not change its declared request')
    if any(requests[0][key] != requests[1][key] for key in shared if key != variable):
        raise ValueError('Undeclared comparison difference')
    hashes = {}
    for suffix, entry in zip(suffixes, entries):
        capture_path = HERE / 'selected-source' / suffix / 'capture-manifest.json'
        capture = json.loads(capture_path.read_text())
        if capture.get('case_id') != entry['case_id'] or capture.get('source_kind') != 'synthetic_fixture' or not capture.get('closed'):
            raise ValueError('Comparison source capture incomplete')
        for label, field in (('public', 'compatibility'), ('saved', 'post_capture')):
            spec = entry.get(field, {})
            path = HERE / spec.get('receipt' if label == 'public' else 'processing_receipt', '')
            digest = spec.get('sha256' if label == 'public' else 'processing_receipt_sha256')
            if not path.is_file() or sha(path) != digest:
                raise ValueError('Comparison ' + label + ' proof changed')
            hashes[suffix + '_' + label] = digest
        hashes[suffix + '_capture'] = sha(capture_path)
    return {'comparison_id': comparison_id, 'case_ids': case_ids,
            'declared_request_difference': variable, 'fixed_requests_verified': True,
            'diagnostic_only': True, 'physical_acceptance': False, 'legal_verdict': None,
            'source_hashes': hashes}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--tamper', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.comparison, args.tamper), sort_keys=True))
