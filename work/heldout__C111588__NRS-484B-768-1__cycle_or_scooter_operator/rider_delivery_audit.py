"""Independent saved-source audit for the exact rider turn-signal cases.

This recomputes frame joins and signal timing from retained originals. A synthetic
fixture can pass source integrity without supplying a visible rider or legal fact.
"""
import argparse
from hashlib import sha256
import json
from math import atan2, cos, radians, sin
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('video_frames.jsonl', 'trace.jsonl', 'rider_motion.jsonl',
           'rider_arm_bones.jsonl', 'rider_signal_review.jsonl',
           'rider_context.json', *(name + '.mkv' for name in CAMERAS))


def _hash(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit_attempt(attempt, report, *, decoder=None, receipt_dir=None):
    root = Path(attempt)
    report = json.loads(Path(report).read_text()) if not isinstance(report, dict) else report
    measurement = report['measurements']['rider_turn_signal_observation']
    original_hashes = measurement['sources']
    if set(original_hashes) != set(SOURCES):
        raise ValueError('Rider analysis source inventory differs')
    for name in SOURCES:
        source = root / name
        if not source.is_file() or _hash(source) != original_hashes[name]:
            raise ValueError('Stale or missing original source: ' + name)
    config = json.loads((root / 'config.json').read_text())
    if report['case_id'] != config['selected_case_id']:
        raise ValueError('Rider analysis case identity differs')
    context = json.loads((root / 'rider_context.json').read_text())
    mapping, trace, motion, bones, reviews = (_rows(root / name) for name in
        ('video_frames.jsonl', 'trace.jsonl', 'rider_motion.jsonl',
         'rider_arm_bones.jsonl', 'rider_signal_review.jsonl'))
    count = len(mapping)
    if count < 3 or any(len(rows) != count for rows in (trace, motion, bones, reviews)):
        raise ValueError('Rider source frame count differs')
    first_yaw = float(motion[0]['rider_yaw_deg'])
    observed_onset = None
    preturn_visible = []
    visible_by_frame = []
    for index, (frame, point, rider, bone, review) in enumerate(
            zip(mapping, trace, motion, bones, reviews)):
        identity = (frame.get('carla_frame'), frame.get('time_s'))
        if (frame.get('video_frame') != index or
                (point.get('frame'), point.get('time_s')) != identity or
                (rider.get('frame'), rider.get('time_s')) != identity or
                (bone.get('frame'), bone.get('time_s')) != identity or
                (review.get('frame'), review.get('time_s')) != identity or
                rider.get('rider_id') != context.get('rider_id') or
                bone.get('rider_id') != context.get('rider_id') or
                review.get('rider_id') != context.get('rider_id')):
            raise ValueError('Rider original frame identity differs')
        if review.get('source_video_sha256') != original_hashes['driver_reference.mkv']:
            raise ValueError('Stale rider pixel review')
        if review.get('visible_signal') is not None and type(review.get('visible_signal')) is not bool:
            raise ValueError('Invalid rider pixel review')
        delta = atan2(sin(radians(float(rider['rider_yaw_deg']) - first_yaw)),
                      cos(radians(float(rider['rider_yaw_deg']) - first_yaw))) * 180 / 3.141592653589793
        if observed_onset is None and abs(delta) > .5:
            observed_onset = index
        visible_by_frame.append(review['visible_signal'])
    if observed_onset is None or observed_onset == 0:
        raise ValueError('Rider turn onset is unmeasured')
    preturn_visible = [mapping[i]['carla_frame'] for i in range(observed_onset)
                       if visible_by_frame[i] is True]
    observed = measurement['value']
    if (observed.get('turn_onset_frame') != mapping[observed_onset]['carla_frame'] or
            observed.get('pre_turn_visible_signal_frames') != preturn_visible or
            observed.get('pre_turn_signal_observation_complete') !=
            all(value is not None for value in visible_by_frame[:observed_onset])):
        raise ValueError('Rider analysis differs from independently recomputed originals')
    if decoder is None:
        from worker_exchange.media import audit as decoder
    directory = Path(receipt_dir) if receipt_dir else None
    if directory is not None:
        directory.mkdir(parents=True, exist_ok=False)
    cameras = {}
    for name in CAMERAS:
        path = root / (name + '.mkv')
        receipt = directory / (name + '-decode.json') if directory else None
        decoded = decoder(path, count, mapping_sha256=original_hashes['video_frames.jsonl'],
                          receipt=receipt)
        if decoded.get('frames') != count:
            raise ValueError('Rider source camera frame count differs: ' + name)
        cameras[name] = {'source_sha256': original_hashes[name + '.mkv'], 'decode': decoded}
    provenance = root / 'acquisition-provenance.json'
    synthetic = provenance.is_file() and json.loads(provenance.read_text()).get('diagnostic_fixture') is True
    return {'format': 'worker-rider-source-audit', 'case_id': report['case_id'],
            'original_source_hashes': original_hashes, 'frame_count': count,
            'independent_turn_onset_frame': mapping[observed_onset]['carla_frame'],
            'independent_pre_turn_visible_signal_frames': preturn_visible,
            'camera_decodes': cameras, 'source_integrity_passed': True,
            'diagnostic_fixture': synthetic,
            'physical_visibility_verified': False, 'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--analysis', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior rider audit; choose a fresh output')
    audited = audit_attempt(args.attempt, args.analysis,
                            receipt_dir=output.parent / (output.stem + '-decodes'))
    output.write_text(json.dumps(audited, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'case_id': audited['case_id'], 'frame_count': audited['frame_count'],
                      'source_integrity_passed': True,
                      'physical_visibility_verified': False}, indent=2))


if __name__ == '__main__':
    main()
