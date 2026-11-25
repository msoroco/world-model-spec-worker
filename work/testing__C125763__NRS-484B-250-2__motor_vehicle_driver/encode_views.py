"""Encode audited original camera PNG sequences as lossless source videos."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from native_history_capture import CAMERAS, _retained_file, audit_media


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _probe(path):
    result = subprocess.run([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-count_frames', '-show_entries',
        'stream=width,height,avg_frame_rate,nb_read_frames,codec_name',
        '-of', 'json', str(path)], capture_output=True, text=True, check=True)
    streams = json.loads(result.stdout).get('streams', [])
    if len(streams) != 1:
        raise ValueError('one decoded camera stream required')
    return streams[0]


def encode(attempt, output, *, camera_dimensions):
    attempt, output = Path(attempt), Path(output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('fresh empty lossless video directory required')
    audit = audit_media(attempt, camera_dimensions=camera_dimensions)
    count = audit['joined_original_frames']
    output.mkdir(parents=True, exist_ok=True)
    videos = {}
    for name in CAMERAS:
        target = output / (name + '.mkv')
        source = attempt / 'original-frames' / (name + '-%06d.png')
        subprocess.run([
            'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
            '-framerate', '20', '-start_number', '0', '-i', str(source),
            '-frames:v', str(count), '-an', '-c:v', 'ffv1', '-level', '3',
            str(target)], capture_output=True, text=True, check=True)
        stream = _probe(target)
        if (stream.get('codec_name') != 'ffv1' or
                [stream.get('width'), stream.get('height')] != list(camera_dimensions[name]) or
                stream.get('avg_frame_rate') != '20/1' or
                int(stream.get('nb_read_frames', -1)) != count):
            raise ValueError('lossless camera decode/profile differs: ' + name)
        videos[name] = {'path': target.name,
                        'sha256': _sha(target),
                        'decoded_frames': count, 'dimensions': list(camera_dimensions[name])}
    return {'source_frame_count': count, 'fps': 20, 'encoding': 'ffv1',
            'videos': videos, 'physical_acceptance': False}


def compose_primary(attempt, videos_dir, output, encoded_receipt):
    """Compose only source-audited profile views with the pinned runtime layout."""
    attempt, videos_dir, output = map(Path, (attempt, videos_dir, output))
    site = json.loads(_retained_file(attempt, 'site-context.json').read_text(
        encoding='utf-8'))
    dimensions = site.get('camera_dimensions')
    expected = {'overview': [1920, 1080], 'approach': [1280, 720],
                'reference_corner': [1280, 720], 'driver_reference': [1280, 720]}
    if dimensions != expected:
        raise ValueError('composed primary requires original four-view profile')
    source = audit_media(attempt, camera_dimensions=dimensions)
    count = source['joined_original_frames']
    receipt = (json.loads(Path(encoded_receipt).read_text(encoding='utf-8'))
               if not isinstance(encoded_receipt, dict) else encoded_receipt)
    if (receipt.get('source_frame_count') != count or receipt.get('fps') != 20 or
            receipt.get('encoding') != 'ffv1' or
            not isinstance(receipt.get('videos'), dict) or
            set(receipt['videos']) != set(CAMERAS)):
        raise ValueError('source video receipt differs from original frame map')
    sources = {}
    for name in CAMERAS:
        row = receipt['videos'][name]
        path = videos_dir / (name + '.mkv')
        if (row.get('path') != path.name or path.is_symlink() or not path.is_file() or
                row.get('sha256') != _sha(path) or row.get('decoded_frames') != count or
                row.get('dimensions') != dimensions[name]):
            raise ValueError('encoded source video differs: ' + name)
        sources[name] = path
    runtime_path = Path(__file__).resolve().parents[2] / 'runtime/scenario_pipeline'
    import sys
    if str(runtime_path) not in sys.path:
        sys.path.insert(0, str(runtime_path))
    from worker_exchange.media import compose_four_views
    composed = compose_four_views(sources, attempt / 'video_frames.jsonl', output)
    if composed['frames'] != count or composed['primary_sha256'] != _sha(output):
        raise ValueError('composed primary lost original source binding')
    stream = _probe(output)
    if (stream.get('codec_name') != 'ffv1' or stream.get('avg_frame_rate') != '20/1' or
            int(stream.get('nb_read_frames', -1)) != count or
            [stream.get('width'), stream.get('height')] != composed['dimensions']):
        raise ValueError('composed primary decode/profile differs')
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-i', str(output),
                    '-map', '0:v:0', '-f', 'null', '-'],
                   capture_output=True, text=True, check=True)
    return {**composed, 'full_video_decode': True,
            'diagnostic_fixture': count != 900 or site.get('review_status') != 'reviewed_original',
            'physical_acceptance': False, 'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser(description='Encode and compose audited C125763 views')
    parser.add_argument('--mode', choices=('encode', 'compose'), default='encode')
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--receipt-output', required=True)
    parser.add_argument('--videos-dir')
    parser.add_argument('--encoded-receipt')
    args = parser.parse_args()
    receipt_output = Path(args.receipt_output)
    if receipt_output.exists():
        raise FileExistsError(receipt_output)
    if args.mode == 'encode':
        site = json.loads(_retained_file(Path(args.attempt), 'site-context.json').read_text())
        receipt = encode(args.attempt, args.output,
                         camera_dimensions=site['camera_dimensions'])
    else:
        if not args.videos_dir or not args.encoded_receipt:
            parser.error('compose needs --videos-dir and --encoded-receipt')
        receipt = compose_primary(args.attempt, args.videos_dir, args.output,
                                  args.encoded_receipt)
    receipt_output.parent.mkdir(parents=True, exist_ok=True)
    receipt_output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n',
                              encoding='utf-8')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
