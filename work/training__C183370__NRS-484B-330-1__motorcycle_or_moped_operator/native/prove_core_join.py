"""Four-case synthetic Native/Core source-join positives and negatives."""

import json
import tempfile
from pathlib import Path

from measure_original import measure_core_join
from prove_original import fixture


ROOT = Path(__file__).resolve().parent.parent


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))


def prove():
    scratch = Path('.runtime-work/c183370-core-join').resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    positive = negative = 0
    with tempfile.TemporaryDirectory(dir=scratch, prefix='fixture-') as temporary:
        for suffix in ('probe_a', 'probe_b', 'probe_c', 'probe_d'):
            attempt = Path(temporary) / suffix
            attempt.mkdir()
            case_id = fixture(attempt, suffix)
            native = [json.loads(line) for line in (attempt / 'native-rows.jsonl').read_text().splitlines()]
            trace = [{'frame': row['native_frame'], 'time_s': row['time_s'],
                      'position': {'x': row['motorcycle_xyz_m'][0],
                                   'y': row['motorcycle_xyz_m'][1],
                                   'z': row['motorcycle_xyz_m'][2]},
                      'speed_mps': row['motorcycle_speed_mps']}
                     for row in native]
            evidence = [{'original_frame': row['native_frame'],
                         'recording_time_s': row['time_s'],
                         'ego': {'position_m': row['motorcycle_xyz_m'],
                                 'speed_mps': row['motorcycle_speed_mps']}}
                        for row in native]
            frames = [{'frame': row['native_frame'], 'time_s': row['time_s']}
                      for row in native]
            sources = {'trace.jsonl': trace, 'capture/evidence.jsonl': evidence,
                       'capture/native/frames.jsonl': frames}
            for name, rows in sources.items():
                write_rows(attempt / name, rows)
            joined = measure_core_join(attempt, case_id)
            if (joined['core_join']['frames'] != 600 or
                    not joined['core_join']['original_native_core_join_passed'] or
                    joined['physical_completion'] is not None):
                raise AssertionError('Core source join did not preserve measured uncertainty')
            positive += 1
            for name, changed, error_text in (
                ('trace.jsonl', dict(trace[10], speed_mps=99), 'Native/Core source join differs'),
                ('capture/evidence.jsonl', dict(evidence[10], original_frame=9999), 'Native/Core source join differs'),
                ('capture/native/frames.jsonl', dict(frames[10], time_s=99), 'Native/Core source join differs'),
                ('trace.jsonl', dict(trace[10], speed_mps=True), 'Native/Core source join differs'),
            ):
                path = attempt / name
                original = path.read_text()
                damaged = [json.loads(line) for line in original.splitlines()]
                damaged[10] = changed
                write_rows(path, damaged)
                try:
                    measure_core_join(attempt, case_id)
                except ValueError as error:
                    if error_text not in str(error):
                        raise
                else:
                    raise AssertionError('Damaged Core source accepted: ' + name)
                path.write_text(original)
                negative += 1
            missing = attempt / 'capture/evidence.jsonl'
            original = missing.read_text()
            missing.unlink()
            try:
                measure_core_join(attempt, case_id)
            except ValueError as error:
                if 'Missing required source: capture/evidence.jsonl' not in str(error):
                    raise
            else:
                raise AssertionError('Missing Core evidence accepted')
            missing.write_text(original)
            negative += 1
    proof = {'format': 'c183370-native-core-join-cpu-v1', 'assignment_id': ROOT.name,
             'positive_count': positive, 'negative_count': negative,
             'synthetic_source_shape_only': True,
             'original_physical_or_legal_outcome_claimed': False}
    (ROOT / 'native/core-join-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'positive_count': positive, 'negative_count': negative}))


if __name__ == '__main__':
    prove()
