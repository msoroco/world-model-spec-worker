"""Three diagnostic physical-checker outcomes from synthetic exact-case attempts."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path

from runner import MOTIONS

ASSIGNMENT = 'testing__C143687__LVMC-11-22-120-B__cycle_or_scooter_operator'


def run(case: str, kind: str, attempt: Path, output: Path) -> dict:
    if case not in {ASSIGNMENT + '__' + name for name in MOTIONS}:
        raise ValueError('exact case required')
    if kind not in {'complete_motion', 'incomplete_motion', 'missing_evidence'}:
        raise ValueError('unknown physical fixture kind')
    if output.exists():
        raise ValueError('fresh diagnostic result required')
    root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root, prefix='c143687-physical-') as temp:
        stage = Path(temp)
        for name in ('config.json', 'trace.jsonl', 'video_frames.jsonl',
                     'acquisition-provenance.json'):
            shutil.copy2(attempt / name, stage / name)
        base = json.loads((attempt / 'result.json').read_text(encoding='utf-8'))
        if base['case_id'] != case or base.get('diagnostic_fixture') is not True:
            raise ValueError('physical proof requires exact synthetic attempt')
        base['realized_observables'] = {'observed_motion_frames': {
            'unit': 'count', 'method': '20 Hz diagnostic trace readback',
            'time_window': '45-second synthetic episode', 'statistic': 'count',
            'reference': 'trace.jsonl', 'value': 900}}
        if kind == 'incomplete_motion':
            path = stage / 'trace.jsonl'
            lines = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
            initial_position = lines[0]['position']
            initial_xyz = lines[0]['position_m']
            for row in lines:
                row['position'] = initial_position
                row['position_m'] = initial_xyz
            path.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in lines), encoding='utf-8')
        elif kind == 'missing_evidence':
            (stage / 'trace.jsonl').unlink()
        from scenario_pipeline.worker_exchange.native_output import physical_result
        result = physical_result(stage, base)
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    actual = result['physical_checks']['maneuver']['status']
    if actual != expected or result['maneuver_completed'] != (expected == 'met'):
        raise ValueError('physical diagnostic outcome differs: ' + actual)
    if result.get('provenance_kind') != 'synthetic_fixture' or result.get('diagnostic_fixture') is not True:
        raise ValueError('synthetic provenance lost')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return {'case_id': case, 'kind': kind, 'status': actual,
            'diagnostic_fixture': True, 'result': str(output)}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--case', required=True)
    p.add_argument('--kind', required=True)
    p.add_argument('--attempt', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(run(args.case, args.kind, args.attempt, args.output), sort_keys=True))


if __name__ == '__main__':
    main()
