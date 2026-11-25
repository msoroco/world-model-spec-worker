"""Synthetic source-shape 80 mph boundary and negative provenance checks."""
import copy
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from measure_absolute_speed import AID, CAMERAS, COUNT, MPS_PER_MPH, measure


def save(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in rows))


def reject(root, changed, mutation):
    path = root/changed
    original = path.read_bytes()
    try:
        if changed.endswith('.jsonl'):
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            if mutation == 'frame':
                rows[200]['native_frame'] = rows[199]['native_frame']
            elif mutation == 'provenance':
                rows[200]['source_kind'] = 'original_native_velocity'
            elif mutation == 'actor':
                rows[200]['ego_actor_id'] = 999
            elif mutation == 'velocity':
                rows[200]['velocity_x_mps'] = float('nan')
            elif mutation == 'driving_state':
                del rows[200]['driving_state']
            save(path, rows)
        else:
            context = json.loads(path.read_text())
            if mutation == 'camera_hash':
                context['camera_sha256'] = {}
            elif mutation == 'route_source':
                del context['route_source']
            path.write_text(json.dumps(context))
        try:
            measure(root)
        except ValueError as exc:
            return {'mutation': mutation, 'rejected': str(exc)}
        raise AssertionError('Mutation accepted: '+mutation)
    finally:
        path.write_bytes(original)


def main():
    with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as tmp:
        root = Path(tmp)
        for name in CAMERAS:
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=64x48:r=20',
                            '-frames:v', str(COUNT), '-c:v', 'ffv1', str(root/(name+'.mkv'))], check=True)
        hashes = {(name+'.mkv'): hashlib.sha256((root/(name+'.mkv')).read_bytes()).hexdigest()
                  for name in CAMERAS}
        frames = [{'video_frame': i, 'native_frame': 1000+i, 'time_s': round(i*.05, 4)} for i in range(COUNT)]
        save(root/'video_frames.jsonl', frames)
        context = {'assignment_id': AID, 'review_kind': 'synthetic_diagnostic',
                   'camera_sha256': hashes, 'reviewer': 'synthetic-software-test',
                   'vehicle_identity_source': 'synthetic fixture', 'route_source': 'synthetic fixture',
                   'driving_state_source': 'synthetic fixture', 'ego_actor_id': 7}
        (root/'road_context.json').write_text(json.dumps(context))
        variants = []
        for label, speed in (('below_75', 75.0), ('near_79_5', 79.5),
                             ('at_80', 80.0), ('above_85', 85.0)):
            motion = [{'video_frame': i, 'native_frame': 1000+i, 'source_kind': 'synthetic_native_sample',
                       'ego_actor_id': 7, 'driving_state': True,
                       'velocity_x_mps': speed*MPS_PER_MPH, 'velocity_y_mps': 0.0,
                       'velocity_z_mps': 0.0} for i in range(COUNT)]
            save(root/'native_motion.jsonl', motion)
            observed = measure(root)
            count = len(observed['frames_above_80_mph'])
            assert count == (600 if label == 'above_85' else 0), (label, count)
            variants.append({'name': label, 'maximum_observed_mph': observed['maximum_observed_mph_while_driving'],
                             'above_cap_frame_count': count})
        negatives = [reject(root, 'native_motion.jsonl', 'frame'),
                     reject(root, 'native_motion.jsonl', 'provenance'),
                     reject(root, 'native_motion.jsonl', 'actor'),
                     reject(root, 'native_motion.jsonl', 'velocity'),
                     reject(root, 'native_motion.jsonl', 'driving_state'),
                     reject(root, 'road_context.json', 'camera_hash'),
                     reject(root, 'road_context.json', 'route_source')]
        print(json.dumps({'assignment_id': AID, 'software_proof': 'synthetic_diagnostic',
                          'variants': variants, 'negative_rejections': negatives,
                          'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
