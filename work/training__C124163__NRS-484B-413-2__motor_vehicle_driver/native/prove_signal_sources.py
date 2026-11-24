"""Source-bound positive/negative proof of the continuous-distance meter."""
import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from signal_distance import measure


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-work', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    source = Path(__file__).with_name('diagnostic-sources')
    expectations = {
        'other_long': (100.0, True, 300),
        'other_short': (70.0, False, 300),
        'district_long': (35.2, True, 100),
        'district_short': (20.0, False, 100),
    }
    positives = []
    for name, (distance, enough, feet) in expectations.items():
        result = measure(source / name)
        assert result['continuous_signal_distance_m'] == distance
        assert result['synthetic_numeric_distance_met'] is enough
        assert result['statutory_distance_ft'] == feet
        assert result['course_change_frame'] == 300 and result['frames'] == 600
        assert not result['weather_waiver_applied']
        positives.append(result)
    negatives = []
    with tempfile.TemporaryDirectory(dir=args.runtime_work) as temporary:
        target = Path(temporary) / 'bad'
        shutil.copytree(source / 'other_long', target)
        (target / 'native-samples.jsonl').unlink()
        for name in ('missing_rows', 'changed_rows', 'changed_district'):
            if name == 'changed_rows':
                shutil.copytree(source / 'other_long', target, dirs_exist_ok=True)
                path = target / 'native-samples.jsonl'
                path.write_bytes(path.read_bytes().replace(b'"signal_visible": true',
                                                           b'"signal_visible": false', 1))
            elif name == 'changed_district':
                shutil.copytree(source / 'other_long', target, dirs_exist_ok=True)
                path = target / 'context.json'
                path.write_bytes(path.read_bytes().replace(b'other_area', b'business_or_residential', 1))
            try:
                measure(target)
            except ValueError as exc:
                assert 'source hash mismatch' in str(exc)
                negatives.append({'case': name, 'error': str(exc)})
            else:
                raise AssertionError(name + ' accepted')
            shutil.copytree(source / 'other_long', target, dirs_exist_ok=True)
    proof = {
        'format': 'c124163-signal-distance-cpu-proof-v1', 'passed': True,
        'meter_sha256': sha(Path(__file__).with_name('signal_distance.py')),
        'positive': positives, 'negative': negatives,
        'physical_signal_pixels_confirmed': False,
        'original_native_observed': False, 'legal_verdict_claimed': False,
    }
    Path(args.output).write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'passed': True, 'positive': len(positives), 'negative': len(negatives)}))


if __name__ == '__main__':
    main()
