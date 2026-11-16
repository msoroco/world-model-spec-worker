"""Audit draft shuttle synthetic source measurements and fixed case construction."""
import copy
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BOUNDARIES = ('below', 'at', 'above', 'no_loading')
EXPECTED = {
    'below': (36120, 1799.95, 'below', 1),
    'at': (36121, 1800, 'at', 1),
    'above': (36122, 1800.05, 'above', 1),
    'no_loading': (36121, 1800, 'at', 0),
}
VARIABLE = {'capture_frames', 'case_id', 'duration_s', 'frames',
            'requested_boundary', 'requested_stationary_duration_s',
            'selected_case_id', 'stationary_frames', 'supported_case_ids',
            'activity_request'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def load(service='shuttle_bus'):
    if service not in ('shuttle_bus', 'rtc_bus'):
        raise ValueError('Unknown signed-bus service')
    proof = json.loads((ROOT / ('update035-' + ('shuttle' if service == 'shuttle_bus' else 'rtc') +
                                '-all-source-proof.json')).read_text())
    packages = {}
    for boundary in BOUNDARIES:
        case = service + '_' + boundary
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            path = (ROOT / ('selected-primary' if candidate == 'primary' else
                            'selected-fallbacks') / case)
            if candidate != 'primary':
                path /= candidate
            package = json.loads((path / 'construction.json').read_text())
            files = {row['path']: row['content'] for row in package['files']}
            packages[(boundary, candidate)] = {
                'case_id': package['case_id'],
                'config': json.loads(files['config.json']),
                'road_sha256': hashlib.sha256(files['red-curb-road.xodr'].encode()).hexdigest(),
                'tracks_sha256': hashlib.sha256(files['requested-tracks.jsonl'].encode()).hexdigest(),
            }
    return proof, packages


def audit(proof, packages, service='shuttle_bus'):
    require(proof['all_passed'] and len(proof['rows']) == 16,
            'Incomplete shuttle source proof')
    rows = {(r['case'].removeprefix(service + '_'), r['candidate']): r
            for r in proof['rows']}
    require(len(rows) == 16, 'Duplicate shuttle source proof')
    base = packages[('below', 'primary')]
    records = []
    for boundary in BOUNDARIES:
        frames, duration, relative, events = EXPECTED[boundary]
        primary = packages[(boundary, 'primary')]
        config = primary['config']
        changed = {key for key in base['config'].keys() | config.keys()
                   if base['config'].get(key) != config.get(key)}
        require(changed <= VARIABLE and
                primary['road_sha256'] == base['road_sha256'] and
                primary['tracks_sha256'] == base['tracks_sha256'],
                'Fixed shuttle boundary construction differs: ' + boundary)
        require(config['capture_frames'] == frames and
                config['requested_stationary_duration_s'] == duration and
                config['requested_boundary'] == relative and
                config['service_class'] == service and
                config['activity_request'] ==
                (None if boundary == 'no_loading' else 'passenger_loading'),
                'Shuttle boundary request differs: ' + boundary)
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            path = (boundary, candidate)
            item = packages[path]
            row = rows[path]
            observed = row['proof']
            require(row['exit_code'] == 0 and observed is not None and
                    observed['case_id'] == item['case_id'] and
                    observed['candidate'] == candidate and
                    observed['measured_duration_s'] == duration and
                    observed['boundary'] == relative and
                    observed['activity_events'] == events and
                    observed['missing_passenger_source_rejected'] is True and
                    observed['draft_text4_contract_passed'] is True and
                    observed['original_native_observed'] is False,
                    'Shuttle source measurement differs: ' + str(path))
            require(item['road_sha256'] == primary['road_sha256'] and
                    item['config']['capture_frames'] == frames and
                    item['config']['service_class'] == service,
                    'Shuttle fallback changed fixed setup: ' + str(path))
            records.append({'case': boundary, 'candidate': candidate,
                            'duration_s': duration, 'activity_events': events})
        fallbacks = [packages[(boundary, x)]['config']
                     for x in ('fallback1', 'fallback2', 'fallback3')]
        require([(x['requested_target_x_m'], x['camera_policy']) for x in fallbacks]
                == [(38, 'standard'), (40, 'elevated_overview'),
                    (42, 'standard')],
                'Shuttle fallback mechanisms are not distinct: ' + boundary)
    return {'format': ('shuttle' if service == 'shuttle_bus' else 'rtc') +
            '-source-boundary-audit-v1', 'passed': True,
            'source_kind': 'synthetic_native_sample',
            'original_native_observed': False, 'records': records}


def mutations(proof, packages, service='shuttle_bus'):
    audit(proof, packages, service)
    rejected = []
    for name, change in (
        ('wrong_duration', lambda p, c: p['rows'][0]['proof'].__setitem__('measured_duration_s', 1800)),
        ('missing_negative', lambda p, c: p['rows'][0]['proof'].__setitem__('missing_passenger_source_rejected', False)),
        ('changed_road', lambda p, c: c[('at', 'primary')].__setitem__('road_sha256', '0' * 64)),
        ('collapsed_fallback', lambda p, c: c[('below', 'fallback1')]['config'].__setitem__('requested_target_x_m', 40)),
    ):
        copied_proof, copied_packages = copy.deepcopy(proof), copy.deepcopy(packages)
        change(copied_proof, copied_packages)
        try:
            audit(copied_proof, copied_packages, service)
        except ValueError as exc:
            rejected.append({'mutation': name, 'error': str(exc)})
        else:
            raise AssertionError('Shuttle audit accepted mutation: ' + name)
    return rejected


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--service', choices=('shuttle_bus', 'rtc_bus'),
                        default='shuttle_bus')
    args = parser.parse_args()
    proof, packages = load(args.service)
    print(json.dumps({**audit(proof, packages, args.service), 'rejected_mutations':
                      mutations(proof, packages, args.service)}, sort_keys=True))
