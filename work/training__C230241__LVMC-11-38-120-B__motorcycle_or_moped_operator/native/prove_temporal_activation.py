"""Prove the exact twilight, motion and low-visibility activation transitions.

All rows are synthetic source-shaped diagnostics and imply no physical or legal
outcome. The 30-second, 20-Hz case contract stays intact.
"""
import hashlib
import json
from pathlib import Path

from measure_lighting import measure

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SCRATCH = ROOT / '.runtime-work' / 'c230241-temporal-activation'
FRAMES = 600


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_rows(path, values):
    path.write_text(''.join(json.dumps(item, sort_keys=True) + '\n' for item in values))


def run_case(name, start_utc, sunset, sunrise, modify, expected):
    folder = SCRATCH / name
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / 'joined-lighting.jsonl'
    context = folder / 'context.json'
    frame_map = folder / 'video_frames.jsonl'
    rows = [{'video_frame': i, 'native_frame': 3000 + i,
             'time_s': i / 20, 'utc_s': start_utc + i / 20,
             'speed_mps': 2.0, 'headlamp_lit': True, 'tail_lamp_lit': True,
             'headlamp_white': True, 'tail_lamp_red': True,
             'front_visible_ft': 300, 'rear_visible_ft': 500,
             'discernible_500ft': True} for i in range(FRAMES)]
    modify(rows)
    write_rows(source, rows)
    write_rows(frame_map, [{'video_frame': i, 'native_frame': 3000 + i,
                            'carla_frame': 3000 + i, 'time_s': i / 20}
                           for i in range(FRAMES)])
    context.write_text(json.dumps({
        'source_kind': 'synthetic_native_sample',
        'vehicle_class_source': 'synthetic motorcycle class',
        'clock_source': 'synthetic UTC clock',
        'range_calibration_source': 'synthetic calibrated distance',
        'visibility_review_source': 'synthetic 500-foot review',
        'vehicle_covered': True, 'headlamp_count': 1,
        'tail_lamp_rear_mounted': True,
        'sunset_utc_s': sunset, 'next_sunrise_utc_s': sunrise}, indent=2) + '\n')
    result = measure(source, context, frame_map)
    counts = result['measurements']
    for key, wanted in expected.items():
        if counts[key] != wanted:
            raise ValueError(f'{name}: {key}={counts[key]} expected {wanted}')
    if (result['frames'] != FRAMES or result['duration_s'] != 30
            or result['original_native_verified'] is not False
            or result['physical_visibility_verified'] is not False
            or result['legal_verdict_claimed'] is not False):
        raise ValueError('Diagnostic source limits or duration differ')
    return {'case': name, 'expected': expected, 'source_sha256': sha(source),
            'context_sha256': sha(context), 'frame_map_sha256': sha(frame_map)}


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    checks = []
    def dusk(rows):
        rows[199]['headlamp_lit'] = False
        rows[200]['headlamp_lit'] = False
        rows[201]['speed_mps'] = 0
        rows[201]['tail_lamp_lit'] = False
    checks.append(run_case('sunset-plus-half-hour', 11790, 10000, 50000,
                           dusk, {'night_window_frames': 400,
                                  'required_burning_frames': 399,
                                  'headlamp_dark_frames': 1,
                                  'tail_lamp_dark_frames': 0}))
    def dawn(rows):
        rows[200]['headlamp_lit'] = False
        rows[201]['headlamp_lit'] = False
    checks.append(run_case('sunrise-minus-half-hour', 48190, 10000, 50000,
                           dawn, {'night_window_frames': 201,
                                  'required_burning_frames': 201,
                                  'headlamp_dark_frames': 1}))
    def low_visibility(rows):
        rows[300]['discernible_500ft'] = False
        rows[300]['tail_lamp_lit'] = False
        rows[301]['discernible_500ft'] = False
        rows[301]['speed_mps'] = 0
        rows[301]['tail_lamp_lit'] = False
    checks.append(run_case('daylight-low-visibility-and-motion', 9000, 10000, 50000,
                           low_visibility, {'night_window_frames': 0,
                                            'low_visibility_frames': 2,
                                            'required_burning_frames': 1,
                                            'tail_lamp_dark_frames': 1}))
    # A changed final UTC timestamp must fail the original clock join even
    # if its 600-frame inventory and frame map are still complete.
    folder = SCRATCH / 'daylight-low-visibility-and-motion'
    source = folder / 'joined-lighting.jsonl'
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    rows[-1]['utc_s'] += 0.05
    altered = folder / 'changed-clock.jsonl'
    write_rows(altered, rows)
    try:
        measure(altered, folder / 'context.json', folder / 'video_frames.jsonl')
    except ValueError as error:
        if 'Original lighting clock join differs at 599' not in str(error):
            raise
        rejection = str(error)
    else:
        raise ValueError('Changed final UTC source accepted')
    receipt = {'format': 'c230241-temporal-activation-cpu-v1', 'passed': True,
               'diagnostic_only': True, 'source_kind': 'synthetic_native_sample',
               'frames_per_case': FRAMES, 'cases': checks,
               'negative_changed_final_clock': rejection,
               'measurement_sha256': sha(HERE / 'measure_lighting.py'),
               'auditor_sha256': sha(Path(__file__)),
               'original_native_verified': False,
               'physical_visibility_verified': False,
               'legal_verdict_claimed': False}
    output = HERE / 'temporal-activation-proof.json'
    output.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'cases': len(checks),
                      'negative_controls_rejected': 1}))


if __name__ == '__main__':
    main()
