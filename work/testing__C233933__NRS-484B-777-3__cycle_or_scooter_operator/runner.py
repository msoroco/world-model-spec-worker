"""Exact source-gated Native three-rider formation runner."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from abreast import CASES, SOURCES, validate_scene
from package_spec import AID, ACTOR, CAMERA_NAMES, CELL, LAW

def reviewed_site(path, case_id):
    path = Path(path).resolve()
    packet = json.loads(path.read_text())
    if packet.get('reviewed_original_native_site') is not True or packet.get('source_kind') != 'original_native_map_geometry' or packet.get('assignment_id') != AID or packet.get('case_id') != case_id:
        raise ValueError('reviewed exact rider site required')
    if packet.get('duration_frames') != 900 or packet.get('rate_hz') != 20 or tuple(packet.get('cameras', ())) != CAMERA_NAMES or not packet.get('map_name'):
        raise ValueError('Native map and four-camera profile required')
    refs = packet.get('source_refs')
    roles = {'map', *SOURCES}
    if not isinstance(refs, list) or not roles <= {ref.get('role') for ref in refs}:
        raise ValueError('independent rider source roles missing')
    for ref in refs:
        target = (path.parent / ref['path']).resolve()
        if not target.is_relative_to(path.parent) or not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != ref.get('sha256'):
            raise ValueError('reviewed rider source changed: ' + ref.get('role', 'unknown'))
    if packet.get('map_sha256') != next(ref['sha256'] for ref in refs if ref['role'] == 'map'):
        raise ValueError('Native map source differs')
    scene = packet['scene']
    case = next((candidate for candidate in CASES if case_id == AID + '__' + candidate.name), None)
    if case is None:
        raise ValueError('unknown exact rider case')
    validate_scene(scene, case)
    for name in SOURCES:
        if scene[name + '_source_sha256'] != next(ref['sha256'] for ref in refs if ref['role'] == name):
            raise ValueError('rider context source binding differs: ' + name)
    if not packet.get('bicycle_blueprint_id') or not packet['bicycle_blueprint_id'].startswith('vehicle.'):
        raise ValueError('reviewed Native bicycle blueprint required')
    packet['reviewed_site_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    return packet, case

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--case')
    parser.add_argument('--site', type=Path)
    parser.add_argument('--host')
    parser.add_argument('--port')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    config = json.loads((Path(__file__).resolve().parent / 'config.json').read_text())
    selected = config['selected_case_id']
    if (config['assignment_id'], config['law_id'], config['cell_id'], config['actor']) != (AID, LAW, CELL, ACTOR) or args.case not in (None, selected):
        raise ValueError('exact rider assignment differs')
    if args.check:
        print('exact rider runner static check passed: ' + selected)
        return
    site_path = args.site or os.environ.get('C233933_REVIEWED_SITE')
    if not site_path or not args.host or not args.port or args.output_dir is None:
        raise ValueError('reviewed rider site, host, port and output required')
    site, case = reviewed_site(site_path, selected)
    from rider_adapter import CarlaRiderAdapter
    from rider_capture import capture
    capture(CarlaRiderAdapter(args.host, args.port, site, case, config.get('control_profile', {})), site, selected, args.output_dir)

if __name__ == '__main__':
    main()
