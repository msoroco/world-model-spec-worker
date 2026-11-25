"""Execute the saved-only join on source-shaped positive and negative samples."""
import json
from pathlib import Path
import tempfile

from finalize_alley import CAMERAS, finalize
from prove_alley import sample


def write_attempt(path, width=6.0):
    packet, inventory = sample(width)
    inventory['source_kind'] = 'native_saved_sample'
    poses = []
    frames = []
    trace = []
    for row in packet['frames']:
        poses.append(row)
        frames.append({'video_frame': row['video_frame'], 'native_frame': row['native_frame'],
                       'carla_frame': row['native_frame'], 'time_s': row['time_s'],
                       'camera_native_frames': {name: row['native_frame'] for name in CAMERAS}})
        trace.append({'frame': row['native_frame'], 'time_s': row['time_s'],
                      'position_m': [*row['subject']['xy_m'], 8.0],
                      'speed_mps': row['subject']['speed_mps']})
    (path / 'vehicle-poses.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in poses))
    (path / 'video_frames.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in frames))
    (path / 'alley-inventory.json').write_text(json.dumps(inventory) + '\n')
    (path / 'trace.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in trace))
    return poses, frames, inventory


def reject(path, expected):
    try:
        finalize(path)
    except ValueError as exc:
        if str(exc) == expected:
            return
        raise
    raise RuntimeError('invalid saved source accepted: ' + expected)


def main():
    with tempfile.TemporaryDirectory(prefix='c178965-477b-saved-') as directory:
        root = Path(directory)
        measured = {}
        for name, width in (('wide', 7.5), ('at_10', 6.648), ('narrow', 6.0)):
            good = root / name
            good.mkdir()
            write_attempt(good, width)
            result = finalize(good)
            measured[name] = result['minimum_measured_halt_free_width_m']
            if not result['camera_frame_map_validated']:
                raise ValueError('saved camera frame join differs')
            if result['video_pixels_decoded'] or result['legal_result'] is not None:
                raise ValueError('saved proof claimed pixels or law')
        if not measured['wide'] > 3.048 or abs(measured['at_10'] - 3.048) > 1e-9 or not measured['narrow'] < 3.048:
            raise ValueError('saved statutory boundary diagnostic differs')
        bad = root / 'missing_camera'
        bad.mkdir()
        poses, frames, inventory = write_attempt(bad)
        frames[200]['camera_native_frames'].pop('driver_reference')
        (bad / 'video_frames.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in frames))
        reject(bad, 'four original camera identities missing or mismatched')
        bad = root / 'missing_ordinance'
        bad.mkdir()
        poses, frames, inventory = write_attempt(bad)
        inventory['local_ordinance_review_source_id'] = None
        (bad / 'alley-inventory.json').write_text(json.dumps(inventory) + '\n')
        reject(bad, 'local_ordinance_review_source_id missing')
        bad = root / 'changed_frame'
        bad.mkdir()
        poses, frames, inventory = write_attempt(bad)
        poses[300]['native_frame'] += 1
        (bad / 'vehicle-poses.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in poses))
        reject(bad, 'original pose/frame-map identity join failed')
        bad = root / 'changed_trace'
        bad.mkdir()
        write_attempt(bad)
        lines = [json.loads(line) for line in (bad / 'trace.jsonl').read_text().splitlines()]
        lines[300]['position_m'][1] += 1
        (bad / 'trace.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in lines))
        reject(bad, 'original trace/subject body pose differs')
        bad = root / 'missing_pose'
        bad.mkdir()
        write_attempt(bad)
        (bad / 'vehicle-poses.jsonl').unlink()
        reject(bad, 'Missing required source: vehicle-poses.jsonl')
    print(json.dumps({'passed': True, 'source_shape': '600 Native pose and FrameMap rows with four camera IDs',
                      'positive_minimum_width_m': measured,
                      'checks': ['positive saved-only join', 'camera identity rejection',
                                 'ordinance-source rejection', 'Native frame mismatch rejection',
                                 'trace/subject body mismatch rejection',
                                 'missing source rejection'],
                      'pixels_decoded': False, 'legal_verdict': None}, sort_keys=True))


if __name__ == '__main__':
    main()
