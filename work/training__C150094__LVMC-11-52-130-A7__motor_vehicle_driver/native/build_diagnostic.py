"""Build a source-shaped, synthetic driveway fixture for CPU compatibility."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parents[1]
AID = ROOT.name
COUNT = 600
VARIANTS = {'01': {'gap_m': 2.0, 'authority': False},
            '02': {'gap_m': 1.2, 'authority': False},
            '03': {'gap_m': 1.2, 'authority': True},
            '04': {'gap_m': 1.524, 'authority': False},
            '05': {'gap_m': 0.0, 'authority': False},
            '06': {'gap_m': 1.2, 'authority': False, 'driveway_kind': 'public'},
            '07': {'gap_m': 1.2, 'authority': True, 'authority_role': 'controller'},
            '08': {'gap_m': 1.2, 'authority': True, 'authority_role': 'family_member'},
            '09': {'gap_m': 1.2, 'authority': True, 'authority_role': 'invitee'},
            '10': {'gap_m': 1.2, 'authority': False, 'usps_official_business': True},
            '11': {'gap_m': 1.2, 'authority': False, 'operator_action': 'stop'},
            '12': {'gap_m': 1.2, 'authority': False, 'operator_action': 'stand'},
            '13': {'gap_m': 1.2, 'authority': False, 'exception_fact': 'necessary_to_avoid_traffic_conflict'},
            '14': {'gap_m': 1.2, 'authority': False, 'exception_fact': 'complying_with_law'},
            '15': {'gap_m': 1.2, 'authority': False, 'exception_fact': 'officer_direction'},
            '16': {'gap_m': 1.2, 'authority': False, 'exception_fact': 'traffic_device_direction'}}


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def lines(items):
    return ''.join(json.dumps(item, separators=(',', ':'), allow_nan=False) + '\n'
                   for item in items)


def main(probe):
    if probe not in VARIANTS:
        raise ValueError('Unknown frozen driveway probe')
    variant = VARIANTS[probe]
    case = AID + '__probe_' + probe
    station = 54.5 if probe == '05' else 53.0 + 2.0 + variant['gap_m']
    reference = REPO / 'work/training__C262666__NRS-484B-363-1__heavy_vehicle_driver/native/selected-generator-probe_03.json'
    base = json.loads(reference.read_text())
    files = dict(base['files'])
    old_context = json.loads(files.pop('school_zone_context.json'))
    camera_hashes = old_context['camera_sha256']
    context = {'assignment_id': AID, 'case_id': case,
               'review_kind': 'synthetic_diagnostic',
               'reviewer': 'synthetic CPU diagnostic, not driveway authority',
               'camera_sha256': camera_hashes,
               'driveway_boundary_source': 'synthetic curb interval',
               'vehicle_extent_source': 'synthetic Native bbox',
               'parking_state_source': 'synthetic brake and velocity trace',
               'private_driveway_authority_source': 'synthetic authority declaration',
               'usps_official_business_source': 'synthetic USPS declaration',
               'traffic_conflict_source': 'synthetic traffic context',
               'lawful_direction_source': 'synthetic law and direction context',
               'driveway_curb_interval_m': [50.0, 53.0],
               'driveway_kind': variant.get('driveway_kind', 'private'),
               'owner_controller_family_invitee': variant['authority'],
               'private_driveway_authority_role': variant.get('authority_role', 'owner' if variant['authority'] else 'none'),
               'usps_vehicle': variant.get('usps_official_business', False),
               'usps_official_business': variant.get('usps_official_business', False),
               'necessary_to_avoid_traffic_conflict': False,
               'complying_with_law': False, 'officer_direction': False,
               'traffic_device_direction': False}
    if 'operator_action' in variant:
        context['vehicle_action'] = variant['operator_action']
        context['vehicle_action_source'] = 'synthetic operator command'
    if 'exception_fact' in variant:
        fact = variant['exception_fact']
        context[fact] = True
        source = {'necessary_to_avoid_traffic_conflict': 'traffic_conflict_source',
                  'complying_with_law': 'applicable_law_source',
                  'officer_direction': 'officer_direction_source',
                  'traffic_device_direction': 'traffic_device_direction_source'}[fact]
        context[source] = 'synthetic source declaration for ' + fact
    files['driveway_context.json'] = json.dumps(context, separators=(',', ':')) + '\n'
    files.pop('native_motion.jsonl', None)
    files['native_parking_trace.jsonl'] = lines({
        'video_frame': i, 'native_frame': 100 + i,
        'source_kind': 'synthetic_native_sample',
        'ego_curb_station_m': station, 'ego_half_length_m': 2.0,
        'ego_speed_mps': 0.0,
        'park_brake_engaged': 'operator_action' not in variant}
        for i in range(COUNT))
    core = [json.loads(s) for s in files['trace.jsonl'].splitlines() if s]
    evidence = [json.loads(s) for s in files['capture/evidence.jsonl'].splitlines() if s]
    for row, item in zip(core, evidence):
        row['position']['y'] = station
        row['position_m'][1] = station
        row['speed_mps'] = 0.0
        row['speed_mph'] = 0.0
        row['velocity_mps'] = [0.0, 0.0, 0.0]
        row['control'] = {'throttle': 0.0, 'brake': 1.0,
                          'hand_brake': 'operator_action' not in variant}
        item['ego']['position_m'][1] = station
        item['ego']['speed_mps'] = 0.0
        item['ego']['body_vertices_m'] = [[1.0, station-2, 0], [1.0, station-2, 1.5],
                                          [2.5, station-2, 0], [2.5, station-2, 1.5],
                                          [2.5, station+2, 0], [2.5, station+2, 1.5],
                                          [1.0, station+2, 0], [1.0, station+2, 1.5]]
        item['world']['road_projection']['s_m'] = station
    files['trace.jsonl'] = lines(core)
    files['capture/evidence.jsonl'] = lines(evidence)
    capture_manifest = json.loads(files['capture/manifest.json'])
    capture_manifest['sources']['trace.jsonl'] = sha_bytes(files['trace.jsonl'].encode())
    files['capture/manifest.json'] = json.dumps(capture_manifest, separators=(',', ':')) + '\n'
    source = {'files': files, 'graphs': base['graphs'], 'videos': base['videos']}
    spec_path = HERE / ('selected-generator-probe_' + probe + '.json')
    spec_path.write_text(json.dumps(source, separators=(',', ':')) + '\n')
    anchor = HERE / ('diagnostic-anchor-probe_' + probe + '.json')
    anchor.write_text(json.dumps({'assignment_id': AID, 'case_id': case,
                                  'scope': 'synthetic diagnostic only'},
                                 separators=(',', ':')) + '\n')
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': anchor.name,
                           'source': str(anchor.relative_to(REPO)),
                           'sha256': sha_bytes(anchor.read_bytes())}],
              'generator': {'source': str(spec_path.relative_to(REPO)),
                            'sha256': sha_bytes(spec_path.read_bytes())}}
    recipe_path = HERE / ('selected-recipe-probe_' + probe + '.json')
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
    print(json.dumps({'generator_bytes': spec_path.stat().st_size,
                      'generator_sha256': recipe['generator']['sha256']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', choices=sorted(VARIANTS), default='02')
    main(parser.parse_args().probe)
