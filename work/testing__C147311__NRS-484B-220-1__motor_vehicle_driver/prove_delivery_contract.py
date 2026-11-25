"""Per-case synthetic protocol proof for independent original delivery audit.

The positive path mocks reviewed-source and video decoding inputs to exercise
the receipt protocol. It is not a released original capture or legal proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from delivery_audit import ASSIGNMENT, CAMERAS, audit
from one_way_direction import CASES


def put(root: Path, name: str, value) -> dict:
    path = root / name
    path.write_text(json.dumps(value) + '\n' if not isinstance(value, str) else value,
                    encoding='utf-8')
    return {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def run(case_id: str, mode: str) -> dict:
    case = next((c for c in CASES if case_id == ASSIGNMENT + '__' + c.name), None)
    if case is None or mode not in {'diagnostic-positive', 'delivery-negative'}:
        raise ValueError('exact case and proof mode required')
    scratch = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch, prefix='c147311-delivery-') as tmp:
        root = Path(tmp)
        site = put(root, 'site.json', {'synthetic_protocol_fixture': True})
        frames = [{'frame': i, 'native_frame': 100 + i, 'time_s': i / 20,
                   'camera_frames': {name: 100 + i for name in CAMERAS}}
                  for i in range(900)]
        frame_map = put(root, 'frame-map.json', {
            'source_kind': 'original_native_frame_map', 'case_id': case_id,
            'frames': frames})
        trace = put(root, 'trace.jsonl', '{}\n' * 900)
        video_refs = {name: put(root, name + '.mkv', 'synthetic protocol pixels\n')
                      for name in CAMERAS}
        refs = [site, frame_map, trace, *video_refs.values()]
        seal = put(root, 'seal.json', {'source_kind': 'original_native_capture_seal',
                                     'case_id': case_id, 'attempt_id': 'synthetic-protocol-attempt',
                                     'recording_id': 'synthetic-protocol-recording',
                                     'sources': {ref['path']: ref['sha256'] for ref in refs}})
        receipt = {'case_id': case_id, 'source_kind': 'original_native_attempt',
                   'diagnostic_fixture': mode == 'delivery-negative',
                   'native_process_exit_code': 0, 'owner_released': True,
                   'attempt_id': 'synthetic-protocol-attempt',
                   'recording_id': 'synthetic-protocol-recording',
                   'site_ref': site, 'frame_map_ref': frame_map, 'trace_ref': trace,
                   'video_refs': video_refs, 'capture_seal_ref': seal}
        probe = lambda path: {'nb_read_frames': '900', 'r_frame_rate': '20/1',
                              'width': 1280, 'height': 720}
        reviewed = {'scene': {'direction': case.direction}}
        measured = {'actual_direction': case.direction}
        with patch('delivery_audit.verify', return_value=reviewed), patch(
                'delivery_audit.measure_reviewed', return_value=measured):
            outcome = audit(root, receipt, probe)
    if outcome['frames_checked'] != 900 or len(outcome['video_sha256']) != 4:
        raise ValueError('delivery protocol skipped frame/video checks')
    return {'case_id': case_id, 'scope': 'synthetic protocol fixture only',
            'positive_protocol_passed': True, 'original_delivery_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--mode', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.mode), sort_keys=True))
