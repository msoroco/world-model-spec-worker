"""Run the exact reference primary's dusk transition through saved-source code.

This uses generated FFV1 media and synthetic review rows only. It tests the
binding, join and finalizer path without claiming original Native observation.
"""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from bind_lighting_sources import VIEWS
from finalize_lighting_sources import finalize

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ROOT = PACKAGE.parents[1]
SCRATCH = ROOT / '.runtime-work' / 'c230241-reference-saved-temporal'
CASE_ID = PACKAGE.name + '__reference'
FRAMES = 600


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_rows(path, values):
    path.write_text(''.join(json.dumps(value, sort_keys=True) + '\n'
                            for value in values))


def run(command):
    subprocess.run(command, check=True, timeout=300,
                   capture_output=True, text=True)


def main():
    manifest_path = PACKAGE / 'draft-primary-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    case = next(item for item in manifest['cases'] if item['case_id'] == CASE_ID)
    construction_path = PACKAGE / case['construction']
    if sha(construction_path) != case['construction_sha256']:
        raise ValueError('Exact reference primary construction changed')
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True)
    for view, color in zip(VIEWS, ('red', 'green', 'blue', 'yellow')):
        run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi',
             '-i', f'color=c={color}:s=64x64:r=20:d=30',
             '-frames:v', str(FRAMES), '-c:v', 'ffv1',
             str(SCRATCH / (view + '.mkv'))])
    inputs = [part for view in VIEWS for part in ('-i', str(SCRATCH / (view + '.mkv')))]
    scale = ''.join(f'[{i}:v]scale=960:540[v{i}];' for i in range(4))
    run(['ffmpeg', '-nostdin', '-v', 'error', *inputs,
         '-filter_complex', scale + '[v0][v1][v2][v3]xstack=inputs=4:layout=0_0|960_0|0_540|960_540[out]',
         '-map', '[out]', '-frames:v', str(FRAMES), '-c:v', 'ffv1',
         str(SCRATCH / 'raw.mkv')])
    native = [{'source_kind': 'synthetic_native_sample',
               'video_frame': i, 'native_frame': 4000 + i,
               'time_s': i / 20,
               'velocity_mps': [0.0 if i == 201 else 2.0, 0.0, 0.0],
               'light_state_observed': 3} for i in range(FRAMES)]
    mapping = [{'video_frame': i, 'native_frame': 4000 + i,
                'carla_frame': 4000 + i, 'time_s': i / 20}
               for i in range(FRAMES)]
    review = [{'source_kind': 'synthetic_native_sample',
               'video_frame': i, 'native_frame': 4000 + i,
               'time_s': i / 20, 'utc_s': 11790 + i / 20,
               'headlamp_lit': i not in (199, 200),
               'tail_lamp_lit': i != 201,
               'headlamp_white': True, 'tail_lamp_red': True,
               'front_visible_ft': 300.0, 'rear_visible_ft': 500.0,
               'discernible_500ft': True} for i in range(FRAMES)]
    write_rows(SCRATCH / 'native-lighting-frames.jsonl', native)
    write_rows(SCRATCH / 'video_frames.jsonl', mapping)
    write_rows(SCRATCH / 'lighting-review.jsonl', review)
    source_hashes = {view: sha(SCRATCH / (view + '.mkv'))
                     for view in (*VIEWS, 'raw')}
    source_hashes['native-lighting-frames.jsonl'] = sha(SCRATCH / 'native-lighting-frames.jsonl')
    source_hashes['video_frames.jsonl'] = sha(SCRATCH / 'video_frames.jsonl')
    (SCRATCH / 'lighting-review-context.json').write_text(json.dumps({
        'source_kind': 'synthetic_native_sample',
        'source_sha256': source_hashes, 'diagnostic_only': True}, indent=2) + '\n')
    measurement_context = SCRATCH / 'lighting-measure-context.json'
    measurement_context.write_text(json.dumps({
        'source_kind': 'synthetic_native_sample',
        'vehicle_class_source': 'synthetic reference motorcycle',
        'clock_source': 'synthetic UTC clock',
        'range_calibration_source': 'synthetic distance review',
        'visibility_review_source': 'synthetic 500-foot review',
        'sunset_utc_s': 10000, 'next_sunrise_utc_s': 50000,
        'vehicle_covered': True, 'headlamp_count': 1,
        'tail_lamp_rear_mounted': True}, indent=2) + '\n')
    receipt_path = finalize(SCRATCH, measurement_context,
                            SCRATCH / 'saved-finalization')
    receipt = json.loads(receipt_path.read_text())
    counts = receipt['measurement']['measurements']
    expected = {'night_window_frames': 400,
                'required_burning_frames': 399,
                'headlamp_dark_frames': 1,
                'tail_lamp_dark_frames': 0,
                'front_below_300ft_frames': 0,
                'rear_below_500ft_frames': 0}
    if (not receipt['binding']['source_integrity_verified']
            or receipt['binding']['frames'] != FRAMES
            or receipt['join']['frames'] != FRAMES
            or receipt['measurement']['frames'] != FRAMES
            or any(counts[key] != value for key, value in expected.items())
            or receipt['diagnostic_only'] is not True
            or receipt['original_native_verified'] is not False
            or receipt['physical_visibility_verified'] is not False
            or receipt['legal_verdict_claimed'] is not False):
        raise ValueError('Exact reference dusk saved-source proof differs')
    output = {'format': 'c230241-reference-saved-temporal-cpu-v1',
              'passed': True, 'case_id': CASE_ID, 'candidate_id': 'primary',
              'selected_delivery': False, 'diagnostic_only': True,
              'manifest_sha256': sha(manifest_path),
              'construction_sha256': sha(construction_path),
              'source_hashes': source_hashes,
              'review_sha256': sha(SCRATCH / 'lighting-review.jsonl'),
              'saved_receipt_sha256': sha(receipt_path),
              'measurement': expected,
              'frames': FRAMES, 'original_native_verified': False,
              'physical_visibility_verified': False,
              'legal_verdict_claimed': False}
    destination = HERE / 'reference-saved-temporal-proof.json'
    destination.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'passed': True, 'case_id': CASE_ID,
                      'saved_receipt_sha256': sha(receipt_path)}))


if __name__ == '__main__':
    main()
