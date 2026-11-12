"""Exercise full-duration far-case frame joins and synthetic camera media.

This is a software diagnostic. Color patterns do not establish participant
visibility, Native motion, physical acceptance, or delivery readiness.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
REPO = FOLDER.parents[1]
sys.path.insert(0, str(FOLDER))
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from prove_far_approach_history import make_sources, source_rows, write_jsonl
from worker_exchange.capture import PROFILE
from worker_exchange.media import audit, compose_four_views, check_four_view_sources

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_join(root, count):
    mapping = [json.loads(line) for line in (root / 'video_frames.jsonl').read_text().splitlines()]
    history = [json.loads(line) for line in (root / 'interaction_history.jsonl').read_text().splitlines()]
    trace = [json.loads(line) for line in (root / 'trace.jsonl').read_text().splitlines()]
    evidence = [json.loads(line) for line in (root / 'capture/evidence.jsonl').read_text().splitlines()]
    if any(len(rows) != count for rows in (mapping, history, trace, evidence)):
        raise ValueError('Full-duration original source count differs')
    for index, (frame, motion, source, capture) in enumerate(zip(mapping, history, trace, evidence)):
        if (frame['video_frame'] != index or frame['carla_frame'] != motion['frame'] or
                frame['carla_frame'] != source['frame'] or frame['carla_frame'] != capture['original_frame'] or
                abs(frame['time_s'] - motion['time_s']) > 1e-6 or
                abs(frame['time_s'] - source['time_s']) > 1e-6 or
                abs(frame['time_s'] - capture['recording_time_s']) > 1e-6):
            raise ValueError('Original frame/time join differs')
    return {name: sha(root / name) for name in
            ('video_frames.jsonl', 'interaction_history.jsonl', 'trace.jsonl', 'capture/evidence.jsonl')}


def verify_seal(root, sealed):
    for name, expected in sealed.items():
        path = root / name
        if not path.is_file():
            raise ValueError('Missing sealed original source: ' + name)
        if sha(path) != expected:
            raise ValueError('Sealed original source changed: ' + name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    if root.exists():
        raise ValueError('Use a fresh diagnostic output')
    rows = source_rows()
    count = len(rows)
    make_sources(root, rows)
    write_jsonl(root / 'trace.jsonl',
                [{'frame': row['frame'], 'time_s': row['time_s'],
                  'position_m': [*row['ego']['position_xy_m'], 0],
                  'heading_deg': row['ego_heading_deg'],
                  'speed_mps': sum(v*v for v in row['ego']['velocity_xy_mps'])**0.5}
                 for row in rows])
    (root / 'capture').mkdir()
    write_jsonl(root / 'capture/evidence.jsonl',
                [{'original_frame': row['frame'], 'recording_time_s': row['time_s'],
                  'fixture_only': True} for row in rows])
    joins = validate_join(root, count)
    dimensions = [PROFILE['overview'], *PROFILE['detail_views']]
    colors = ('black', 'navy', 'maroon', 'darkgreen')
    sources = {}
    for name, size, color in zip(CAMERAS, dimensions, colors):
        video = root / (name + '.mkv')
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                        '-f', 'lavfi', '-i', f'color=c={color}:s={size[0]}x{size[1]}:r=20',
                        '-vf', 'drawbox=x=20:y=20:w=64:h=64:color=red:t=fill',
                        '-frames:v', str(count), '-c:v', 'ffv1', '-pix_fmt', 'yuv444p',
                        str(video)], check=True, timeout=3600)
        sources[name] = video
    check_four_view_sources(sources)
    composition = compose_four_views(sources, root / 'video_frames.jsonl', root / 'raw.mkv')
    sealed = {name: sha(path) for name, path in sources.items()}
    sealed.update(joins)
    sealed['raw.mkv'] = sha(root / 'raw.mkv')
    verify_seal(root, {name + '.mkv': sealed[name] for name in CAMERAS})
    receipts = {}
    for name, video in (*sources.items(), ('raw', root / 'raw.mkv')):
        receipt = audit(video, count, mapping_sha256=joins['video_frames.jsonl'],
                        receipt=root / (name + '-decode.json'))
        expected = dimensions[CAMERAS.index(name)] if name in CAMERAS else composition['dimensions']
        if receipt['dimensions'] != expected or receipt['frames'] != count:
            raise ValueError('Decoded source dimensions/count differ: ' + name)
        receipts[name] = receipt['video_sha256']
    negative = root / 'missing-camera-negative'
    negative.mkdir()
    try:
        verify_seal(negative, {'overview.mkv': sealed['overview']})
    except ValueError as exc:
        if 'Missing sealed original source: overview.mkv' not in str(exc):
            raise
    else:
        raise ValueError('Missing sealed camera was accepted')
    print(json.dumps({'format': 'far-full-duration-synthetic-media-proof',
                      'frames': count, 'rate_hz': 20, 'duration_s': 45,
                      'frame_join_sha256': joins, 'source_sha256': sealed,
                      'decoded_sha256': receipts,
                      'composed_dimensions': composition['dimensions'],
                      'missing_sealed_camera_rejected': True,
                      'synthetic_pixels': True,
                      'physical_acceptance_claimed': False,
                      'delivery_readiness_claimed': False}, indent=2))


if __name__ == '__main__':
    main()
