"""Exercise complete, incomplete and absent rider-turn originals as CPU diagnostics."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile

from rider_physical_outcome import assess


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_rows(path, values):
    path.write_text(''.join(json.dumps(value, allow_nan=False) + '\n' for value in values))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--kind', choices=['complete_motion', 'incomplete_motion', 'missing_evidence'], required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    source, output = Path(args.source), Path(args.output)
    if output.exists():
        raise ValueError('Retain prior result; choose fresh output')
    with tempfile.TemporaryDirectory(prefix='rider-physical-fixture-') as temporary:
        root = Path(temporary)
        for name in ('rider_motion.jsonl', 'trace.jsonl', 'video_frames.jsonl'):
            shutil.copy2(source / name, root / name)
        if args.kind == 'complete_motion':
            motion, trace = rows(root / 'rider_motion.jsonl'), rows(root / 'trace.jsonl')
            for index, (rider, point) in enumerate(zip(motion, trace)):
                yaw = [0, 0, 0, 0, 0, 15, 45, 70, 80][index]
                rider['rider_yaw_deg'] = yaw
                point['heading_deg'] = yaw
                point['position_m'][0] = float(point['position_m'][0]) + index * .5
                point['position']['x'] = point['position_m'][0]
            write_rows(root / 'rider_motion.jsonl', motion)
            write_rows(root / 'trace.jsonl', trace)
        elif args.kind == 'missing_evidence':
            (root / 'rider_motion.jsonl').unlink()
        result = assess(root)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[args.kind]
        assert result['physical_checks']['maneuver']['status'] == expected
        result['kind'] = args.kind
        result['source_original_sha256'] = {name: sha256((source / name).read_bytes()).hexdigest()
                                            for name in ('rider_motion.jsonl', 'trace.jsonl', 'video_frames.jsonl')}
        result['synthetic_input_sha256'] = {name: sha256((root / name).read_bytes()).hexdigest()
                                            for name in ('rider_motion.jsonl', 'trace.jsonl', 'video_frames.jsonl') if (root / name).is_file()}
        output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
        print(json.dumps({'kind': args.kind, 'status': expected,
                          'actual_native_capture': False, 'physical_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
