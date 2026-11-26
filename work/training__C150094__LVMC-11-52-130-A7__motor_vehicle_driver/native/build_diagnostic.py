"""Build a source-shaped, synthetic driveway fixture for CPU compatibility."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parents[1]
AID = ROOT.name
CASE = AID + '__probe_02'
COUNT = 600


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def lines(items):
    return ''.join(json.dumps(item, separators=(',', ':'), allow_nan=False) + '\n'
                   for item in items)


def main():
    reference = REPO / 'work/training__C262666__NRS-484B-363-1__heavy_vehicle_driver/native/selected-generator-probe_03.json'
    base = json.loads(reference.read_text())
    files = dict(base['files'])
    old_context = json.loads(files.pop('school_zone_context.json'))
    camera_hashes = old_context['camera_sha256']
    context = {'assignment_id': AID, 'case_id': CASE,
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
               'driveway_kind': 'private',
               'owner_controller_family_invitee': False,
               'usps_vehicle': False, 'usps_official_business': False,
               'necessary_to_avoid_traffic_conflict': False,
               'complying_with_law': False, 'officer_direction': False,
               'traffic_device_direction': False}
    files['driveway_context.json'] = json.dumps(context, separators=(',', ':')) + '\n'
    files.pop('native_motion.jsonl', None)
    files['native_parking_trace.jsonl'] = lines({
        'video_frame': i, 'native_frame': 100 + i,
        'source_kind': 'synthetic_native_sample',
        'ego_curb_station_m': 56.2, 'ego_half_length_m': 2.0,
        'ego_speed_mps': 0.0, 'park_brake_engaged': True}
        for i in range(COUNT))
    core = [json.loads(s) for s in files['trace.jsonl'].splitlines() if s]
    evidence = [json.loads(s) for s in files['capture/evidence.jsonl'].splitlines() if s]
    for row, item in zip(core, evidence):
        row['position']['y'] = 56.2
        row['position_m'][1] = 56.2
        row['speed_mps'] = 0.0
        row['speed_mph'] = 0.0
        row['velocity_mps'] = [0.0, 0.0, 0.0]
        row['control'] = {'throttle': 0.0, 'brake': 1.0, 'hand_brake': True}
        item['ego']['position_m'][1] = 56.2
        item['ego']['speed_mps'] = 0.0
        item['ego']['body_vertices_m'] = [[1.0, 54.2, 0], [1.0, 54.2, 1.5],
                                          [2.5, 54.2, 0], [2.5, 54.2, 1.5],
                                          [2.5, 58.2, 0], [2.5, 58.2, 1.5],
                                          [1.0, 58.2, 0], [1.0, 58.2, 1.5]]
        item['world']['road_projection']['s_m'] = 56.2
    files['trace.jsonl'] = lines(core)
    files['capture/evidence.jsonl'] = lines(evidence)
    files['road.xodr'] = files['road.xodr'].replace('C262666', 'C150094')
    source = {'files': files, 'graphs': base['graphs'], 'videos': base['videos']}
    spec_path = HERE / 'selected-generator-probe_02.json'
    spec_path.write_text(json.dumps(source, separators=(',', ':')) + '\n')
    anchor = HERE / 'diagnostic-anchor-probe_02.json'
    anchor.write_text(json.dumps({'assignment_id': AID, 'case_id': CASE,
                                  'scope': 'synthetic diagnostic only'},
                                 separators=(',', ':')) + '\n')
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': anchor.name,
                           'source': str(anchor.relative_to(REPO)),
                           'sha256': sha_bytes(anchor.read_bytes())}],
              'generator': {'source': str(spec_path.relative_to(REPO)),
                            'sha256': sha_bytes(spec_path.read_bytes())}}
    recipe_path = HERE / 'selected-recipe-probe_02.json'
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
    print(json.dumps({'generator_bytes': spec_path.stat().st_size,
                      'generator_sha256': recipe['generator']['sha256']}))


if __name__ == '__main__':
    main()
