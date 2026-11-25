"""Synthetic positive/negative protocol checks for original delivery auditor."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from delivery_audit import ASSIGNMENT, CAMERAS, MOTIONS, audit
from native_site import canonical_sha


def put(root: Path, name: str, value) -> dict:
    path = root / name
    path.write_text(json.dumps(value) + '\n' if not isinstance(value, str) else value,
                    encoding='utf-8')
    return {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def run(case_id: str, mode: str) -> dict:
    suffix = case_id.removeprefix(ASSIGNMENT + '__')
    if case_id != ASSIGNMENT + '__' + suffix or suffix not in MOTIONS or mode not in ('diagnostic-positive', 'delivery-negative'):
        raise ValueError('exact bicycle case and protocol mode required')
    scratch = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch, prefix='c143687-delivery-') as temp:
        root = Path(temp)
        site_data = {'map_name': 'synthetic-protocol-map', 'street_id': 'street',
                     'bicycle_blueprint_id': 'vehicle.bicycle',
                     'engineer_designation_source': 'synthetic protocol only',
                     'sign': {'source_id': 'sign'}, 'diagnostic_protocol': True}
        site = put(root, 'site.json', {'synthetic_protocol_fixture': True})
        entering = MOTIONS[suffix] == 'enter_roadway'
        packet = {'source_kind': 'original_native_capture', 'case_id': case_id,
                  'site_sha256': canonical_sha(site_data), 'map_name': site_data['map_name'],
                  'street_id': site_data['street_id'], 'actor_id': '11',
                  'actor_blueprint_id': site_data['bicycle_blueprint_id'],
                  'frames': [{'original_frame': i, 'elapsed_s': i / 20,
                              'actor_id': '11',
                              'segment': 'governed_street_roadway' if entering and i >= 200 else 'nonmotorized_trail',
                              'street_id': 'street', 'sign_source_id': 'sign',
                              'sign_posted_readback': True} for i in range(900)]}
        packet['seal_sha256'] = canonical_sha(packet)
        packet_ref = put(root, 'capture-packet.json', packet)
        frames = [{'frame': i, 'native_frame': 100 + i, 'time_s': i / 20,
                   'camera_frames': {name: 100 + i for name in CAMERAS}}
                  for i in range(900)]
        frame_map = put(root, 'frame-map.json', {'source_kind': 'original_native_frame_map',
                                                'case_id': case_id, 'frames': frames})
        trace = put(root, 'trace.jsonl', ''.join(json.dumps({'frame': 100 + i,
                       'time_s': i / 20}) + '\n' for i in range(900)))
        videos = {name: put(root, name + '.mkv', 'synthetic protocol pixels\n') for name in CAMERAS}
        refs = [site, packet_ref, frame_map, trace, *videos.values()]
        seal = put(root, 'seal.json', {'source_kind': 'original_native_capture_seal',
                    'case_id': case_id, 'attempt_id': 'synthetic-protocol-attempt',
                    'recording_id': 'synthetic-protocol-recording',
                    'sources': {ref['path']: ref['sha256'] for ref in refs}})
        receipt = {'case_id': case_id, 'source_kind': 'original_native_attempt',
                   'diagnostic_fixture': mode == 'delivery-negative',
                   'native_process_exit_code': 0, 'owner_released': True,
                   'attempt_id': 'synthetic-protocol-attempt',
                   'recording_id': 'synthetic-protocol-recording',
                   'site_ref': site, 'capture_packet_ref': packet_ref,
                   'frame_map_ref': frame_map, 'trace_ref': trace,
                   'video_refs': videos, 'capture_seal_ref': seal}
        probe = lambda path: {'nb_read_frames': '900', 'r_frame_rate': '20/1',
                              'width': 1280, 'height': 720}
        with patch('delivery_audit.verify', return_value={'site': site_data}), patch(
                'delivery_audit.measure', side_effect=lambda s, p, c: {
                    'roadway_frames': 700 if entering else 0}):
            outcome = audit(root, receipt, probe)
    if outcome['frames_checked'] != 900 or len(outcome['video_sha256']) != 4:
        raise ValueError('delivery protocol skipped original frame/video checks')
    return {'case_id': case_id, 'scope': 'synthetic protocol fixture only',
            'positive_protocol_passed': True, 'original_delivery_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--mode', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.mode), sort_keys=True))
