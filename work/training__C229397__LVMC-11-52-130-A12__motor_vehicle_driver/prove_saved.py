"""Execute the saved-only join on source-shaped positive and negative samples."""
import json
import hashlib
from pathlib import Path
import tempfile

from finalize_crosswalk import CAMERAS, finalize
from prove_crosswalk import sample
from source_review import FIELDS


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
    source = path / 'synthetic-original-review-source.txt'
    source.write_text('synthetic source shape only; no actual marked crosswalk or exception evidence\n')
    review = {'format': 'c229397-crosswalk-source-review-v1',
              'assignment_id': inventory['assignment_id'],
              'findings': {field: {'finding': 'present' if field == 'marked_crosswalk_source_id' else 'unresolved',
                                   'source': source.name,
                                   'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
                           for field in FIELDS}}
    (path / 'crosswalk-source-review.json').write_text(json.dumps(review) + '\n')
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
        if (result['video_pixels_decoded'] or result['legal_result'] is not None or
                result['independent_source_review_findings']['directions_review_source_id'] != 'unresolved'):
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
        review_path = bad / 'crosswalk-source-review.json'
        review = json.loads(review_path.read_text())
        review['findings']['marked_crosswalk_source_id']['finding'] = 'absent'
        review_path.write_text(json.dumps(review) + '\n')
        reject(bad, 'marked crosswalk has not been established')
        bad = root / 'stale_review_hash'
        bad.mkdir()
        write_attempt(bad)
        (bad / 'synthetic-original-review-source.txt').write_text('altered\n')
        reject(bad, 'crosswalk source review hash differs: jurisdiction_source_id')
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
                                 'marked-crosswalk-source rejection', 'source hash rejection',
                                 'Native frame mismatch rejection',
                                 'missing source rejection'],
                      'pixels_decoded': False, 'legal_verdict': None}, sort_keys=True))


if __name__ == '__main__':
    main()
