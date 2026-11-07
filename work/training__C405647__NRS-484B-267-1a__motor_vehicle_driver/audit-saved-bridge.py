"""Independent audit of retained synthetic Native-to-saved integration packets."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAMES = ('observed-actors.jsonl', 'video-frames.jsonl', 'front-lamp-review.json',
         'front_lamp.source')


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit():
    proof = json.loads((ROOT / 'saved-bridge-proof.json').read_text())
    assert proof['passed'] and len(proof['results']) == 2
    results = []
    for case in ('witness_1', 'witness_2'):
        folder = ROOT / 'synthetic-bridge' / case
        source, prepared = folder / 'source', folder / 'prepared'
        original = _rows(source / 'observed-actors.jsonl')
        frames = _rows(source / 'video-frames.jsonl')
        review = json.loads((source / 'front-lamp-review.json').read_text())
        saved = _rows(prepared / 'actor-frames.jsonl')
        scope = json.loads((prepared / 'source-scope.json').read_text())
        measured = json.loads((prepared / 'saved-motion-preview.json').read_text())
        assert len(original) == len(frames) == len(review['frames']) == len(saved) == 480
        assert review['source_kind'] == 'synthetic_cpu'
        assert review['source_video_sha256'] == _sha(source / 'front_lamp.source')
        assert scope['case_suffix'] == case
        assert scope['source_kind'] == 'synthetic_cpu'
        assert scope['coordinate_frame'] == 'authored_opendrive_xy'
        assert not scope['physical_success_claimed']
        assert scope['native_source_hashes'] == {name: _sha(prepared / name) for name in NAMES}
        for index, (native, video, annotation, row) in enumerate(
                zip(original, frames, review['frames'], saved)):
            assert native['frame'] == row['frame'] == video['video_frame'] == index
            assert native['native_frame'] == video['native_frame'] == annotation['native_frame']
            assert row['native_frame'] == native['native_frame']
            assert row['video_frame'] == annotation['video_frame'] == index
            assert row['front_red_flash_on'] == annotation['front_red_flash_on']
            assert native['front_red_flash_on'] is None
            assert row['source_kind'] == 'synthetic_cpu'
            assert row['coordinate_frame'] == 'authored_opendrive_xy'
            for participant in ('subject', 'approach'):
                x, y = native['actors'][participant]['native_center_xy_m']
                assert row[participant] == {'x_m': x, 'y_m': -y}
            assert row['subject_body_xy_m'] == [
                [x, -y] for x, y in native['actors']['subject']['native_body_xy_m']]
        gaps = [row['subject']['x_m'] - row['approach']['x_m'] for row in saved]
        catchup = next(index for index, gap in enumerate(gaps) if gap <= 4.5)
        clearance = next((index for index, row in enumerate(saved) if
                          max(vertex[1] for vertex in row['subject_body_xy_m']) < -3.5), None)
        assert measured['catchup_frame'] == catchup == 182
        assert measured['first_full_body_inner_lane_clearance_frame'] == clearance
        assert clearance == (81 if case == 'witness_1' else None)
        assert measured['vehicle_authority_verified'] is False
        assert measured['lamp_qualification_verified'] is False
        expected = next(row for row in proof['results'] if row['case_suffix'] == case)
        assert expected['retained_actor_frames_sha256'] == _sha(prepared / 'actor-frames.jsonl')
        assert expected['retained_scope_sha256'] == _sha(prepared / 'source-scope.json')
        results.append({'case_suffix': case, 'frames': len(saved),
                        'catchup_frame': catchup, 'clearance_frame': clearance})
    return {'passed': True, 'results': results,
            'scope': 'independent retained synthetic CPU source/frame/body audit; '
                     'no Native observation or legal result'}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
