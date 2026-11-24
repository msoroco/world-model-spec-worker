"""Run exact comparison isolation on retained diagnostic source packets.

This proves the audit logic and source joins. Diagnostic packets cannot satisfy
the later original Native capture or parcel authority acceptance gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import comparison_audit
import property_route


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def packet(attempt: Path) -> dict:
    attempt = attempt.resolve()
    config = json.loads((attempt / 'config.json').read_text())
    map_packet = json.loads((attempt / 'map-packet.json').read_text())
    trace = json.loads((attempt / 'trace.json').read_text())
    native_map = map_packet['native_map']
    road = (attempt / native_map['path']).resolve()
    if not road.is_relative_to(attempt) or _sha(road) != native_map['sha256']:
        raise ValueError('native road source seal differs')
    source = map_packet['source']
    authority = (attempt / source['path']).resolve()
    if not authority.is_relative_to(attempt) or _sha(authority) != source['sha256']:
        raise ValueError('parcel authority source seal differs')
    if trace['case_id'] != config['selected_case_id']:
        raise ValueError('config and trace case differ')
    observation = property_route.analyze(map_packet, trace, {'case_id': trace['case_id']})
    statuses = observation['traversed_property_statuses']
    if len(statuses) > 1:
        raise ValueError('multiple parcel classes traversed')
    if statuses:
        parcel_class = statuses[0]
        route_class = 'property'
    else:
        parcel_class = map_packet['properties'][0]['status']
        route_class = 'roadway'
    frames = attempt / 'video_frames.jsonl'
    if not frames.is_file():
        raise ValueError('retained original frame map absent')
    return {
        'case_id': trace['case_id'],
        'map_id': native_map['map_name'],
        'actor_id': trace['actor_class'],
        'capture_profile': hashlib.sha256(json.dumps(config['cameras'], sort_keys=True).encode()).hexdigest(),
        'duration_frames': int(config['duration_s'] * config['rate_hz']),
        'approach_device_id': trace['approach_signal']['device_id'],
        'destination_device_id': trace['destination_signal']['device_id'],
        'parcel_class': parcel_class,
        'route_class': route_class,
        'approach_state': trace['approach_signal']['state'],
        'destination_state': trace['destination_signal']['state'],
        'purpose': trace['purpose']['value'],
        'trace_sha256': _sha(attempt / 'trace.json'),
        'map_source_sha256': _sha(road),
        'frame_map_sha256': _sha(frames),
        'parcel_authority_sha256': _sha(authority),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--comparison', required=True, choices=sorted(comparison_audit.PAIRS))
    ap.add_argument('--left-attempt', type=Path, required=True)
    ap.add_argument('--right-attempt', type=Path, required=True)
    ap.add_argument('--negative', action='store_true')
    args = ap.parse_args()
    left, right = packet(args.left_attempt), packet(args.right_attempt)
    if args.negative:
        right['approach_device_id'] = 'wrong-device'
    result = comparison_audit.audit_planned(left, right, args.comparison)
    print(json.dumps({'diagnostic_only': True, 'comparison': result,
                      'left': left, 'right': right}, sort_keys=True))


if __name__ == '__main__':
    main()
