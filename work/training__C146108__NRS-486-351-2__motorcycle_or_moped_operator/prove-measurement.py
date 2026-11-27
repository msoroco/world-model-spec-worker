"""Exercise the bundled source-bound pass measurement with positive and negative saved sources."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__controlled_2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rectangle(x, y, half_length, half_width):
    return [[x - half_length, y - half_width], [x - half_length, y + half_width],
            [x + half_length, y - half_width], [x + half_length, y + half_width]]


def make(attempt):
    attempt.mkdir()
    cameras = ('overview', 'approach', 'reference_corner', 'driver_reference')
    with (attempt / 'participant-poses.jsonl').open('w') as poses, (attempt / 'video_frames.jsonl').open('w') as frames:
        for index in range(600):
            time = index / 20
            native = 1000 + index
            row = {'native_frame': native, 'video_frame': index, 'time_s': time,
                   'rider_body_xy_m': rectangle(-80 + 5 * time, -4.7, 1.2, .4),
                   'motor_body_xy_m': rectangle(-50 + 3 * time, -1.5, 2.2, .9)}
            poses.write(json.dumps(row) + '\n')
            frames.write(json.dumps({'native_frame': native, 'video_frame': index,
                'time_s': time, 'camera_native_frames': {name: native for name in cameras}}) + '\n')
    (attempt / 'pass-context.json').write_text(json.dumps({'rider_class': 'motorcycle',
        'passed_class': 'motor_vehicle', 'driver_consent_review_pending': True,
        'subsection_3_text_review_pending': True}) + '\n')
    (attempt / 'road.xodr').write_text('<OpenDRIVE><road name="one-way-two-lane"/></OpenDRIVE>\n')
    for name in cameras:
        (attempt / (name + '.mkv')).write_bytes(('synthetic-source-placeholder-' + name).encode())


def main():
    manifest = json.loads((HERE / 'draft-two-case-manifest.json').read_text())
    item = manifest['cases'][1]
    construction = HERE / item['construction']
    if sha(construction) != item['construction_sha256']:
        raise ValueError('Construction hash mismatch')
    bundled = ROOT / '.runtime-work/c146108-moto/offline-pass-v2/measure_pass.py'
    expected = next(file['content'] for file in json.loads(construction.read_text())['files']
                    if file['path'] == 'measure_pass.py')
    if bundled.read_text() != expected:
        raise ValueError('Bundled measurement differs from construction')
    output_root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
    output_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_root, prefix='c146108-moto-proof-') as temp:
        root = Path(temp)
        positive = root / 'positive'
        make(positive)
        result_path = root / 'measurement.json'
        positive_run = subprocess.run([sys.executable, str(bundled), '--attempt', str(positive),
            '--output', str(result_path)], text=True, capture_output=True)
        if positive_run.returncode:
            raise ValueError(positive_run.stderr)
        result = json.loads(result_path.read_text())
        if not (result['first_behind_frame'] < result['first_overlap_frame'] < result['first_clear_ahead_frame']):
            raise ValueError('Pass order wrong')
        if result['source_sha256']['participant-poses.jsonl'] != sha(positive / 'participant-poses.jsonl'):
            raise ValueError('Original pose hash not bound')
        if result['legal_verdict_claimed'] or result['physical_acceptance_claimed']:
            raise ValueError('Diagnostic claimed acceptance')
        (positive / 'participant-poses.jsonl').unlink()
        negative_run = subprocess.run([sys.executable, str(bundled), '--attempt', str(positive),
            '--output', str(root / 'negative.json')], text=True, capture_output=True)
        if negative_run.returncode == 0 or 'Missing required source: participant-poses.jsonl' not in negative_run.stderr:
            raise ValueError('Missing original pose was not rejected')
        adjacent = root / 'adjacent'
        make(adjacent)
        pose_path = adjacent / 'participant-poses.jsonl'
        rows = [json.loads(line) for line in pose_path.read_text().splitlines()]
        rows[300]['rider_body_xy_m'] = rectangle(-80 + 5 * 15, -9.0, 1.2, .4)
        pose_path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        wrong_lane = subprocess.run([sys.executable, str(bundled), '--attempt', str(adjacent),
            '--output', str(root / 'wrong-lane.json')], text=True, capture_output=True)
        if wrong_lane.returncode == 0 or 'Participant body departed shared lane at frame 300' not in wrong_lane.stderr:
            raise ValueError('Different-lane body was not rejected')
        print(json.dumps({'passed': True, 'case_id': CASE,
            'construction_sha256': item['construction_sha256'],
            'bundled_measurement_sha256': sha(bundled),
            'first_overlap_frame': result['first_overlap_frame'],
            'first_clear_ahead_frame': result['first_clear_ahead_frame'],
            'minimum_lateral_surface_gap_m': result['minimum_lateral_surface_gap_during_overlap_m'],
            'missing_original_pose_rejected': True,
            'adjacent_lane_body_rejected': True,
            'videos_are_synthetic_placeholders': True,
            'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
