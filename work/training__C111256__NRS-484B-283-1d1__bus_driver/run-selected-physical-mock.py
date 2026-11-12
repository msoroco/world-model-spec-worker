"""Exercise selected Walk physical outcomes on synthetic source-shaped rows."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from physical_walk_audit import (LIFECYCLE, audit_original, check_lifecycle,
                                 classify, diagnostic_source)
from native.measure_walk import read_rows

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(suffix, kind):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    case_id = HERE.name + '__' + suffix
    entry = next(entry for entry in manifest['cases'] if entry['case_id'] == case_id)
    base = {'case_id': case_id, 'construction_sha256': entry['construction_sha256'],
            'cpu_fixture_mock': True, 'mock_input_provenance': 'synthetic_native_sample',
            'original_native_motion_verified': False, 'original_walk_pixels_verified': False,
            'accepted': False, 'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        events = list(LIFECYCLE)
        assert check_lifecycle(events)['saved_processing_after_owner_release']
        bad = events.copy()
        bad[-2:] = reversed(bad[-2:])
        try:
            check_lifecycle(bad)
        except ValueError:
            pass
        else:
            raise ValueError('Premature saved processing accepted')
        return {**base, 'events': events, 'exit_code': 0,
                'actual_owner_release_verified': False}
    source = ROOT / '.runtime-work/c111256-update017-selected' / suffix / 'primary/fresh-attempt'
    assert diagnostic_source(source, suffix)['status'] == 'met'
    try:
        audit_original(source, suffix, source / 'official-walk-review.json')
    except ValueError as exc:
        assert 'Synthetic source cannot prove original Native Walk motion' in str(exc)
    else:
        raise ValueError('Synthetic Walk source accepted as original')
    names = ('native_samples.jsonl', 'video_frames.jsonl', 'road_geometry.json')
    samples = read_rows(source / names[0])
    mapping = read_rows(source / names[1])
    geometry = json.loads((source / names[2]).read_text())
    if kind == 'incomplete_motion':
        samples = copy.deepcopy(samples)
        for sample in samples:
            sample['pedestrian_body_xy_m'] = [[-5.2, -11.2], [-4.8, -11.2],
                                              [-4.8, -10.8], [-5.2, -10.8]]
    elif kind == 'missing_evidence':
        mapping = mapping[:-1]
    try:
        measured = classify(samples, mapping, geometry, suffix)
        status = measured['status']
    except ValueError:
        if kind != 'missing_evidence':
            raise
        measured, status = {}, 'unverified'
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    assert status == expected, (suffix, kind, status)
    return {**base, 'physical_checks': {'maneuver': {
                'status': status,
                'method': '480-frame synthetic source-shape Walk/bus response classifier',
                'sources': list(names)}},
            'maneuver_completed': status == 'met',
            'realized_observables': measured if status == 'met' else {},
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'mock_native_branch_only': True,
            'original_production_audit_rejected': True,
            'source_sha256': {name: sha(source / name) for name in names}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('reference', 'contrast'), required=True)
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion',
                                          'missing_evidence', 'lifecycle'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = run(args.case, args.kind)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps({'case_id': value['case_id'], 'kind': args.kind,
                      'status': value.get('physical_checks', {}).get('maneuver', {}).get('status'),
                      'cpu_fixture_mock': True, 'original_native_motion_verified': False}))
