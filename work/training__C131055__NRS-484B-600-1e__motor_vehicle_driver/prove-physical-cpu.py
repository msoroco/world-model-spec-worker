"""Exercise source-shaped motion and lifecycle CPU branches; never claim Native capture."""
import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
output_root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
if not output_root.is_relative_to(ROOT / '.runtime-work'):
    raise ValueError('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
sys.path.insert(0, str(HERE / 'native'))
from measure import measure


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(index, kind):
    assert index in (1, 2, 3)
    assert kind in ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle')
    label = {1: 'below', 2: 'above', 3: 'at'}[index]
    source = HERE / f'current-v2-{label}-sources'
    history = source / 'roundabout-speed-history.jsonl'
    survey = source / 'roundabout-survey.json'
    recipe = json.loads((HERE / f'current-v2-{label}-fixture-recipe.json').read_text())
    bound = {item['path']: item['sha256'] for item in recipe['sources']}
    assert sha(history) == bound[history.name] and sha(survey) == bound[survey.name]
    case = HERE.name + f'__controlled_{index}'
    if kind == 'lifecycle':
        code = (HERE / 'native/runner.py').read_text()
        events = ['capture_finished', 'encoders_closed', 'restoration_verified',
                  'native_exit', 'owner_released', 'saved_processing_started']
        assert 'process.stdin.close()' in code and 'process.wait(timeout=180)' in code
        assert 'finally:' in code and 'restore(client, saved)' in code
        assert code.index('process.stdin.close()') < code.index('measured = measure(')
        assert code.index('measured = measure(') < code.index('finally:')
        return {'format': 'worker-physical-lifecycle-cpu-test', 'case_id': case,
                'events': events, 'runner_sha256': sha(HERE / 'native/runner.py'),
                'scope': 'source-shape and static ownership-order CPU check only',
                'physical_acceptance': False}
    with tempfile.TemporaryDirectory(prefix='owner199-physical-',
                                     dir=ROOT / '.runtime-work') as directory:
        scratch = Path(directory)
        if kind == 'complete_motion':
            metrics = measure(history, survey)
            assert metrics['frames'] == 600 and metrics['first_exit_road_frame'] == 500
            status, completed = 'met', True
            observations = {'exit_frame': metrics['first_exit_road_frame'],
                            'synthetic_maximum_mph': metrics['maximum_full_trace_mph']}
        else:
            if kind == 'incomplete_motion':
                rows = [json.loads(line) for line in history.read_text().splitlines()]
                for row in rows:
                    row['road_id'] = 1
                trial = scratch / 'incomplete-history.jsonl'
                trial.write_text(''.join(json.dumps(row) + '\n' for row in rows))
                expected = 'original roundabout exit traversal missing'
            else:
                trial = scratch / 'missing-history.jsonl'
                expected = 'No such file or directory'
            try:
                measure(trial, survey)
            except (ValueError, FileNotFoundError) as error:
                assert expected in str(error)
            else:
                raise AssertionError('Negative physical source branch accepted')
            status = 'not_met' if kind == 'incomplete_motion' else 'unverified'
            completed = False
            observations = {}
    return {'format': 'worker-physical-motion-cpu-test', 'case_id': case,
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'physical_checks': {'maneuver': {'status': status,
                'method': '600-frame roundabout arc-to-exit source-shape measurement',
                'sources': [f'current-v2-{label}-sources/roundabout-speed-history.jsonl',
                            f'current-v2-{label}-sources/roundabout-survey.json']}},
            'maneuver_completed': completed,
            'realized_observables': observations,
            'physical_or_legal_acceptance': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--index', type=int, required=True)
    parser.add_argument('--kind', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.index, args.kind)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'case_id': result['case_id'], 'kind': args.kind,
                      'cpu_branch_passed': True, 'physical_acceptance': False}))
