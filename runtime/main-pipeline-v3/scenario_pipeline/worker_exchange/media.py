"""Streaming P6 source audits: one decode, many checks, exact-file receipts."""
import json
import hashlib
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from .common import digest, read, sha, write


def compose_four_views(sources, frame_map, output):
    """Compose four synchronized original sources into one lossless primary video."""
    from .capture import PROFILE, layout
    names = ('overview', 'approach', 'reference_corner', 'driver_reference')
    if set(sources) != set(names):
        raise ValueError('Four named original camera sources are required')
    videos = [Path(sources[name]).resolve() for name in names]
    mapping = [json.loads(line) for line in Path(frame_map).read_text().splitlines() if line.strip()]
    if not mapping or any(row.get('video_frame') != index for index, row in enumerate(mapping)):
        raise ValueError('Original frame map is incomplete')
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Retain the prior composed source; choose a fresh attempt')
    dimensions = [PROFILE['overview'], *PROFILE['detail_views']]
    for name, video, size in zip(names, videos, dimensions):
        if not video.is_file():
            raise ValueError('Missing original camera source: ' + name)
        probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames',
            '-select_streams', 'v:0', '-show_entries', 'stream=width,height,nb_read_frames,r_frame_rate',
            '-of', 'json', str(video)], text=True))['streams'][0]
        if [probe['width'], probe['height']] != size or int(probe['nb_read_frames']) != len(mapping) or probe['r_frame_rate'] != '20/1':
            raise ValueError('Camera source dimensions, rate or frame count differ: ' + name)
    geometry = layout(PROFILE['overview'], PROFILE['detail_views'])
    width = geometry['width']; detail_height = max(size[1] for size in dimensions[1:])
    filters = f'[0:v]format=yuv444p,pad={width}:1080:{(width-1920)//2}:0[overview];'
    for index, size in enumerate(dimensions[1:], 1):
        filters += f'[{index}:v]format=yuv444p,pad={size[0]}:{detail_height}:0:0[detail{index}];'
    filters += f'[detail1][detail2][detail3]hstack=inputs=3,pad={width}:{detail_height}:0:0[details];[overview][details]vstack=inputs=2[primary]'
    command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n']
    for video in videos:
        command += ['-threads', '4', '-i', str(video)]
    command += ['-filter_complex_threads', '1', '-filter_complex', filters, '-map', '[primary]',
                '-frames:v', str(len(mapping)), '-vsync', '0', '-an', '-c:v', 'ffv1',
                '-pix_fmt', 'yuv444p', str(output)]
    subprocess.run(command, check=True, timeout=3600)
    final = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames',
        '-select_streams', 'v:0', '-show_entries', 'stream=width,height,nb_read_frames',
        '-of', 'json', str(output)], text=True))['streams'][0]
    if [final['width'], final['height']] != [geometry['width'], geometry['height']] or int(final['nb_read_frames']) != len(mapping):
        raise ValueError('Composed primary changed frame count or dimensions')
    return {'format': 'synchronized-four-view-v1', 'sources': {name: sha(video) for name, video in zip(names, videos)},
            'frame_map_sha256': sha(frame_map), 'primary': str(output), 'primary_sha256': sha(output),
            'frames': len(mapping), 'dimensions': [geometry['width'], geometry['height']],
            'pixel_visibility_verified': False}


@dataclass(frozen=True)
class Frame:
    index: int
    width: int
    height: int
    pixels: bytes


def _token(stream):
    token = bytearray()
    while True:
        byte = stream.read(1)
        if not byte:
            if token:
                raise ValueError('Truncated P6 header')
            return None
        if byte == b'#' and not token:
            if not stream.readline().endswith(b'\n'):
                raise ValueError('Truncated P6 comment')
            continue
        if byte in b' \t\r\n':
            if token:
                return bytes(token)
            continue
        token.extend(byte)
        if len(token) > 32:
            raise ValueError('Invalid P6 header token')


