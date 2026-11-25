"""Exercise real physical checker on three distinct synthetic source outcomes."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.native_output import physical_result


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def run(letter, kind):
    source = REPO / '.runtime-work' / f'c111277-compat-new-{letter}-primary'
    stage = REPO / '.runtime-work' / f'c111277-physical-{letter}-{kind}'
    stage.mkdir(parents=True, exist_ok=True)
    for name in ('config.json', 'trace.jsonl', 'video_frames.jsonl',
                 'signal_context.json', 'acquisition-provenance.json'):
        shutil.copy2(source / name, stage / name)
    if kind != 'missing_evidence':
        motion = [json.loads(line) for line in (source / 'interaction_history.jsonl').read_text().splitlines()]
        if kind == 'incomplete_motion':
            first = motion[0]['states']['ego']['body_vertices_m']
            for row in motion:
                row['states']['ego']['body_vertices_m'] = first
        (stage / 'interaction_history.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in motion))
    base = json.loads((source / 'result.json').read_text())
    result = physical_result(stage, {'target_checks': base['target_checks']})
    reduced = {key: result[key] for key in ('physical_checks', 'maneuver_completed',
                                             'realized_observables', 'provenance_kind',
                                             'diagnostic_fixture')}
    destination = ROOT / 'proofs' / f'condition_{letter}' / 'physical' / (kind + '.json')
    write(destination, reduced)
    status = reduced['physical_checks']['maneuver']['status']
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    if status != expected:
        raise AssertionError(f'{kind}: expected {expected}; observed {status}')
    print(json.dumps({'kind': kind, 'status': status, 'result': str(destination),
                      'result_sha256': hashlib.sha256(destination.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--letter', choices=['a', 'b'], required=True)
    parser.add_argument('--kind', choices=['complete_motion', 'incomplete_motion', 'missing_evidence'], required=True)
    arguments = parser.parse_args()
    run(arguments.letter, arguments.kind)
