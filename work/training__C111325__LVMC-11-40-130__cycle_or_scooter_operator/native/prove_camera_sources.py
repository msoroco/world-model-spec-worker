"""Build four-camera CPU diagnostics for the paired bicycle speed requests."""
import hashlib
import json
import subprocess
from pathlib import Path

from bicycle_setup import plan
from speed import measure


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decoded_frames(path):
    process = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
        '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
        capture_output=True, text=True, check=True)
    return int(process.stdout.strip())


def main():
    assignment = Path(__file__).resolve().parents[1]
    root = assignment.parents[1]
    output = root/'.runtime-work/c111325/camera-proof'
    output.mkdir(parents=True, exist_ok=True)
    context = assignment/'diagnostic-speed/context.json'
    proofs = []
    for condition in ('condition_a', 'condition_b'):
        source = assignment/'diagnostic-speed'/(condition+'.jsonl')
        observed = measure(source, context)
        request = plan(condition)
        rows = [json.loads(line) for line in source.read_text().splitlines()]
        if len(rows) != request['frames']:
            raise ValueError('Source and Native request durations differ')
        stage = output/condition
        stage.mkdir(exist_ok=True)
        mapping = stage/'video_frames.jsonl'
        mapping.write_text(''.join(json.dumps({
            'video_frame': i, 'source_frame': row['frame'],
            'time_s': row['time_s'],
            'bicycle_center_xy_m': row['bicycle_center_xy_m'],
            'source_kind': 'synthetic_cpu'})+'\n'
            for i, row in enumerate(rows)))
        joined = [json.loads(line) for line in mapping.read_text().splitlines()]
        if any(joined[i]['video_frame'] != i or
               joined[i]['source_frame'] != rows[i]['frame'] or
               joined[i]['bicycle_center_xy_m'] != rows[i]['bicycle_center_xy_m']
               for i in range(len(rows))):
            raise ValueError('Camera/source frame join differs')
        cameras = {}
        for camera in request['cameras']:
            name = camera['name']
            # Small black frames exercise codec and timing only; no pixels
            # establish the actual rider, traffic or road conditions.
            path = stage/(name+'.mkv')
            subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-f','lavfi',
                '-i','color=c=black:s=32x32:r=20:d=30','-frames:v','600',
                '-an','-c:v','ffv1',str(path)],check=True)
            count = decoded_frames(path)
            if count != len(rows):
                raise ValueError('Decoded camera frame count differs')
            cameras[name] = {'decoded_frames': count, 'sha256': sha(path)}
        if set(cameras) != set(request['source_streams']):
            raise ValueError('Native request camera names changed')
        proofs.append({'condition': condition, 'request': request,
                       'measurement': observed,
                       'source_sha256': sha(source),
                       'context_sha256': sha(context),
                       'frame_map_sha256': sha(mapping),
                       'cameras': cameras})
    if proofs[0]['measurement']['first_stopped_frame'] == \
            proofs[1]['measurement']['first_stopped_frame']:
        raise ValueError('Controlled speed contrast absent')
    receipt = {'format': 'c111325-four-camera-synthetic-cpu-v1',
               'passed': True, 'conditions': proofs,
               'original_native_observed': False,
               'physical_conditions_verified': False,
               'reasonable_and_prudent_verdict_claimed': False}
    target = assignment/'four-camera-cpu-proof.json'
    target.write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps({'passed': True, 'camera_streams': 8,
                      'first_stopped_frames': [p['measurement']['first_stopped_frame']
                                               for p in proofs],
                      'receipt_sha256': sha(target)}))


if __name__ == '__main__':
    main()
