"""Measure synthetic flagger motion outcomes without physical or legal claims."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from flagger_zone import CASES, measure_original
from source_packet import ASSIGNMENT, verify

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(case_id, kind):
    case = next((item for item in CASES if case_id == ASSIGNMENT + '__' + item.name), None)
    if case is None or kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('exact physical probe selection differs')
    source = HERE / 'cases' / case.name / 'diagnostic-sources/original-flagger-source'
    packet_path = source / 'source-packet.json'
    checked = verify(packet_path, diagnostic_fixture=True)
    scene = json.loads(packet_path.read_text())['scene']
    source_path = source / 'original-ticks.jsonl'
    rows = [json.loads(line) for line in source_path.read_text().splitlines()]
    if checked['case_id'] != case_id:
        raise ValueError('source case differs')
    if kind == 'incomplete_motion':
        for row in rows[scene['signal_frame']:scene['release_frame']]:
            row['vehicle_speed_mps'] = 1.0 if case.response == 'stop' else 0.0
    elif kind == 'missing_evidence':
        rows.pop(4)
    measured = None
    failure = None
    try:
        measured = measure_original(rows, scene, case, expected_frames=9)
    except ValueError as error:
        failure = str(error)
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    if (expected == 'met') != (measured is not None):
        raise ValueError('diagnostic physical outcome differs')
    if expected == 'not_met' and (failure is None or 'not physically realized' not in failure):
        raise ValueError('incomplete motion did not fail response measurement')
    if expected == 'unverified' and (failure is None or 'frame-count' not in failure):
        raise ValueError('missing original sample was not rejected')
    sources = {'source_packet_sha256': sha(packet_path), 'original_ticks_sha256': sha(source_path)}
    return {'format': 'c230235-physical-probe-v1', 'case_id': case_id,
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
            'maneuver_completed': expected == 'met',
            'physical_checks': {'maneuver': {'status': expected,
                                             'method': 'flagger_zone.measure_original on source-hashed nine-frame CPU fixture',
                                             'sources': sources, 'failure': failure}},
            'realized_observables': ({'maximum_active_speed_mps': measured['maximum_active_speed_mps'],
                                      'active_signal_frames': measured['active_signal_frames']}
                                     if measured else {})}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.case, args.kind)
    args.output.write_text(json.dumps(result, sort_keys=True, separators=(',', ':')) + '\n')
    print(args.case, args.kind, result['physical_checks']['maneuver']['status'])
