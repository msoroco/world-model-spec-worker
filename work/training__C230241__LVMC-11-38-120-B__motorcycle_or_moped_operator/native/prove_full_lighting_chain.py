"""Exercise the 600-frame source binding, review join and lighting measurement.

All inputs made here are synthetic diagnostics. They are never Native evidence.
"""
import copy
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from bind_lighting_sources import VIEWS, bind
from finalize_lighting_sources import finalize
from join_lighting_review import join
from measure_lighting import measure


HERE = Path(__file__).resolve().parent
SCRATCH = HERE.parents[2] / '.runtime-work' / 'c230241-full-lighting-chain'
FRAMES = 600


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))


def reject(label, action, phrase):
    try:
        action()
    except ValueError as exc:
        assert phrase in str(exc), (label, str(exc))
        return {'case': label, 'rejected': str(exc)}
    raise AssertionError(label + ' unexpectedly accepted')


def main():
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True)
    for view, color in zip(VIEWS, ('red', 'green', 'blue', 'yellow')):
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi',
                        '-i', f'color=c={color}:s=64x64:r=20:d=30',
                        '-frames:v', str(FRAMES), '-c:v', 'ffv1',
                        str(SCRATCH / (view + '.mkv'))], check=True, timeout=180)
    native = [{'source_kind': 'synthetic_native_sample',
               'video_frame': i, 'native_frame': 2000 + i, 'time_s': i / 20,
               'velocity_mps': [2.0, 0.0, 0.0], 'light_state_observed': 3}
              for i in range(FRAMES)]
    mapping = [{'video_frame': i, 'native_frame': 2000 + i,
                'carla_frame': 2000 + i, 'time_s': i / 20}
               for i in range(FRAMES)]
    review = [{'source_kind': 'synthetic_native_sample',
               'video_frame': i, 'native_frame': 2000 + i, 'time_s': i / 20,
               'utc_s': 1_000_000 + i / 20, 'headlamp_lit': True,
               'tail_lamp_lit': True, 'headlamp_white': True,
               'tail_lamp_red': True, 'front_visible_ft': 300.0,
               'rear_visible_ft': 500.0, 'discernible_500ft': True}
              for i in range(FRAMES)]
    trace_path = SCRATCH / 'native-lighting-frames.jsonl'
    map_path = SCRATCH / 'video_frames.jsonl'
    review_path = SCRATCH / 'lighting-review.jsonl'
    context_path = SCRATCH / 'lighting-review-context.json'
    measure_context_path = SCRATCH / 'lighting-measure-context.json'
    joined_path = SCRATCH / 'joined-lighting.jsonl'
    write_rows(trace_path, native)
    write_rows(map_path, mapping)
    write_rows(review_path, review)
    hashes = {view: sha(SCRATCH / (view + '.mkv')) for view in VIEWS}
    hashes[trace_path.name] = sha(trace_path)
    hashes[map_path.name] = sha(map_path)
    context = {'source_kind': 'synthetic_native_sample',
               'source_sha256': hashes, 'diagnostic_only': True}
    context_path.write_text(json.dumps(context, indent=2) + '\n')
    measure_context = {'source_kind': 'synthetic_native_sample',
                       'vehicle_class_source': 'synthetic motorcycle fixture',
                       'clock_source': 'synthetic UTC clock',
                       'range_calibration_source': 'synthetic range values',
                       'visibility_review_source': 'synthetic review values',
                       'sunset_utc_s': 990_000, 'next_sunrise_utc_s': 1_030_000,
                       'vehicle_covered': True, 'headlamp_count': 1,
                       'tail_lamp_rear_mounted': True}
    measure_context_path.write_text(json.dumps(measure_context, indent=2) + '\n')
    binding = bind(SCRATCH)
    joined = join(trace_path, review_path, map_path, joined_path)
    measured = measure(joined_path, measure_context_path, map_path)
    counts = measured['measurements']
    assert binding['frames'] == joined['frames'] == measured['frames'] == FRAMES
    assert counts['required_burning_frames'] == FRAMES
    assert counts['front_below_300ft_frames'] == 0
    assert counts['rear_below_500ft_frames'] == 0
    assert joined['joined_sha256'] == measured['source_sha256']
    checks = [{'case': '600-frame-positive', 'measurements': counts}]

    context['diagnostic_only'] = False
    context_path.write_text(json.dumps(context, indent=2) + '\n')
    checks.append(reject('synthetic-review-as-original',
                         lambda: bind(SCRATCH),
                         'Review context source kind differs'))
    context['diagnostic_only'] = True
    context_path.write_text(json.dumps(context, indent=2) + '\n')
    mixed_review = copy.deepcopy(review)
    mixed_review[0]['source_kind'] = 'calibrated_original_review'
    write_rows(review_path, mixed_review)
    checks.append(reject('mixed-synthetic-and-original-row',
                         lambda: bind(SCRATCH),
                         'review source kind differs'))
    write_rows(review_path, review)

    changed_review = copy.deepcopy(review)
    changed_review[300]['front_visible_ft'] = 299.0
    write_rows(review_path, changed_review)
    # A review is separate from the captured sources: its hash changes in the
    # resulting join and measured receipt, while source hashes stay fixed.
    binding_again = bind(SCRATCH)
    changed_path = SCRATCH / 'changed-joined-lighting.jsonl'
    changed_join = join(trace_path, review_path, map_path, changed_path)
    changed_measure = measure(changed_path, measure_context_path, map_path)
    assert binding_again['source_sha256'] == binding['source_sha256']
    assert changed_measure['measurements']['front_below_300ft_frames'] == 1
    assert changed_join['review_source_sha256'] != joined['review_source_sha256']
    checks.append({'case': 'one-foot-below-front-boundary',
                   'front_below_300ft_frames': 1})
    write_rows(review_path, review)
    final_receipt_path = finalize(SCRATCH, measure_context_path,
                                  SCRATCH / 'saved-finalization')
    final_receipt = json.loads(final_receipt_path.read_text())
    assert final_receipt['measurement']['measurements'] == counts
    assert final_receipt['join']['joined_sha256'] == final_receipt['measurement']['source_sha256']
    checks.append({'case': 'saved-finalizer-positive',
                   'receipt_sha256': sha(final_receipt_path)})

    mismatched_context = dict(measure_context,
                              source_kind='calibrated_original_review')
    measure_context_path.write_text(json.dumps(mismatched_context, indent=2) + '\n')
    checks.append(reject('synthetic-measurement-as-original',
                         lambda: finalize(SCRATCH, measure_context_path,
                                          SCRATCH / 'mismatched-finalization'),
                         'Measurement context source kind differs'))
    measure_context_path.write_text(json.dumps(measure_context, indent=2) + '\n')

    bad_mapping = copy.deepcopy(mapping)
    bad_mapping[301]['native_frame'] += 1
    write_rows(map_path, bad_mapping)
    context['source_sha256'][map_path.name] = sha(map_path)
    context_path.write_text(json.dumps(context, indent=2) + '\n')
    checks.append(reject('changed-frame-join', lambda: bind(SCRATCH),
                         'Review frame identity differs'))
    write_rows(map_path, mapping)
    context['source_sha256'][map_path.name] = sha(map_path)
    context_path.write_text(json.dumps(context, indent=2) + '\n')

    damaged_video = SCRATCH / 'approach.mkv'
    original_video = damaged_video.read_bytes()
    damaged_video.write_bytes(original_video[:len(original_video) // 2])
    context['source_sha256']['approach'] = sha(damaged_video)
    context_path.write_text(json.dumps(context, indent=2) + '\n')
    checks.append(reject('damaged-source-video', lambda: bind(SCRATCH),
                         'source video'))
    damaged_video.write_bytes(original_video)
    context['source_sha256']['approach'] = sha(damaged_video)
    context_path.write_text(json.dumps(context, indent=2) + '\n')

    (SCRATCH / 'approach.mkv').unlink()
    checks.append(reject('missing-source-video', lambda: bind(SCRATCH),
                         'Original video, trace, frame map or independent review missing'))

    receipt = {'format': 'c230241-full-lighting-chain-diagnostic-v1',
               'diagnostic_only': True, 'synthetic_frames': FRAMES,
               'original_native_verified': False,
               'physical_visibility_verified': False,
               'checks': checks, 'binding_sha256': sha(HERE / 'bind_lighting_sources.py'),
               'join_sha256': sha(HERE / 'join_lighting_review.py'),
               'measure_sha256': sha(HERE / 'measure_lighting.py'),
               'finalizer_sha256': sha(HERE / 'finalize_lighting_sources.py'),
               'prover_sha256': sha(Path(__file__))}
    output = HERE / 'full-lighting-chain-proof.json'
    output.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'checks_passed': len(checks), 'receipt_sha256': sha(output)}))


if __name__ == '__main__':
    main()
