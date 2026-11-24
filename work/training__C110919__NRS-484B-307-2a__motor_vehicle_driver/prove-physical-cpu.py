"""Test source-shaped maneuver outcomes and ownership order without Native claims."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(index: int, kind: str) -> dict:
    assert index in (1, 2)
    assert kind in ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle')
    generator = HERE / ('current-v2-primary-generator.json' if index == 1 else
                        'current-v2-controlled_2-generator.json')
    recipe = HERE / ('current-v2-primary-recipe.json' if index == 1 else
                     'current-v2-controlled_2-recipe.json')
    assert json.loads(recipe.read_text())['generator']['sha256'] == sha(generator)
    case = HERE.name + f'__controlled_{index}'
    if kind == 'lifecycle':
        code = (HERE / 'native/runner.py').read_text()
        ordered = ('capture.close(confirmed=error is None)',
                   'encoder.stdin.close()', 'restore(client,saved)',
                   "write_new(output/'native-capture-report.json'")
        assert all(part in code for part in ordered)
        assert [code.index(part) for part in ordered] == sorted(code.index(part) for part in ordered)
        return {'format': 'worker-right-turn-lifecycle-cpu-test', 'case_id': case,
                'events': ['capture_finished', 'encoders_closed', 'restoration_verified',
                           'native_exit', 'owner_released', 'saved_processing_started'],
                'runner_sha256': sha(HERE / 'native/runner.py'),
                'scope': 'static closure ordering plus prospective owner handoff; no Native capture',
                'physical_acceptance': False}
    files = json.loads(generator.read_text())['files']
    samples = [json.loads(line) for line in files['native_samples.jsonl'].splitlines()]
    geometry = json.loads(files['road_geometry.json'])
    assert geometry['signal_actor_id'] == 601 and geometry['stop_line_y_m'] == -14.0
    assert len(samples) == 600 and all(sample['signal_state_observed'] == 'Green'
                                       for sample in samples)
    if kind == 'missing_evidence':
        observed = []
    elif kind == 'incomplete_motion':
        observed = [dict(sample, native_center_xy_m=[1.75, -40.0],
                         ego_turn_entered=False) for sample in samples]
    else:
        observed = samples
    entered = [i for i, sample in enumerate(observed) if sample['ego_turn_entered']]
    exited = bool(observed and observed[-1]['native_center_xy_m'][0] > 13 and
                  abs(observed[-1]['native_center_xy_m'][1] + 1.75) < 2)
    if not observed:
        status = 'unverified'
    elif entered and exited:
        status = 'met'
    else:
        status = 'not_met'
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    assert status == expected
    return {'format': 'worker-right-turn-physical-cpu-test', 'case_id': case,
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'physical_checks': {'maneuver': {'status': status,
                'method': '600-frame source-shaped yaw/turn entry and destination exit',
                'sources': [generator.name + ':native_samples.jsonl',
                            generator.name + ':road_geometry.json']}},
            'maneuver_completed': status == 'met',
            'realized_observables': ({'first_turn_entry_frame': entered[0],
                                    'destination_exit_observed': exited} if status == 'met' else {}),
            'source_recipe_sha256': sha(recipe),
            'physical_or_legal_acceptance': False}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--index', type=int, required=True)
    parser.add_argument('--kind', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output_root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
    if not output_root.is_relative_to(ROOT / '.runtime-work'):
        raise ValueError('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
    result = run(args.index, args.kind)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'case_id': result['case_id'], 'kind': args.kind,
                      'cpu_branch_passed': True, 'physical_acceptance': False}))
