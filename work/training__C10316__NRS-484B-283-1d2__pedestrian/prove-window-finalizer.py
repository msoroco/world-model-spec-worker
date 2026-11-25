"""Generated 30-second saved-source diagnostic for the unselected countdown probes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FRAMES = 600


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))


def run_finalizer(attempt):
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join((str(ROOT / 'runtime'),
        str(ROOT / 'runtime/scenario_pipeline'), str(HERE / 'native'),
        env.get('PYTHONPATH', '')))
    return subprocess.run([sys.executable, str(HERE / 'native/finalize.py'),
        '--attempt', str(attempt), '--output', str(attempt / 'analysis-report.json')],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)


def make_video(folder, camera):
    width, height = camera['width'], camera['height']
    path = folder / (camera['name'] + '.mkv')
    subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
        '-f', 'lavfi', '-i', f'color=c=black:s={width}x{height}:r=20:d=30',
        '-frames:v', str(FRAMES), '-c:v', 'ffv1', '-level', '1', str(path)],
        check=True, capture_output=True, text=True, timeout=300)
    return path


def display_pixel_sha(video, width, height):
    decoded = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(video),
        '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
        check=True, capture_output=True, timeout=60).stdout
    assert len(decoded) == width * height * 3
    return hashlib.sha256(decoded).hexdigest()


def make_attempt(folder, suffix, source):
    folder.mkdir()
    construction = json.loads((HERE / 'draft-bundles' / suffix / 'primary/construction.json').read_text())
    config = json.loads(next(item['content'] for item in construction['files'] if item['path'] == 'config.json'))
    (folder / 'config.json').write_text(json.dumps(config) + '\n')
    shutil.copy2(HERE / 'native/road.xodr', folder / 'road.xodr')
    shutil.copy2(source / 'countdown-context.json', folder / 'countdown-context.json')
    samples = [json.loads(line) for line in (source / 'countdown_samples.jsonl').read_text().splitlines()]
    assert len(samples) == FRAMES
    videos = [make_video(folder, camera) for camera in config['cameras']]
    display_digest = display_pixel_sha(videos[-1], config['cameras'][-1]['width'],
                                       config['cameras'][-1]['height'])
    mapping, trace, evidence, native = [], [], [], []
    for index, sample in enumerate(samples):
        frame, time = sample['native_frame'], sample['time_s']
        x, y = sample['pedestrian_xy_m']
        sample['original_display_frame_sha256'] = display_digest
        mapped = {'video_frame': index, 'native_frame': frame, 'carla_frame': frame,
                  'time_s': time, 'source_rgb_sha256': {'display_close': display_digest}}
        mapping.append(mapped)
        trace.append({'frame': frame, 'time_s': time, 'position_m': [x, y, .5],
                      'synthetic_diagnostic': True})
        body = [[point[0], point[1], z] for point in sample['pedestrian_footprint_xy_m']
                for z in (0, 1.8)]
        evidence.append({'original_frame': frame, 'recording_time_s': time,
                         'ego': {'body_vertices_m': body}, 'synthetic_diagnostic': True})
        native.append({'frame': frame, 'time_s': time, 'synthetic_diagnostic': True})
    write_rows(folder / 'countdown_samples.jsonl', samples)
    for name, rows in (('video_frames.jsonl', mapping), ('trace.jsonl', trace),
                       ('capture/evidence.jsonl', evidence),
                       ('capture/native/frames.jsonl', native)):
        write_rows(folder / name, rows)
    (folder / 'capture/manifest.json').write_text(json.dumps({
        'extraction_confirmed': True, 'frames': FRAMES,
        'synthetic_diagnostic': True}) + '\n')
    return config


def main():
    root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
    root.mkdir(parents=True, exist_ok=True)
    source_summary = json.loads((HERE / 'draft-countdown-measurement-summary.json').read_text())
    source_root = Path(source_summary['retained_root'])
    with tempfile.TemporaryDirectory(prefix='window-finalizer-', dir=root) as scratch:
        scratch = Path(scratch)
        records = []
        for suffix in ('probe_01', 'probe_02'):
            good = scratch / (suffix + '-positive')
            config = make_attempt(good, suffix, source_root / suffix)
            hashes = {p.name: sha(p) for p in good.glob('*.mkv')}
            passed = run_finalizer(good)
            if passed.returncode:
                raise RuntimeError('Saved positive failed: ' + passed.stderr[-1600:])
            report = json.loads((good / 'analysis-report.json').read_text())
            result = json.loads((good / 'result.json').read_text())
            assert report['display_integrity']['pixel_integrity_verified'] is True
            assert report['display_integrity']['frames'] == FRAMES
            assert report['governing_context']['governing_device_source_verified'] is False
            assert result['accepted'] is False and result['legal_verdict_claimed'] is False
            assert len(report['source_derived_channel_hashes']) == 5
            assert all((good / 'channels' / (name + '.jsonl')).is_file()
                       for name in report['source_derived_channel_hashes'])
            assert {p.name: sha(p) for p in good.glob('*.mkv')} == hashes
            preexisting = scratch / (suffix + '-preexisting-channel')
            shutil.copytree(good, preexisting)
            (preexisting / 'result.json').unlink()
            (preexisting / 'analysis-report.json').unlink()
            failed_channel = run_finalizer(preexisting)
            assert failed_channel.returncode and 'Preexisting derived channels are not an acquisition source' in failed_channel.stderr
            missing = scratch / (suffix + '-missing')
            shutil.copytree(good, missing)
            (missing / 'result.json').unlink()
            (missing / 'analysis-report.json').unlink()
            shutil.rmtree(missing / 'channels')
            (missing / 'countdown_samples.jsonl').unlink()
            failed = run_finalizer(missing)
            assert failed.returncode and 'Missing required source: countdown_samples.jsonl' in failed.stderr
            changed = scratch / (suffix + '-changed-pixel')
            shutil.copytree(good, changed)
            (changed / 'result.json').unlink()
            (changed / 'analysis-report.json').unlink()
            shutil.rmtree(changed / 'channels')
            rows = [json.loads(line) for line in (changed / 'video_frames.jsonl').read_text().splitlines()]
            rows[17]['source_rgb_sha256']['display_close'] = '0' * 64
            write_rows(changed / 'video_frames.jsonl', rows)
            failed_pixel = run_finalizer(changed)
            assert failed_pixel.returncode and 'Original display RGB hash join differs at 17' in failed_pixel.stderr
            records.append({'case_id': config['case_id'], 'frames': FRAMES,
                'relation': result['measured_values']['clearance_relative_to_displayed_zero'],
                'video_sources': len(hashes), 'missing_source_rejected': True,
                'changed_pixel_hash_rejected': True, 'source_videos_unchanged': True,
                'preexisting_channel_rejected': True,
                'source_derived_channel_hashes': report['source_derived_channel_hashes'],
                'display_integrity': report['display_integrity'],
                'governing_context': report['governing_context'],
                'physical_acceptance_claimed': False})
    assert [row['relation'] for row in records] == ['before_zero', 'at_or_after_zero']
    print(json.dumps({'passed': True, 'records': records, 'selected_cases': 0,
                      'accepted_recordings': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
