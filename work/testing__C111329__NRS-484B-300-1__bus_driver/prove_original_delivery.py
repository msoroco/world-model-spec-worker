"""Synthetic software proof for the production original-only audit interface."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from PIL import Image

from delivery_audit import audit_attempt
from package_spec import CASES, HERE, ROOT, case_id, CAMERA_NAMES


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def build(name):
    scratch = ROOT / '.runtime-work/c111329/delivery' / name
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    aspect, policy, direction, enter = next(row[1:] for row in CASES if row[0] == name)
    site = json.loads((HERE / 'diagnostics' / name / 'site.json').read_text())
    site['original_sources'] = []
    hashes = {}
    for source in ('map', 'device', 'route', 'authority'):
        path = scratch / (source + '.json')
        put(path, {'mock_only_contract_wiring': True, 'source': source})
        site[source + '_source_path'] = path.name
        site['original_sources'].append({'path': path.name, 'sha256': sha(path)})
        hashes[source] = sha(path)
    packet_path = scratch / 'reviewed-site.json'
    put(packet_path, {'case_id': case_id(name), 'candidate_id': 'primary',
                      'source_kind': 'reviewed_original_site', 'site': site,
                      'device_aspect': aspect, 'bus_control_policy': policy,
                      'police_direction': direction, 'mock_only_contract_wiring': True})
    attempt = scratch / 'attempt'
    attempt.mkdir()
    image = Image.new('RGB', (1, 1), (0, 0, 0))
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    png = buffer.getvalue()
    frames = []
    frame_map = []
    for index in range(900):
        frame = 100 + index
        rows = {'original_frame': frame, 'time_s': index / 20,
                'case_id': case_id(name), 'device_id': site['device_id'],
                'facing_approach_id': site['ego_approach_id'],
                'bus_blueprint_id': site['bus_blueprint_id'], 'aspect': aspect,
                'bus_front_xy': [7 if not enter else 20 * min(index / 350, 1), 0],
                'police_direction': direction,
                'police_direction_source': 'authority.json' if direction else None,
                'placement_source': 'device.json',
                'nrs_307_context_source': 'authority.json'}
        rows.update({source + '_source_sha256': digest for source, digest in hashes.items()})
        frames.append(rows)
        frame_map.append({'original_frame': frame, 'time_s': index / 20,
                          'camera_png_sha256': {camera: hashlib.sha256(png).hexdigest()
                                                for camera in CAMERA_NAMES}})
    rows_path = attempt / 'original-device-frames.jsonl'
    rows_path.write_text(''.join(json.dumps(row) + '\n' for row in frames))
    map_path = attempt / 'camera-frame-map.jsonl'
    map_path.write_text(''.join(json.dumps(row) + '\n' for row in frame_map))
    video = scratch / 'mock-video.mkv'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=640x360:r=20',
                    '-frames:v', '900', '-c:v', 'ffv1', '-y', str(video)], check=True)
    archives, streams = {}, {}
    for camera in CAMERA_NAMES:
        archive = attempt / (camera + '.zip')
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_STORED) as handle:
            for index in range(900):
                handle.writestr(f'{index:04d}-{100+index}.png', png)
        copy = attempt / (camera + '.mkv')
        shutil.copyfile(video, copy)
        archives[camera] = {'path': archive.name, 'sha256': sha(archive)}
        streams[camera] = {'path': copy.name, 'sha256': sha(copy), 'frame_count': 900}
    put(attempt / 'capture-identity.json', {
        'case_id': case_id(name), 'candidate_id': 'primary',
        'source_kind': 'original_native_capture', 'diagnostic_fixture': False,
        'reviewed_site_sha256': sha(packet_path), 'frames_sha256': sha(rows_path),
        'camera_frame_map_sha256': sha(map_path), 'camera_archives': archives,
        'cameras': streams, 'mock_only_contract_wiring': True})
    return packet_path, attempt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--negative-missing-review', action='store_true')
    args = parser.parse_args()
    if args.case not in {case_id(row[0]) for row in CASES}:
        raise ValueError('unknown case')
    name = args.case.removeprefix(HERE.name + '__')
    if args.negative_missing_review:
        try:
            audit_attempt(ROOT / '.runtime-work/c111329/delivery/missing-reviewed-site.json',
                          ROOT / '.runtime-work/c111329/delivery/missing-attempt', name)
        except FileNotFoundError:
            print('original reviewed bus site packet missing')
            return 2
        raise ValueError('missing reviewed source unexpectedly accepted')
    packet, attempt = build(name)
    report = audit_attempt(packet, attempt, name, allow_mock=True)
    if report['case_id'] != args.case or report['legal_status'] != 'unresolved':
        raise ValueError('software contract proof differs')
    put(packet.parent / 'report.json', report)
    print(json.dumps({'case_id': args.case, 'mock_only_contract_wiring': True,
                      'source_complete_wiring': True, 'legal_status': 'unresolved'}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
