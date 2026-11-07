"""Build and challenge 480-frame synthetic saved C111331 sources."""
import hashlib
import json
from pathlib import Path
import shutil

from measure_saved import measure

HERE = Path(__file__).resolve().parent
AID = HERE.parent.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in values))


def prove():
    summary = []
    for case in ('reference', 'contrast'):
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            authored = HERE / 'drafts' / case / candidate
            request = [json.loads(line) for line in (authored / 'native-requests.jsonl').read_text().splitlines()]
            folder = HERE / 'synthetic-saved' / case / candidate
            folder.mkdir(parents=True, exist_ok=True)
            native = []
            video = []
            for row in request:
                i = row['frame']
                native.append({'source_kind': 'synthetic_cpu_native_observation',
                               'request_index': i, 'native_frame': 1000 + i,
                               'time_s': row['time_s'], 'native_center_xy_m': row['native_center_xy_m'],
                               'native_yaw_deg': row['native_yaw_deg_requested'],
                               'native_body_xy_m': row['native_body_xy_m'],
                               'observed_signal_state': row['signal_phase_requested'],
                               'signal_actor_id': 601})
                video.append({'video_frame': i, 'native_frame': 1000 + i,
                              'carla_frame': 1000 + i,
                              'time_s': row['time_s'], 'synthetic_frame_only': True})
            write_rows(folder / 'native_samples.jsonl', native)
            write_rows(folder / 'video_frames.jsonl', video)
            result = measure(folder, AID + '__' + case, candidate)
            (folder / 'measurement.json').write_text(json.dumps(result, indent=2) + '\n')
            assert result['observed_signal_phase_at_entry'] == ('yellow' if case == 'reference' else 'red')
            assert not result['physical_native_evidence'] and not result['original_pixel_visibility_verified']
            negatives = []
            bad = folder / 'negative-input'
            if bad.exists():
                shutil.rmtree(bad)
            bad.mkdir()
            for filename in ('native_samples.jsonl', 'video_frames.jsonl'):
                shutil.copy2(folder / filename, bad / filename)
            (bad / 'native_samples.jsonl').unlink()
            try:
                measure(bad, AID + '__' + case, candidate)
            except ValueError as exc:
                assert 'Missing required source' in str(exc)
                negatives.append('missing_native_source')
            else:
                raise AssertionError('Missing Native source accepted')
            write_rows(bad / 'native_samples.jsonl', native)
            corrupted = list(video)
            corrupted[200] = dict(corrupted[200], native_frame=9999)
            write_rows(bad / 'video_frames.jsonl', corrupted)
            try:
                measure(bad, AID + '__' + case, candidate)
            except ValueError as exc:
                assert 'frame join differs' in str(exc)
                negatives.append('broken_camera_join')
            else:
                raise AssertionError('Broken camera join accepted')
            write_rows(bad / 'video_frames.jsonl', video)
            corrupted = [dict(n) for n in native]
            corrupted[200] = dict(corrupted[200], observed_signal_state='blue')
            write_rows(bad / 'native_samples.jsonl', corrupted)
            try:
                measure(bad, AID + '__' + case, candidate)
            except ValueError as exc:
                assert 'phase missing' in str(exc)
                negatives.append('invalid_observed_phase')
            else:
                raise AssertionError('Invalid observed phase accepted')
            shutil.rmtree(bad)
            summary.append({'case': case, 'candidate': candidate,
                            'measurement_sha256': sha(folder / 'measurement.json'),
                            'native_sha256': sha(folder / 'native_samples.jsonl'),
                            'video_frames_sha256': sha(folder / 'video_frames.jsonl'),
                            'negatives_rejected': negatives,
                            'physical_success_claimed': False})
    output = {'format': 'c111331-synthetic-saved-proof-v1', 'rows': summary,
              'physical_success_claimed': False, 'original_pixels_verified': False}
    (HERE / 'synthetic-saved-summary.json').write_text(json.dumps(output, indent=2) + '\n')
    return {'passed': True, 'bundles': len(summary), 'negative_rejections': 3 * len(summary),
            'summary_sha256': sha(HERE / 'synthetic-saved-summary.json')}


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
