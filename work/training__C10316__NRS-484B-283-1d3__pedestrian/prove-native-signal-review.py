"""CPU contract check for a later independent original-pixel signal review."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from no_countdown import sha, validate_original_signal_review


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def main():
    with tempfile.TemporaryDirectory(prefix='c10316-signal-review-', dir=ROOT / '.runtime-work') as temp:
        folder = Path(temp)
        video = folder / 'driver_reference.mkv'
        video.write_bytes(b'diagnostic contract bytes, not camera evidence')
        frames = []
        samples = []
        for index, (indication, illuminated) in enumerate((
            ('walk', True), ('dont_walk_flashing', False), ('dont_walk_steady', True)
        )):
            pixel_hash = hashlib.sha256(f'frame-{index}'.encode()).hexdigest()
            frames.append({'video_frame': index, 'native_frame': 500 + index,
                           'source_rgb_sha256': {'driver_reference': pixel_hash}})
            samples.append({'native_frame': 500 + index, 'indication': indication,
                            'display_illuminated': illuminated,
                            'native_signal_head': {'device_id': 'physical-crosswalk-head',
                                'opendrive_id': '203', 'source': 'native_actor_readback',
                                'native_state': 'Green' if indication == 'walk' else
                                    'Red' if illuminated else 'Off'},
                            'original_display_frame_sha256': pixel_hash})
        map_path = folder / 'video_frames.jsonl'
        map_path.write_text(''.join(json.dumps(row) + '\n' for row in frames))
        sample_path = folder / 'no-countdown-samples.jsonl'
        sample_path.write_text(''.join(json.dumps(row) + '\n' for row in samples))
        review = {'source_kind': 'independent_original_pixel_review',
                  'reviewer': 'independent_pixel_reviewer',
                  'device_id': 'physical-crosswalk-head', 'crosswalk_id': 'physical-crosswalk',
                  'governs_crosswalk': True, 'faces_pedestrian': True,
                  'countdown_absent': True,
                  'source_sha256': {'driver_reference.mkv': sha(video),
                                    'video_frames.jsonl': sha(map_path),
                                    'no-countdown-samples.jsonl': sha(sample_path)},
                  'frame_observations': [
                      {'native_frame': row['native_frame'],
                       'original_display_frame_sha256': row['original_display_frame_sha256'],
                       'indication': row['indication'],
                       'illuminated': row['display_illuminated'],
                       'countdown_visible': False} for row in samples]}
        review_path = folder / 'signal-observation-audit.json'
        write(review_path, review)
        context = {'device_id': review['device_id'], 'crosswalk_id': review['crosswalk_id'],
                   'display_pixel_audit_sha256': sha(review_path)}
        validate_original_signal_review(folder, context, samples)
        failures = {}
        variants = {
            'program_self_review': lambda value: value.update(reviewer='capture_program'),
            'wrong_video_hash': lambda value: value['source_sha256'].update({'driver_reference.mkv': '0' * 64}),
            'missing_middle_frame': lambda value: value['frame_observations'].pop(1),
            'counterfeit_phase': lambda value: value['frame_observations'][1].update(indication='walk'),
            'invented_countdown': lambda value: value.update(countdown_absent=False),
        }
        for name, mutate in variants.items():
            altered = copy.deepcopy(review)
            mutate(altered)
            write(review_path, altered)
            altered_context = {**context, 'display_pixel_audit_sha256': sha(review_path)}
            try:
                validate_original_signal_review(folder, altered_context, samples)
            except ValueError as error:
                failures[name] = str(error)
            else:
                raise AssertionError('Signal review negative passed: ' + name)
        write(review_path, review)
        stale_context = {**context, 'display_pixel_audit_sha256': '0' * 64}
        try:
            validate_original_signal_review(folder, stale_context, samples)
        except ValueError as error:
            failures['stale_receipt'] = str(error)
        else:
            raise AssertionError('Stale signal review receipt passed')
    proof = {'format': 'c10316-signal-review-contract-proof-v1',
             'positive_count': 1, 'rejected_negatives': failures,
             'native_observation_claimed': False,
             'scope': 'synthetic contract-shaped inputs only; no original pixels reviewed'}
    path = HERE / 'native-signal-review-proof.json'
    write(path, proof)
    print(json.dumps({'positive_count': 1, 'rejected_negatives': len(failures),
                      'native_observation_claimed': False}))


if __name__ == '__main__':
    main()
