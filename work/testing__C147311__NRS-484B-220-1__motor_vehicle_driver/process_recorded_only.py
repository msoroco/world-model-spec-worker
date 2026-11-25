"""Immutable-input original direction measurement, with explicit synthetic mode."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from one_way_direction import CASES, measure_original
from reviewed_source import measure_reviewed, verify

ASSIGNMENT = 'testing__C147311__NRS-484B-220-1__motor_vehicle_driver'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def process(attempt: Path, output: Path, case_id: str, reviewed_packet: Path | None = None,
            diagnostic_fixture: bool = False) -> dict:
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or output.is_relative_to(attempt) or attempt.is_relative_to(output):
        raise ValueError('fresh derived output outside original acquisition required')
    suffix = case_id.removeprefix(ASSIGNMENT + '__')
    case = next((c for c in CASES if c.name == suffix), None)
    if case is None or case_id != ASSIGNMENT + '__' + suffix:
        raise ValueError('exact one-way case required')
    trace = attempt / 'native-frames.jsonl'
    if not trace.is_file():
        raise ValueError('Missing required source: native-frames.jsonl')
    trace_hash = sha(trace)
    rows = [json.loads(line) for line in trace.read_text(encoding='utf-8').splitlines()]
    if diagnostic_fixture:
        scene_path = attempt / 'diagnostic-scene.json'
        if not scene_path.is_file():
            raise ValueError('Missing required source: diagnostic-scene.json')
        scene_hash = sha(scene_path)
        scene = json.loads(scene_path.read_text(encoding='utf-8'))
        if scene.get('diagnostic_fixture') is not True:
            raise ValueError('diagnostic source provenance mismatch')
        measurement = measure_original(rows, scene, case)
        source_kind = 'synthetic_software_fixture'
    else:
        if reviewed_packet is None:
            raise ValueError('original reviewed site packet path required')
        reviewed = verify(reviewed_packet, suffix)
        scene_hash = reviewed['site_sha256']
        measurement = measure_reviewed(rows, reviewed_packet, suffix)
        source_kind = 'original_native_attempt'
    if sha(trace) != trace_hash:
        raise ValueError('original acquisition changed during saved processing')
    output.mkdir(parents=True)
    target = output / 'measurement.json'
    target.write_text(json.dumps(measurement, indent=2) + '\n', encoding='utf-8')
    receipt = {'format': 'c147311-recorded-only-direction-v1', 'case_id': case_id,
               'source_kind': source_kind, 'trace_sha256': trace_hash,
               'scene_sha256': scene_hash, 'measurement_sha256': sha(target),
               'original_frame_count': measurement['frame_count'],
               'actual_direction': measurement['actual_direction'],
               'legal_verdict_claimed': False, 'physical_acceptance_claimed': False}
    (output / 'processing-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--reviewed-packet', type=Path)
    parser.add_argument('--diagnostic-fixture', action='store_true')
    args = parser.parse_args()
    print(json.dumps(process(args.attempt, args.output, args.case, args.reviewed_packet,
                             args.diagnostic_fixture), sort_keys=True))


if __name__ == '__main__':
    main()
