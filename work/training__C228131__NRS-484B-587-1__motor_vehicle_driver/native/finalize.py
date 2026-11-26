"""Source-bound entry measurement; external authority and legal outcome remain review matters."""
import argparse
import hashlib
import json
from pathlib import Path

from saved_entry import measure

CAMERAS = ('overview', 'approach', 'indicated_gate', 'highway_side')
AUTHORITY = ('access-authority.txt', 'device-authority.txt', 'device-content.txt',
             'device-erection.txt', 'entrance-extent.txt', 'highway-dedication.txt',
             'public-use.txt', 'jurisdiction.txt', 'vehicle-eligibility.txt')
SOURCES = ('road.xodr', 'access-inventory.json', 'access-review.json',
           'device-review.json', 'actor-poses.jsonl', 'video_frames.jsonl',
           'overview.mkv', *AUTHORITY)
CHANNELS = ('st.controlled_access', 'dev.regulatory_sign', 'dev.governs',
            'rel.occupies', 'kin.path_length', 'st.lane_connectivity', 'kin.position')


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def observation(root):
    root = Path(root)
    paths = {name: required(root, name) for name in SOURCES}
    for camera in CAMERAS:
        required(root, camera + '.mkv')
    inventory = json.loads(paths['access-inventory.json'].read_text())
    access = json.loads(paths['access-review.json'].read_text())
    device = json.loads(paths['device-review.json'].read_text())
    diagnostic = (root / 'fixture-provenance.json').is_file()
    expected = 'synthetic_diagnostic' if diagnostic else 'independently_reviewed'
    if access.get('review_status') != expected or device.get('review_status') != expected:
        raise ValueError('Independent access and device reviews required')
    if not access.get('reviewer') or not device.get('reviewer') or access.get('source') == device.get('source'):
        raise ValueError('Access and device review sources must be distinct')
    if inventory.get('source_kind') != 'native_saved_sample' or inventory.get('cell_id') != 'C228131':
        raise ValueError('Native access inventory missing')
    if len(inventory.get('road_survey', [])) != 4 or not inventory.get('subject_id'):
        raise ValueError('Native road or vehicle survey incomplete')
    if access.get('road_sha256') != sha(paths['road.xodr']) or access.get('pose_sha256') != sha(paths['actor-poses.jsonl']):
        raise ValueError('Access review road/pose source differs')
    if device.get('road_sha256') != sha(paths['road.xodr']) or device.get('overview_sha256') not in (sha(paths['overview.mkv']), 'synthetic_rgb_source' if diagnostic else ''):
        raise ValueError('Device review road/pixel source differs')
    for name in AUTHORITY:
        review = access if name in ('access-authority.txt', 'highway-dedication.txt',
                                    'public-use.txt', 'jurisdiction.txt', 'vehicle-eligibility.txt') else device
        if review.get('source_sha256', {}).get(name) != sha(paths[name]):
            raise ValueError('Authority source differs: ' + name)
    if access.get('controlled_access_highway') is not True or device.get('device_official') is not True or device.get('device_erected') is not True:
        raise ValueError('Controlled-access and official-device source claims missing')
    if device.get('device_indicates_entry') is not True or not isinstance(device.get('indicated_entrance_x_interval_m'), list):
        raise ValueError('Indicated entrance source missing')
    poses = rows(paths['actor-poses.jsonl'])
    if len(poses) != 600 or any(p.get('vehicle_id') != inventory['subject_id'] for p in poses):
        raise ValueError('Original vehicle identity or 600-frame history missing')
    context = {'assignment_id': 'training__C228131__NRS-484B-587-1__motor_vehicle_driver',
        'source_kind': 'synthetic_cpu' if diagnostic else 'original_native',
        'road_source_sha256': sha(paths['road.xodr']),
        'controlled_access_designation_sha256': sha(paths['access-authority.txt']),
        'official_device_authority_sha256': sha(paths['device-authority.txt']),
        'device_content_sha256': sha(paths['device-content.txt']),
        'device_erection_sha256': sha(paths['device-erection.txt']),
        'entrance_extent_source_sha256': sha(paths['entrance-extent.txt']),
        'controlled_access_highway': access['controlled_access_highway'],
        'device_official': device['device_official'],
        'device_erected': device['device_erected'],
        'device_indicates_entry': device['device_indicates_entry'],
        'highway_road_id': inventory['highway_road_id_candidate'],
        'highway_edge_y_m': access['highway_edge_y_m'],
        'indicated_entrance_x_interval_m': device['indicated_entrance_x_interval_m']}
    fact = measure(paths['actor-poses.jsonl'].read_bytes(),
                   paths['video_frames.jsonl'].read_bytes(),
                   json.dumps(context).encode(), paths['road.xodr'].read_bytes())
    xs = [row['center_xy_m'][0] for row in poses]
    ys = [row['center_xy_m'][1] for row in poses]
    fact.update(path_length_m=sum(((xs[i]-xs[i-1])**2+(ys[i]-ys[i-1])**2)**.5
                                  for i in range(1, len(xs))),
                source_sha256={name: sha(path) for name, path in paths.items()},
                access_review_status=access['review_status'],
                device_review_status=device['review_status'],
                highway_dedication_source=access['source_sha256']['highway-dedication.txt'],
                public_use_source=access['source_sha256']['public-use.txt'],
                jurisdiction_source=access['source_sha256']['jurisdiction.txt'],
                vehicle_eligibility_source=access['source_sha256']['vehicle-eligibility.txt'],
                legal_outcome='unassessed')
    return fact


