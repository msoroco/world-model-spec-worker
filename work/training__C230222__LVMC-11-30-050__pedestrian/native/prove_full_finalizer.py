"""Exercise complete saved finalization on a small synthetic video shape."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from finalize import finalize


def main():
    root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    source = root / 'lvmc-route-finalizer'
    if not (source / 'capture/manifest.json').is_file():
        raise ValueError('Run prove_finalizer.py first')
    dest = root / 'lvmc-route-full-finalizer-test'
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source, dest)
    if not (dest / 'route-samples.jsonl').is_file():
        fixture = root / 'lvmc-route-comparison/a/samples.jsonl'
        rows = [json.loads(line) for line in fixture.read_text().splitlines()]
        frames = [json.loads(line) for line in (dest / 'video_frames.jsonl').read_text().splitlines()]
        for row, frame in zip(rows, frames):
            row['original_frame_sha256'] = frame['source_rgb_sha256']['reference_corner']
        (dest / 'route-samples.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    bundle = json.loads((ROOT / 'draft-route/condition_a/construction.json').read_text())
    config = next(json.loads(item['content']) for item in bundle['files'] if item['path'] == 'config.json')
    for camera in config['cameras']:
        camera['width'], camera['height'] = 64, 36
    (dest / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    for name in ('route-geometry-analysis.json', 'analysis.json', 'result.json'):
        (dest / name).unlink(missing_ok=True)
    video = dest / 'overview.mkv'
    subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                    '-f', 'lavfi', '-i', 'color=c=gray:s=64x36:r=20', '-frames:v', '600',
                    '-an', '-c:v', 'ffv1', '-level', '1', '-y', str(video)], check=True)
    for name in ('approach', 'reference_corner', 'driver_reference'):
        (dest / (name + '.mkv')).write_bytes(video.read_bytes())
    positive = finalize(dest, dest / 'analysis.json')
    if positive['measurements']['crossing_route_geometry']['value']['frames'] != 600:
        raise AssertionError('Saved route report incomplete')
    result = json.loads((dest / 'result.json').read_text())
    if result['accepted'] or result['legal_verdict_claimed']:
        raise AssertionError('Synthetic fixture claimed acceptance')
    proof = {'format': 'worker-crossing-full-finalizer-cpu-proof-v1',
             'positive': True, 'frame_count': 600, 'camera_count': 4,
             'diagnostic_video_dimensions': [64, 36],
             'original_camera_dimensions_proven': False,
             'accepted': False, 'legal_verdict_claimed': False,
             'finalizer_sha256': hashlib.sha256((HERE / 'finalize.py').read_bytes()).hexdigest()}
    out = HERE / 'full-finalizer-proof.json'
    out.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'proof': str(out), 'sha256': hashlib.sha256(out.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
