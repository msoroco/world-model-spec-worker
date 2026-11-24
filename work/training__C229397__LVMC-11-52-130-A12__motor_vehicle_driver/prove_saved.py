"""Execute the saved-only join on source-shaped positive and negative samples."""
import json
from pathlib import Path
import tempfile

from finalize_crosswalk import CAMERAS, finalize
from prove_crosswalk import sample


def write_attempt(path, center_x=-5.0):
    packet, inventory = sample(center_x)
    inventory['source_kind'] = 'native_saved_sample'
    poses = []
    frames = []
    for row in packet['frames']:
        poses.append(row)
        frames.append({'video_frame': row['video_frame'], 'native_frame': row['native_frame'],
                       'carla_frame': row['native_frame'], 'time_s': row['time_s'],
                       'camera_native_frames': {name: row['native_frame'] for name in CAMERAS}})
    (path / 'vehicle-poses.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in poses))
    (path / 'video_frames.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in frames))
    (path / 'crosswalk-inventory.json').write_text(json.dumps(inventory) + '\n')
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
    with tempfile.TemporaryDirectory(prefix='c229397-a12-saved-') as directory:
        root = Path(directory)
        good = root / 'good'
        good.mkdir()
        write_attempt(good)
        result = finalize(good)
        if result['halt_body_distance_below_20ft_frames'] != list(range(200,500)) or not result['camera_frame_map_validated']:
            raise ValueError('saved near-crosswalk diagnostic differs')
        if result['video_pixels_decoded'] or result['legal_result'] is not None:
            raise ValueError('saved proof claimed pixels or law')
        bad = root / 'missing_camera'
        bad.mkdir()
        poses, frames, inventory = write_attempt(bad)
        frames[200]['camera_native_frames'].pop('subject_side')
        (bad / 'video_frames.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in frames))
        reject(bad, 'four original camera identities missing or mismatched')
        bad = root / 'missing_marking'
        bad.mkdir()
        poses, frames, inventory = write_attempt(bad)
        inventory['marked_crosswalk_source_id'] = None
        (bad / 'crosswalk-inventory.json').write_text(json.dumps(inventory) + '\n')
        reject(bad, 'marked_crosswalk_source_id missing')
        bad = root / 'changed_frame'
        bad.mkdir()
        poses, frames, inventory = write_attempt(bad)
        poses[300]['native_frame'] += 1
        (bad / 'vehicle-poses.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in poses))
        reject(bad, 'original pose/frame-map identity join failed')
        bad = root / 'missing_pose'
        bad.mkdir()
        write_attempt(bad)
        (bad / 'vehicle-poses.jsonl').unlink()
        reject(bad, 'required original saved source missing')
    print(json.dumps({'passed': True, 'source_shape': '600 Native pose and FrameMap rows with four camera IDs',
                      'positive_body_gap_m': result['body_to_crosswalk_m_by_frame'][250],
                      'checks': ['positive saved-only join', 'camera identity rejection',
                                 'marked-crosswalk-source rejection', 'Native frame mismatch rejection',
                                 'missing source rejection'],
                      'pixels_decoded': False, 'legal_verdict': None}, sort_keys=True))


if __name__ == '__main__':
    main()