def entry_position(root):
    fact = observation(root)
    return {'entry_events': fact['entry_events'], 'path_length_m': fact['path_length_m']}


def controlled_access_context(root):
    fact = observation(root)
    return {key: fact[key] for key in ('highway_road_id', 'highway_dedication_source',
        'public_use_source', 'jurisdiction_source', 'access_review_status')}


def official_device_context(root):
    fact = observation(root)
    return {'device_review_status': fact['device_review_status'],
            'entry_events': fact['entry_events']}


def vehicle_context(root):
    fact = observation(root)
    return {'vehicle_eligibility_source': fact['vehicle_eligibility_source'],
            'frame_count': fact['frame_count']}


def report(root):
    root = Path(root)
    config = json.loads(required(root, 'config.json').read_text())
    fact = observation(root)
    sources = fact['source_sha256']
    items = {'entry_position': ('entry_position', entry_position(root)),
             'controlled_access_context': ('controlled_access_context', controlled_access_context(root)),
             'official_device_context': ('official_device_context', official_device_context(root)),
             'vehicle_context': ('vehicle_context', vehicle_context(root))}
    measurements = {key: {'method': method, 'value': value, 'sources': sources}
                    for key, (method, value) in items.items()}
    return {'format': 'worker-analysis-report-v1', 'case_id': config['case_id'],
            'measurements': measurements, 'scope': 'Original Native entry path and separately sourced access and device context'}


def finalize(root, output):
    from worker_exchange.native_output import physical_result, provenance_record, write_result
    root, output = Path(root), Path(output)
    if output.exists() or (root / 'result.json').exists():
        raise ValueError('Use a fresh finalization stage')
    config = json.loads(required(root, 'config.json').read_text())
    report_data = report(root)
    fact = observation(root)
    if {row['name'] for row in config['recording_description']['channels']} != set(CHANNELS):
        raise ValueError('Declared entry channels differ')
    source_names = fact['source_sha256']
    channel_dir = root / 'channels'
    channel_dir.mkdir(exist_ok=True)
    for name in CHANNELS:
        value = {'source_sha256': source_names, 'measured_entry': fact['entry_events'],
                 'source_review_status': [fact['access_review_status'], fact['device_review_status']],
                 'legal_outcome': 'unassessed'}
        (channel_dir / (name + '.jsonl')).write_text(''.join(
            json.dumps({'time_s': i/20, 'value': value}) + '\n' for i in range(600)))
    intended = config['entry_mode'] == 'witness_1'
    measured = fact['entry_events'][0]['within_indicated_gate']
    target = {'target': 'measured entry point relative to sourced indicated entrance',
              'requested': intended, 'measured': measured, 'method': 'original body/frame/access review join',
              'tolerance': 0, 'matched': intended == measured,
              'physical_cause_confirmed': False, 'cause_evidence': list(SOURCES)}
    evidence = [{'name': name, 'unit': 'source', 'reference': name} for name in SOURCES]
    evidence += [{'name': row['name'], 'unit': row['unit'], 'reference': row['source']}
                 for row in config['recording_description']['channels']]
    result = {'case_id': config['case_id'], 'measured_values': fact,
              'target_checks': [target], 'setup_confirmed': False,
              'behavior_attempted': False, 'maneuver_completed': False,
              'termination_reason': 'Awaiting original physical and official-authority review',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              **provenance_record(root), 'accepted': False, 'legal_verdict_claimed': False}
    physical_result(root, result)
    output.write_text(json.dumps(report_data, indent=2, allow_nan=False) + '\n')
    write_result(root, result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
