"""Independent CPU audit of saved diagnostic source and all four video streams.

This command tests source handling only. Synthetic packets cannot prove parcel
authority, physical completion, or a legal conclusion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from property_route import analyze_files
from case_observation import audit_case


CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def audit(root, case_id):
    root = Path(root).resolve()
    packet_path = source(root, 'map-packet.json')
    trace_path = source(root, 'trace.json')
    authority = source(root, 'authority.json')
    xodr = source(root, 'road.xodr')
    mapping_path = source(root, 'video_frames.jsonl')
    config = json.loads(source(root, 'config.json').read_text())
    packet = json.loads(packet_path.read_text())
    trace = json.loads(trace_path.read_text())
    if config['selected_case_id'] != case_id or trace['case_id'] != case_id:
        raise ValueError('Exact diagnostic case identity differs')
    if packet.get('diagnostic_fixture') is not True:
        raise ValueError('Only synthetic diagnostic proof is accepted here')
    if packet['source']['sha256'] != sha(authority) or packet['native_map']['sha256'] != sha(xodr):
        raise ValueError('Synthetic source hash differs')
    if json.loads(authority.read_text())['opendrive_sha256'] != sha(xodr):
        raise ValueError('Authority/OpenDRIVE source seal differs')
    mapping = [json.loads(line) for line in mapping_path.read_text().splitlines()]
    if not mapping or len(mapping) != len(trace['ego']):
        raise ValueError('Original ego/frame-map count differs')
    for index, (frame, ego) in enumerate(zip(mapping, trace['ego'])):
        if frame['video_frame'] != index or frame['carla_frame'] != ego['frame'] or abs(frame['time_s'] - ego['time_s']) > 1e-6:
            raise ValueError('Original ego/frame-map identity differs')
    observation = analyze_files(packet_path, trace_path, root / 'case-identity.json') if (root / 'case-identity.json').is_file() else None
    if observation is None:
        from property_route import analyze
        observation = analyze(packet, trace, {'case_id': case_id})
    contrast = audit_case(observation, trace, {'case_id': case_id})
    from worker_exchange.media import audit as media_audit
    decoded = {}
    for camera in CAMERAS:
        path = source(root, camera + '.mkv')
        receipt = media_audit(path, len(mapping), mapping_sha256=sha(mapping_path))
        if receipt.get('passed') is not True or receipt.get('frames') != len(mapping):
            raise ValueError('Diagnostic camera pixel decode differs: ' + camera)
        decoded[camera] = {'frames': receipt['frames'], 'rgb_sequence_sha256': receipt['rgb_sequence_sha256']}
    return {'format': 'property-diagnostic-delivery-audit', 'case_id': case_id,
            'diagnostic_fixture': True, 'source_hashes': {name: sha(source(root, name)) for name in
            ('map-packet.json', 'trace.json', 'authority.json', 'road.xodr', 'video_frames.jsonl')},
            'frame_count': len(mapping), 'decoded_cameras': decoded,
            'planned_case': contrast['planned_case'],
            'physical_acceptance_claimed': False, 'legal_judgment': None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case), indent=2))


if __name__ == '__main__':
    main()
