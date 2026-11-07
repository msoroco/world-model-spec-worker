"""Exercise original-capture joins with temporary, explicitly synthetic CPU media."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from prepare_original import decoded_hashes, prepare, sha

ROOT = Path(__file__).resolve().parent
FFMPEG = shutil.which('ffmpeg') or str(ROOT.parents[1] / '..' / '.runtime-work' / 'linux_arm64' / 'ffmpeg')
NAMES = ('observed-actors.jsonl', 'video_frames.jsonl',
         'officer-direction-review.json', 'officer_reference.mkv')


def write_rows(path, data):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in data))


def negative(source, root, case, label, change, expected):
    bad = root / ('bad-' + label)
    bad.mkdir()
    for name in NAMES:
        shutil.copyfile(source / name, bad / name)
    change(bad)
    try:
        prepare(bad, root / ('out-' + label), case, FFMPEG)
    except ValueError as exc:
        if expected not in str(exc):
            raise AssertionError(f'{label}: unexpected rejection {exc}') from exc
        return {'label': label, 'rejected': str(exc)}
    raise AssertionError(label + ': invalid source accepted')


def prove():
    ffmpeg = FFMPEG
    if not Path(ffmpeg).is_file():
        raise ValueError('FFmpeg required for original-path proof')
    positives, negatives = [], []
    with tempfile.TemporaryDirectory(prefix='c405647-officer-original-path-') as tmp:
        root = Path(tmp)
        for case in ('exception_1_1', 'exception_1_2'):
            fixture = ROOT / 'saved-fixtures' / case / 'primary'
            authored = [json.loads(line) for line in (fixture / 'native-requests.jsonl').read_text().splitlines()]
            cues = json.loads((fixture / 'direction-review.json').read_text())['frames']
            source = root / case
            source.mkdir()
            video_path = source / 'officer_reference.mkv'
            run = subprocess.run([ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error',
                                  '-f', 'lavfi', '-i', 'color=c=black:s=16x16:r=20:d=24',
                                  '-frames:v', '480', '-an', '-c:v', 'ffv1', str(video_path)],
                                 capture_output=True, text=True, check=False, timeout=90)
            if run.returncode:
                raise ValueError('CPU mock encoder failed: ' + run.stderr[-300:])
            hashes = decoded_hashes(video_path, ffmpeg)
            actors, videos, notes = [], [], []
            for i, row in enumerate(authored):
                native_id = 1000 + i
                sx, sy = row['subject_request']['x_m'], row['subject_request']['y_m']
                ax, ay = row['approach_request']['x_m'], row['approach_request']['y_m']
                body = [[sx + dx, sy + dy] for dx, dy in
                        ((-2.25, -.9), (-2.25, .9), (2.25, -.9), (2.25, .9))]
                actors.append({'frame': i, 'native_frame': native_id, 'time_s': row['time_s'],
                               'source_kind': 'cpu_mock',
                               'actors': {'subject': {'native_center_xy_m': [sx, sy],
                                                      'native_body_xy_m': body},
                                          'approach': {'native_center_xy_m': [ax, ay]}},
                               'officer_direction_requested': row['officer_direction_request']['requested'],
                               'actual_direction_identity_content_recipient_observed': None})
                videos.append({'video_frame': i, 'native_frame': native_id,
                               'carla_frame': native_id, 'time_s': row['time_s']})
                notes.append(dict(cues[i], video_frame=i, native_frame=native_id,
                                  pixel_frame_sha256=hashes[i]))
            write_rows(source / NAMES[0], actors)
            write_rows(source / NAMES[1], videos)
            review = {'source_kind': 'cpu_mock_original_path', 'reviewer': 'cpu_test',
                      'source_video_sha256': sha(video_path), 'frames': notes}
            (source / NAMES[2]).write_text(json.dumps(review, sort_keys=True) + '\n')
            result = prepare(source, root / ('saved-' + case), case, ffmpeg)
            if result['frames'] != 480 or result['legal_exception_verdict'] is not None or \
                    result['verified_communication_frames'] != 0 or \
                    result['approach_catchup_frame'] != 182 or \
                    result['cue_frames'] != (0 if case == 'exception_1_1' else 60) or \
                    result['cue_overlaps_request'] != (case == 'exception_1_2'):
                raise AssertionError('CPU mock overstated original-path proof')
            positives.append({'case': case, 'result': result,
                              'saved_actor_sha256': sha(root / ('saved-' + case) / 'actor-frames.jsonl')})
            if case == 'exception_1_2':
                def change_review(folder, fn):
                    packet = json.loads((folder / NAMES[2]).read_text())
                    fn(packet)
                    (folder / NAMES[2]).write_text(json.dumps(packet, sort_keys=True) + '\n')
                negatives.append(negative(source, root, case, 'video-hash',
                                          lambda folder: change_review(folder, lambda p: p.update(source_video_sha256='0'*64)),
                                          'video source hash differs'))
                negatives.append(negative(source, root, case, 'frame-hash',
                                          lambda folder: change_review(folder, lambda p: p['frames'][145].update(pixel_frame_sha256='0'*64)),
                                          'decoded pixel frame hash differs'))
                negatives.append(negative(source, root, case, 'reviewer',
                                          lambda folder: change_review(folder, lambda p: p.update(reviewer='')),
                                          'CPU mock reviewer differs'))
                def change_actor(folder, fn):
                    packet = [json.loads(line) for line in (folder / NAMES[0]).read_text().splitlines()]
                    fn(packet)
                    write_rows(folder / NAMES[0], packet)
                negatives.append(negative(source, root, case, 'request-as-observation',
                                          lambda folder: change_actor(folder, lambda p: p[145].update(
                                              actual_direction_identity_content_recipient_observed=True)),
                                          'Requested direction substituted'))
                negatives.append(negative(source, root, case, 'native-frame',
                                          lambda folder: change_actor(folder, lambda p: p[145].update(native_frame=17)),
                                          'frame join differs'))
                negatives.append(negative(source, root, case, 'mock-identity',
                                          lambda folder: change_review(folder, lambda p: p['frames'][145].update(identity_verified=True)),
                                          'CPU mock promoted'))
    proof = {'format': 'c405647-original-path-cpu-mock-proof-v1',
             'processor_sha256': sha(ROOT / 'prepare_original.py'),
             'positive': positives, 'negative': negatives,
             'original_native_pixels_seen': False, 'physical_officer_signal_seen': False,
             'legal_exception_verdict': None}
    (ROOT / 'original-path-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    return proof


if __name__ == '__main__':
    print(json.dumps(prove(), indent=2))
