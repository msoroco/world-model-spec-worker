"""CPU-only positive, incomplete and missing source parking probes."""

import argparse
import hashlib
import json
from pathlib import Path

from city_space import CASES
from physical_completion import assess, verify_lifecycle, EVENTS
from source_packet import ASSIGNMENT

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(case_name, kind):
    case = next((item for item in CASES if item.name == case_name), None)
    if case is None or kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('unknown physical CPU probe')
    spec = json.loads((ROOT / 'diagnostics' / case_name / 'diagnostic.json').read_text())
    scene = json.loads(spec['files']['city-space-context.json'])['scene']
    rows = [json.loads(line) for line in spec['files']['original-city-space.jsonl'].splitlines()]
    if kind == 'incomplete_motion':
        rows[3]['speed_mps'] = 1.0
    if kind == 'missing_evidence':
        rows = []
    status = assess(rows, scene, case, diagnostic_frames=9)
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    if status['status'] != expected:
        raise ValueError('physical probe did not distinguish observed outcome')
    return {'format': 'c229439-physical-cpu-probe-v1',
            'case_id': ASSIGNMENT + '__' + case_name,
            'provenance_kind': 'synthetic_fixture',
            'diagnostic_fixture': True,
            'maneuver_completed': status['status'] == 'met',
            'physical_checks': {'maneuver': {
                'status': status['status'], 'method': 'source-bound parked interval and complete footprint',
                'sources': status['sources'] or {
                    'diagnostic_fixture_sha256': sha(ROOT / 'diagnostics' / case_name / 'diagnostic.json'),
                    'original_city_space': 'deliberately omitted in missing-evidence probe'},
                'reason': status['reason']}},
            'realized_observables': status.get('realized_observables', {})}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.kind == 'lifecycle':
        verify_lifecycle(EVENTS)
        payload = {'events': list(EVENTS), 'exit_code': 0}
    else:
        payload = run(args.case, args.kind)
    args.output.write_text(json.dumps(payload, indent=2) + '\n')
    print(json.dumps({'case': args.case, 'kind': args.kind, 'passed': True}))


if __name__ == '__main__':
    main()
