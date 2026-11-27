"""Compare two independently recorded, source-sealed original attempts.

This is a source and observed-state comparison, not physical or legal acceptance.
Diagnostic attempts require an explicit flag and cannot satisfy the production path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from parking import audit_saved_attempt, measure_original_history

ROOT = Path(__file__).resolve().parent
FIELDS = {
    'device_effective_time': 'device_effective',
    'traffic_conflict_exception': 'traffic_conflict',
    'law_direction_exception': 'law_direction',
    'police_direction_exception': 'police_direction',
    'device_direction_exception': 'device_direction',
    'prohibited_halt_mode': 'prohibited_halt_mode',
}
EXCEPTIONS = ('traffic_conflict', 'law_direction', 'police_direction', 'device_direction')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_sealed(root, name, refs):
    ref = refs.get(name)
    require(isinstance(ref, dict) and ref.get('path') == name,
            'missing exact original source reference: ' + name)
    path = root / name
    require(path.is_file(), 'missing original source: ' + name)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    require(digest == ref.get('sha256'), 'original source hash mismatch: ' + name)
    return json.loads(raw), digest


def load_attempt(path, case_id, diagnostic):
    root = Path(path).resolve()
    require(root.is_dir(), 'original attempt directory missing')
    attempt_path = root / 'attempt.json'
    require(attempt_path.is_file(), 'original attempt manifest missing')
    attempt = json.loads(attempt_path.read_text())
    require(attempt.get('case_id') == case_id, 'wrong exact comparison case')
    required_format = 'synthetic_diagnostic' if diagnostic else 'native_original'
    require(attempt.get('source_format') == required_format,
            'original Native source format required' if not diagnostic else
            'explicit diagnostic source format required')
    require(attempt.get('frame_count') == 900, '900 original frames required')
    if not diagnostic:
        require(attempt.get('fps') == 20, 'original 20 Hz profile required')
    refs = attempt.get('source_context')
    require(isinstance(refs, dict) and set(refs) == {
        'site-source.json', 'device-source.json', 'actor_rows.json'},
        'site, device and actor source references required')
    site, site_sha = read_sealed(root, 'site-source.json', refs)
    device, device_sha = read_sealed(root, 'device-source.json', refs)
    rows, rows_sha = read_sealed(root, 'actor_rows.json', refs)
    require(site.get('cell_id') == 'C229439', 'wrong reviewed road cell')
    require(device.get('device_id') == attempt.get('device_id') and
            device.get('exact_instruction') == attempt.get('device_instruction') and
            device.get('governed_polygon') == site.get('parking_polygon') ==
            attempt.get('parking_polygon'), 'device/site/attempt source join differs')
    require(all(device.get(k) for k in ('authority_source', 'placement_source',
            'traffic_purpose_source', 'legal_consistency_source')),
            'official device review incomplete')
    expected = {key: attempt[key] for key in ('frame_count', 'first_frame',
        'case_id', 'subject_id', 'device_id', 'device_instruction',
        'parking_polygon', 'halt_action')}
    measured = measure_original_history(rows, expected)
    require(measured['halt_inside_frames'] > 0, 'no observed governed halt')
    if not diagnostic:
        require(not site.get('diagnostic_fixture') and
                not device.get('diagnostic_fixture'), 'diagnostic sources in original attempt')
        require(site.get('native_opendrive_sha256'), 'original map hash missing')
        audit_saved_attempt(attempt, root)
        vehicle_path = root / 'vehicle-source.json'
        require(vehicle_path.is_file(), 'original vehicle source missing')
        vehicle = json.loads(vehicle_path.read_text())
        require(vehicle.get('blueprint') and vehicle.get('vehicle_class_source') and
                vehicle.get('driver_identity_source'), 'reviewed driver vehicle source incomplete')
    else:
        vehicle = None
    return {'root': root, 'attempt': attempt, 'site': site, 'device': device,
            'vehicle': vehicle, 'rows': rows, 'measured': measured,
            'hashes': {'attempt.json': hashlib.sha256(attempt_path.read_bytes()).hexdigest(),
                       'site-source.json': site_sha, 'device-source.json': device_sha,
                       'actor_rows.json': rows_sha}}


def audit(comparison_id, left_path, right_path, *, diagnostic=False):
    require(Path(left_path).resolve() != Path(right_path).resolve(),
            'comparison requires independent attempts')
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    entry = next((e for e in plan['comparisons'] if e['comparison_id'] == comparison_id), None)
    require(entry is not None and comparison_id in FIELDS, 'unknown exact comparison')
    left, right = [load_attempt(path, case, diagnostic) for path, case in
                   zip((left_path, right_path), entry['case_ids'])]
    require(left['root'] != right['root'], 'comparison requires independent attempts')
    for key in ('map_name', 'native_opendrive_sha256', 'parking_polygon',
                'approach_waypoints'):
        require(left['site'].get(key) == right['site'].get(key),
                'matched road/route condition differs: ' + key)
    if not diagnostic:
        for key in ('blueprint', 'vehicle_class_source', 'driver_identity_source'):
            require(left['vehicle'].get(key) == right['vehicle'].get(key),
                    'matched vehicle/driver source differs: ' + key)
    device_fixed = ('governed_polygon',) if comparison_id == 'prohibited_halt_mode' else (
        'exact_instruction', 'governed_polygon', 'prohibited_actions')
    for key in device_fixed:
        require(left['device'].get(key) == right['device'].get(key),
                'matched device instruction differs: ' + key)
    if comparison_id == 'prohibited_halt_mode':
        require(left['device']['exact_instruction'] != right['device']['exact_instruction'],
                'deliberate source difference absent: matching instruction')
    field = FIELDS[comparison_id]
    paired = list(zip(left['rows'], right['rows']))
    require(len(paired) == 900, 'matched original frame count differs')
    changed = 0
    matched = 0
    for index, (a, b) in enumerate(paired):
        require(abs((a['time_s'] - left['rows'][0]['time_s']) -
                    (b['time_s'] - right['rows'][0]['time_s'])) <= 0.001,
                'relative original frame cadence differs')
        if comparison_id != 'prohibited_halt_mode':
            require(a['halt_activity'] == b['halt_activity'],
                    'matched observed halt activity differs')
            require(a['prohibited_actions'] == b['prohibited_actions'],
                    'matched prohibited actions differ')
        elif a['halt_activity'] in ('stop', 'stand') or b['halt_activity'] in ('stop', 'stand'):
            require(a['halt_activity'] == left['attempt']['halt_action'] and
                    b['halt_activity'] == right['attempt']['halt_action'] and
                    a['prohibited_actions'] == [a['halt_activity']] and
                    b['prohibited_actions'] == [b['halt_activity']] and
                    a['device_instruction'] == left['device']['exact_instruction'] and
                    b['device_instruction'] == right['device']['exact_instruction'],
                    'observed halt and sign instruction do not match')
        for other in EXCEPTIONS:
            if other != field:
                require(a[other] == b[other],
                        'non-deliberate exception differs: ' + other)
        if field != 'device_effective':
            require(a['device_effective'] == b['device_effective'],
                    'non-deliberate effective state differs')
        if (a['halt_activity'] == left['attempt']['halt_action'] and
                b['halt_activity'] == right['attempt']['halt_action']):
            matched += 1
            changed += (a['halt_activity'] != b['halt_activity'] and
                        a['prohibited_actions'] != b['prohibited_actions'] and
                        a['device_instruction'] != b['device_instruction']) if (
                            comparison_id == 'prohibited_halt_mode') else a[field] != b[field]
    require(matched > 0, 'no matched observed halt frames')
    require(changed > 0, 'deliberate source difference absent: ' + field)
    return {'comparison_id': comparison_id, 'case_ids': entry['case_ids'],
            'attempt_directories': [str(left['root']), str(right['root'])],
            'source_sha256': [left['hashes'], right['hashes']],
            'matched_halt_frames': matched, 'different_halt_frames': changed,
            'deliberate_field': field, 'source_format': 'synthetic_diagnostic' if diagnostic
                else 'native_original', 'physical_acceptance': False,
            'legal_judgment': None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True, choices=FIELDS)
    parser.add_argument('--left-attempt', required=True)
    parser.add_argument('--right-attempt', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    result = audit(args.comparison, args.left_attempt, args.right_attempt,
                   diagnostic=args.diagnostic)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'comparison_id': args.comparison,
                      'different_halt_frames': result['different_halt_frames']}))


if __name__ == '__main__':
    main()
