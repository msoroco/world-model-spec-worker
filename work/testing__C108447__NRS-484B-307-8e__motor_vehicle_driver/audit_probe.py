"""Six-case synthetic CPU probe for the independent original-attempt auditor.

This intentionally reuses the tiny test fixture generator. Its source claims
are fictional and its pixels are 2x2; no physical acceptance follows.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('test_saved_delivery', BASE / 'tests/test_saved_delivery.py')
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def run(case_id: str, scratch: Path, negative: bool) -> dict:
    if not case_id.startswith('testing__C108447__NRS-484B-307-8e__motor_vehicle_driver__'):
        raise ValueError('Exact assignment case required')
    suffix = case_id.rsplit('__', 1)[1]
    if suffix not in ('private_bypass', 'public_bypass', 'ordinary_crossing',
                      'no_approach_red', 'destination_red', 'other_purpose'):
        raise ValueError('Unknown exact case')
    with tempfile.TemporaryDirectory(dir=scratch, prefix='property-audit-') as temporary:
        fixture = module.SavedDeliveryTests()
        fixture.setUp()
        try:
            root = fixture.root
            trace = json.loads((root / 'trace.json').read_text())
            packet = json.loads((root / 'map.json').read_text())
            authority = json.loads((root / 'original-map.json').read_text())
            trace['case_id'] = case_id
            fixture.bundle['case_id'] = case_id
            fixture.bundle['case'] = fixture.write('case.json', json.dumps({'case_id': case_id}) + '\n')
            if suffix == 'public_bypass':
                packet['properties'][0]['status'] = 'public'
            if suffix == 'ordinary_crossing':
                route = [[-3, -2], [5, -2], [13, -2]]
                packet['roadway_route'] = route
                authority['roadway_route'] = route
                for row in trace['ego']:
                    row['y'] = -2
            if suffix == 'no_approach_red':
                for row in trace['approach_signal_history']:
                    row['state'] = 'green'
                trace['approach_signal']['state'] = 'green'
            if suffix == 'destination_red':
                for row in trace['destination_signal_history']:
                    row['state'] = 'red_alone'
                trace['destination_signal']['state'] = 'red_alone'
            if suffix == 'other_purpose':
                trace['purpose']['value'] = 'other'
            (root / 'original-map.json').write_text(json.dumps(authority) + '\n')
            packet['source']['sha256'] = module.audit.sha((root / 'original-map.json').read_bytes())
            fixture.bundle['map'] = fixture.write('map.json', json.dumps(packet) + '\n')
            fixture.bundle['trace'] = fixture.write('trace.json', json.dumps(trace) + '\n')
            if negative:
                (root / 'original-map.json').unlink()
            result = module.original_delivery.audit(root, fixture.bundle, expected_frames=20)
            return {'case_id': case_id, 'diagnostic_fixture': True,
                    'source_and_pixels': 'passed',
                    'physical_completion': result['physical_completion']['status'],
                    'physical_acceptance_claimed': False}
        finally:
            fixture.doCleanups()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    args.scratch.mkdir(parents=True, exist_ok=True)
    print(json.dumps(run(args.case, args.scratch, args.negative), sort_keys=True))


if __name__ == '__main__':
    main()
