"""Deterministic synthetic 900-frame probes of exact physical outcome logic."""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('device_physical_probe', ROOT / 'physical_audit.py')
physical = importlib.util.module_from_spec(spec)
spec.loader.exec_module(physical)


def run(case_id: str, kind: str, packet_path: Path, result_path: Path) -> dict:
    if kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('unknown physical probe kind')
    if not case_id.startswith('testing__C111748__NRS-484B-403-2__motor_vehicle_driver__'):
        raise ValueError('wrong exact case')
    turn_case = not case_id.endswith('__prohibited_obey')
    if kind != 'missing_evidence':
        turn = turn_case if kind == 'complete_motion' else not turn_case
        prohibits = not case_id.endswith('__neutral_device_turn')
        packet = {'case_id': case_id, 'actor': 'motor_vehicle_driver',
                  'diagnostic': True, 'ego_id': 7,
                  'device': {'device_id': 20, 'governed_approach': 'A',
                             'prohibits_u_turn': prohibits}, 'frames': []}
        for i in range(900):
            packet['frames'].append({'frame': 1000 + i, 'time_s': i / 20,
                'ego': {'id': 7, 'approach_id': 'A', 'road_id': 1,
                        'lane_id': -1 if turn and i == 899 else 1,
                        'x': float(i) / 20, 'y': 0.0,
                        'yaw_deg': 180.0 if turn and i == 899 else 0.0,
                        'u_turn_in_progress': bool(turn and i >= 600)},
                'device_readback': {'device_id': 20, 'prohibits_u_turn': prohibits,
                                    'visible_to_ego': i >= 20}})
        packet_path.write_text(json.dumps(packet, separators=(',', ':')) + '\n')
    result = physical.assess(packet_path, case_id)
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    if result['physical_checks']['maneuver']['status'] != expected:
        raise ValueError('physical probe outcome mismatch: ' + kind)
    result.update(case_id=case_id, fixture_kind=kind,
                  provenance_kind='synthetic_fixture', diagnostic_fixture=True)
    result_path.write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.kind, args.packet, args.result), sort_keys=True))


if __name__ == '__main__':
    main()