def frames(stream):
    index = 0
    while True:
        magic = _token(stream)
        if magic is None:
            return
        if magic != b'P6':
            raise ValueError('Expected FFmpeg P6 frame')
        try:
            width, height, maximum = (int(_token(stream)) for _ in range(3))
        except (TypeError, ValueError) as exc:
            raise ValueError('Invalid P6 dimensions') from exc
        if not (0 < width <= 16384 and 0 < height <= 16384 and maximum == 255):
            raise ValueError('Unsupported P6 dimensions/range')
        remaining = width * height * 3
        chunks = bytearray()
        while remaining:
            chunk = stream.read(remaining)
            if not chunk:
                raise ValueError('Truncated P6 pixels')
            chunks.extend(chunk)
            remaining -= len(chunk)
        yield Frame(index, width, height, bytes(chunks))
        index += 1


def verify_receipt(video, receipt, expected_frames, *, mapping_sha256=None, required_checks=None):
    value = read(receipt) if isinstance(receipt, (str, Path)) else receipt
    if (value.get('format') != 'source-decode-v1' or not value.get('passed') or
            value.get('auditor_sha256') != sha(Path(__file__)) or
            value.get('video_sha256') != sha(video) or value.get('frames') != expected_frames or
            value.get('mapping_sha256') != mapping_sha256):
        raise ValueError('Stale/incompatible source audit receipt')
    for key, version in (required_checks or {}).items():
        if value.get('checks', {}).get(key) != version:
            raise ValueError('Receipt does not cover required checker: ' + key)
    if value.get('checks', {}).get('frame_count') != 'all-decoded-frames-v1':
        raise ValueError('Missing frame count audit')
    return value


def audit(video, expected_frames, *, checkers=None, mapping_sha256=None, threads=4, receipt=None):
    """checkers maps name -> (code SHA256, callback(Frame)). Raising fails the audit.

    The trusted caller supplies checker code versions. Only a successful complete
    decode is reusable. Mapping validation is a separate check: its hash binds
    this result to that exact mapping, not a claim that timestamps were checked.
    """
    if expected_frames <= 0 or threads < 0:
        raise ValueError('Expected positive frames and nonnegative threads (zero=auto)')
    checkers = checkers or {}
    if 'frame_count' in checkers or any(not isinstance(v, str) or len(v) != 64 for v, _ in checkers.values()):
        raise ValueError('Pixel checkers need names and exact code SHA256 versions')
    required = {'frame_count': 'all-decoded-frames-v1', **{k: v for k, (v, _) in checkers.items()}}
    before = sha(video)
    if receipt and Path(receipt).exists():
        # Never silently fall back from a stale receipt; diagnosis remains visible.
        return verify_receipt(video, receipt, expected_frames,
                              mapping_sha256=mapping_sha256, required_checks=required)
    command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-threads', str(threads),
               '-i', str(video), '-vsync', '0', '-f', 'image2pipe', '-c:v', 'ppm', '-pix_fmt', 'rgb24', 'pipe:1']
    started = time.monotonic()
    count, dimensions = 0, None
    rgb_hash = hashlib.sha256()
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors)
        try:
            for frame in frames(process.stdout):
                current = [frame.width, frame.height]
                if dimensions is not None and current != dimensions:
                    raise ValueError('Source dimensions changed')
                dimensions = current
                rgb_hash.update(frame.pixels)
                if frame.index >= expected_frames:
                    raise ValueError('Too many decoded frames')
                for _, callback in checkers.values():
                    callback(frame)
                count += 1
            code = process.wait()
            if code:
                errors.seek(0)
                raise ValueError('FFmpeg decode failed: ' + errors.read(4000).decode(errors='replace'))
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    if count != expected_frames or sha(video) != before:
        raise ValueError('Wrong frame count or source changed during audit')
    result = {'format': 'source-decode-v1', 'passed': True, 'video_sha256': before,
              'frames': count, 'dimensions': dimensions, 'rgb_sequence_sha256': rgb_hash.hexdigest(), 'mapping_sha256': mapping_sha256,
              'checks': required, 'auditor_sha256': sha(Path(__file__)), 'threads': threads,
              'seconds': time.monotonic() - started,
              'ffmpeg_version': subprocess.check_output(['ffmpeg', '-version'], text=True).splitlines()[0]}
    if receipt:
        write(receipt, result)
    return result


