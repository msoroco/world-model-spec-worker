"""Construct textual source-shaped CPU diagnostics for three exact cases.

These packets carry explicit synthetic provenance and cannot be submitted as
original Native captures or used by the production full-PNG delivery audit.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pass_right_measure import observe
from pass_right_route import build_case

HERE = Path(__file__).resolve().parent


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n'


def source(folder, name, value):
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded(value))
    return {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def map_packet():
    return {
        'source_kind': 'original_native_map_geometry',
        'diagnostic_fixture': True,
        'direction': 'two_way', 'map_name': 'SyntheticDiagnosticOnly',
        'source_opendrive_sha256': hashlib.sha256(b'synthetic diagnostic OpenDRIVE').hexdigest(),
        'same_direction_marked_lanes': 1,
        'public_highway_observed': True, 'two_way_observed': True,
        'intersection_s_m': [55.0, 70.0],
        'actor_half_width_m': 0.9, 'right_pass_center_m': 3.0,
        'target_lane_center_m': 0.0, 'turn_lateral_displacement_m': 1.2,
        'cross_sections': [{'station_m': station, 'source': 'native_map',
                            'right_positive': True,
                            'world_center_xy_m': [station, 10.0],
                            'paved_lateral_bounds_m': [-2.5, 4.5]}
                           for station in range(45, 81, 5)]}


def trace(packet, variant):
    frames = []
    for index in range(900):
        step = min(index, 11)
        frame_id = 1420 + index
        frames.append({
            'frame': index, 't_s': index / 20,
            'native_frame_id': frame_id,
            'camera_frame_ids': {name: frame_id for name in
                                 ('front', 'rear', 'left', 'right')},
            'ego_s_m': 55 + 0.7 * step,
            'target_s_m': 59 + 0.15 * step,
            'ego_lateral_m': 3.0,
            'target_lateral_m': -0.13 * step if variant == 'left_turn' else 0.0,
            'ego_speed_mps': 14.0 if index <= 11 else 0.0,
            'target_speed_mps': 3.0 if index <= 11 else 0.0,
            'target_left_signal': variant == 'left_signal',
            'target_heading_deg': -3.0 * step if variant == 'left_turn' else 0.0,
            'ego_paved': True, 'target_paved': True})
    result = {
        'source_kind': 'original_native_actor_trace', 'diagnostic_fixture': True,
        'fps': 20, 'ego_id': 10, 'target_id': 11,
        'road': {key: value for key, value in packet.items() if key != 'source_kind'},
        'frames': frames, 'physical_acceptance_claimed': False}
    measurement = observe(result)
    if (measurement['target_left_signal_during_pass'] != (variant == 'left_signal') or
            measurement['target_left_motion_during_pass'] != (variant == 'left_turn')):
        raise ValueError('diagnostic variant measurement does not match')
    return result, measurement


def build():
    packet = map_packet()
    for variant in ('left_signal', 'left_turn', 'neither'):
        folder = HERE / 'cases' / variant / 'fixture-sources'
        native = folder / 'original-attempt/native'
        map_ref = source(native, 'map.json', packet)
        request_ref = source(native, 'route-request.json', build_case(packet, variant))
        actual, measured = trace(packet, variant)
        trace_ref = source(native, 'trace.json', actual)
        frame_map = {'fps': 20, 'frames': [
            {'original_index': i, 'native_frame_id': 1420 + i,
             'time_s': i / 20, 'camera_frame_ids': {name: 1420 + i for name in
                                                   ('front', 'rear', 'left', 'right')}}
            for i in range(900)]}
        map_clock_ref = source(native, 'frame-map.json', frame_map)
        source(native, 'capture-receipt.json', {
            'case_id': HERE.name + '__' + variant,
            'diagnostic_fixture': True,
            'map_source': map_ref, 'route_request_source': request_ref,
            'trace_source': trace_ref, 'frame_map_source': map_clock_ref,
            'delivered_measurement': measured,
            'physical_acceptance_claimed': False})
        source(folder / 'fixture-sources/original-attempt', 'source-manifest.json', {
            'assignment_id': HERE.name, 'case_id': HERE.name + '__' + variant,
            'variant': variant, 'diagnostic_fixture': True,
            'map': {'path': 'native/map.json', 'sha256': map_ref['sha256']},
            'route_request': {'path': 'native/route-request.json',
                              'sha256': request_ref['sha256']},
            'trace': {'path': 'native/trace.json', 'sha256': trace_ref['sha256']},
            'frame_map': {'path': 'native/frame-map.json',
                          'sha256': map_clock_ref['sha256']},
            'frame_count': 900,
            'physical_acceptance_claimed': False})
        print(variant, measured['pass_frames'], measured['paragraph_a_condition_observed'])


if __name__ == '__main__':
    build()
