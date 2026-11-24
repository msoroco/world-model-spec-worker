"""Build four 30-second synthetic source traces for the statutory distance fork."""
import hashlib
import json
from pathlib import Path

from signal_distance import FRAMES, HZ

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent.name
CASES = {
    'other_long': ('other_area', 'clear', 50),
    'other_short': ('other_area', 'clear', 125),
    'district_long': ('business_or_residential', 'rain', 212),
    'district_short': ('business_or_residential', 'rain', 250),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    root = HERE / 'diagnostic-sources'
    records = []
    for condition, (district, weather, signal_start) in CASES.items():
        target = root / condition
        target.mkdir(parents=True, exist_ok=True)
        context = {
            'source_kind': 'synthetic_native_sample', 'district_class': district,
            'weather': weather, 'course_change_request_frame': 300,
            'signal_activity_is_observed_pixels': False,
            'native_district_and_weather_verified': False,
        }
        (target / 'context.json').write_text(json.dumps(context, indent=2) + '\n')
        rows = []
        for frame in range(FRAMES):
            rows.append({
                'frame': frame, 'time_s': frame / HZ,
                'odometer_native_m': round(frame * 0.4, 6),
                'signal_visible': signal_start <= frame <= 300,
                'course_change_started': frame == 300,
                'source_kind': 'synthetic_native_sample',
            })
        (target / 'native-samples.jsonl').write_text(
            ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
        index = {
            'format': 'c124163-signal-distance-source-v1',
            'assignment_id': ASSIGNMENT, 'condition': condition,
            'frames': FRAMES, 'rate_hz': HZ,
            'files': {name: sha(target / name)
                      for name in ('native-samples.jsonl', 'context.json')},
            'claim': 'synthetic source diagnostic; no original Native or legal outcome',
        }
        (target / 'source-index.json').write_text(json.dumps(index, indent=2) + '\n')
        records.append({'condition': condition, 'source_index_sha256': sha(target / 'source-index.json')})
    print(json.dumps({'conditions': records, 'frames_per_case': FRAMES}))


if __name__ == '__main__':
    main()