def benchmark(video, expected_frames, output, thread_counts=(0, 4, 8)):
    """Full source decodes only; does not claim composition/encoder speedups."""
    values = [audit(video, expected_frames, threads=n) for n in thread_counts]
    if len({(v['video_sha256'], v['frames'], tuple(v['dimensions'])) for v in values}) != 1:
        raise ValueError('Benchmark inputs differ')
    result = {'kind': 'full-source-decode', 'runs': values,
              'fastest_threads': min(values, key=lambda v: v['seconds'])['threads'],
              'production_settings_changed': False,
              'limitation': 'Benchmark filter and encoder separately before changing those settings'}
    write(output, result)
    return result


def benchmark_render(videos, expected_frames, destination, filter_threads=(1, 4), encoder_threads=(4, 8), overview_size=None):
    """CPU-only multiview lossless VP9 benchmark. Retains all measured outputs.

    Fixed decoder threads isolate filter/encoder settings. Does not change live
    defaults. Compare decoded RGB sequences across settings, not encoded bytes.
    """
    from .capture import layout
    if len(videos) != 4 or expected_frames <= 0 or any(n < 1 for n in (*filter_threads, *encoder_threads)):
        raise ValueError('Expected four videos, positive frames and bounded thread settings')
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Use a new benchmark directory; retain earlier results')
    dimensions = []
    for video in videos:
        info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,r_frame_rate', '-of', 'json', str(video)], text=True))['streams'][0]
        dimensions.append(info)
    if len({d['r_frame_rate'] for d in dimensions}) != 1:
        raise ValueError('Source frame rates differ')
    overview = list(overview_size) if overview_size else [dimensions[0]['width'], dimensions[0]['height']]
    geometry = layout(overview, [[d['width'], d['height']] for d in dimensions[1:]])
    source_hashes = [sha(v) for v in videos]
    # hstack/vstack are supported by the older production FFmpeg too.
    width = geometry['width']
    detail_height = max(d['height'] for d in dimensions[1:])
    first = f'scale={overview[0]}:{overview[1]},' if overview_size else ''
    filters = (f'[0:v]{first}format=yuv444p,pad={width}:{overview[1]}:{(width-overview[0])//2}:0[overview];')
    for i, d in enumerate(dimensions[1:], 1):
        filters += f'[{i}:v]format=yuv444p,pad={d["width"]}:{detail_height}:0:0[detail{i}];'
    filters += (f'[detail1][detail2][detail3]hstack=inputs=3,pad={width}:{detail_height}:0:0[details];'
                '[overview][details]vstack=inputs=2[rendered]')
    destination.mkdir(parents=True)
    measurements = []
    for nf in filter_threads:
        for ne in encoder_threads:
            video = destination / f'filter{nf}-encoder{ne}.webm'
            command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error']
            for source in videos:
                command += ['-threads', '4', '-i', str(source)]
            command += ['-filter_complex_threads', str(nf), '-filter_complex', filters,
                        '-map', '[rendered]', '-frames:v', str(expected_frames), '-vsync', '0',
                        '-an', '-c:v', 'libvpx-vp9', '-crf', '0', '-b:v', '0', '-deadline', 'realtime',
                        '-cpu-used', '8', '-threads', str(ne), '-lossless', '1', '-pix_fmt', 'yuv444p', str(video)]
            started = time.monotonic()
            with (destination / (video.stem + '.log')).open('w') as log:
                subprocess.run(command, stderr=log, check=True)
            seconds = time.monotonic() - started
            result = audit(video, expected_frames, threads=4, receipt=video.with_suffix('.audit.json'))
            if result['dimensions'] != [geometry['width'], geometry['height']]:
                raise ValueError('Rendered layout dimensions differ')
            measurements.append({'filter_threads': nf, 'encoder_threads': ne, 'render_seconds': seconds,
                                 'audit': result, 'video': video.name})
            write(destination / 'progress.json', measurements)
    if len({v['audit']['rgb_sequence_sha256'] for v in measurements}) != 1:
        raise ValueError('Decoded rendered pixels differ across thread settings')
    if source_hashes != [sha(v) for v in videos]:
        raise ValueError('Benchmark sources changed')
    result = {'kind': 'multiview-filter-and-encoder', 'runs': measurements, 'layout': geometry,
              'source_sha256': source_hashes, 'fixed_decoder_threads': 4,
              'fastest': {k: v for k, v in min(measurements, key=lambda v: v['render_seconds']).items() if k != 'audit'},
              'production_settings_changed': False, 'visibility_capability_established': False}
    write(destination / 'benchmark.json', result)
    return result
