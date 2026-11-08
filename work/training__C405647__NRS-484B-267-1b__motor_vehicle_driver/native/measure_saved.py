"""Saved right-edge geometry diagnostics, without legal or authority verdicts."""
import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
AID = 'training__C405647__NRS-484B-267-1b__motor_vehicle_driver'
FRAME = 'authored_opendrive_xy'
EXPECTED_ASSIGNMENT_SHA256 = '5fdf7db6dbb934d4ebe21ebea78baeaaf7cb93d6df595dbfbf0b86d1e7822ffa'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def assignment_hash():
    source = HERE / 'assignment-source.json'
    if not source.is_file():
        source = ROOT / 'inputs' / AID / 'assignment.json'
    if not source.is_file() or sha(source) != EXPECTED_ASSIGNMENT_SHA256:
        raise ValueError('frozen assignment source differs')
    return EXPECTED_ASSIGNMENT_SHA256


def _point(value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError('saved XY point absent')
    result = tuple(float(x) for x in value)
    if not all(math.isfinite(x) for x in result):
        raise ValueError('saved XY point nonfinite')
    return result


def _verify_original_cameras(folder, scope):
    ffprobe = shutil.which('ffprobe')
    ffmpeg = shutil.which('ffmpeg')
    if not ffprobe or not ffmpeg:
        raise ValueError('original camera decoder absent')
    expected = {'overview': (1920, 1080), 'front_lamp': (1280, 720),
                'right_edge': (1280, 720), 'rear_approach': (1280, 720)}
    if set(scope.get('camera_sha256', {})) != set(expected):
        raise ValueError('original camera source hashes absent')
    for name, dimensions in expected.items():
        video = folder / (name + '.mkv')
        if not video.is_file() or scope['camera_sha256'][name] != sha(video):
            raise ValueError('original camera source differs')
        probe = subprocess.run([ffprobe, '-v', 'error', '-count_frames',
                                '-select_streams', 'v:0', '-show_entries',
                                'stream=width,height,nb_read_frames,codec_name',
                                '-of', 'json', str(video)], text=True,
                               capture_output=True, timeout=180, check=False)
        if probe.returncode:
            raise ValueError('original camera probe failed')
        streams = json.loads(probe.stdout).get('streams', [])
        if len(streams) != 1 or (streams[0].get('width'), streams[0].get('height')) != dimensions or streams[0].get('codec_name') != 'ffv1' or streams[0].get('nb_read_frames') != '480':
            raise ValueError('original camera codec/dimensions/frames differ')
        decoded = subprocess.run([ffmpeg, '-nostdin', '-v', 'error', '-i', str(video),
                                  '-map', '0:v:0', '-f', 'null', '-'],
                                 capture_output=True, timeout=180, check=False)
        if decoded.returncode:
            raise ValueError('original camera decode failed')


def measure(folder):
    folder = Path(folder)
    scope_path = folder / 'source-scope.json'
    actor_path = folder / 'actor-frames.jsonl'
    if not scope_path.is_file() or not actor_path.is_file():
        raise ValueError('saved source files absent')
    scope = json.loads(scope_path.read_text())
    if scope.get('assignment_sha256') != assignment_hash():
        raise ValueError('frozen assignment source differs')
    if scope.get('case_suffix') not in ('reference', 'contrast') or scope.get('coordinate_frame') != FRAME:
        raise ValueError('saved case or coordinate frame differs')
    kind = scope.get('source_kind')
    if kind not in ('synthetic_cpu', 'original_native'):
        raise ValueError('saved provenance differs')
    if kind == 'original_native':
        if not scope.get('original_camera_decode_verified'):
            raise ValueError('original cameras need decoded frame proof')
        _verify_original_cameras(folder, scope)
    packet = rows(actor_path)
    if len(packet) != 480:
        raise ValueError('saved frame count differs')
    centers, outer_edges, gaps, speeds, headings = [], [], [], [], []
    previous_native_frame = None
    for index, row in enumerate(packet):
        if (row.get('frame') != index or row.get('video_frame') != index or
            abs(float(row.get('time_s', -1)) - index / 20) > 1e-4 or
            row.get('coordinate_frame') != FRAME or row.get('source_kind') != kind):
            raise ValueError('saved frame/time/provenance join differs')
        native_frame = row.get('native_frame')
        if not isinstance(native_frame, int) or (previous_native_frame is not None and native_frame != previous_native_frame + 1):
            raise ValueError('Native frame identity differs')
        previous_native_frame = native_frame
        subject, approach = row.get('subject'), row.get('approach')
        if not isinstance(subject, dict) or not isinstance(approach, dict):
            raise ValueError('saved participant absent')
        center = _point(subject.get('center_xy_m'))
        other = _point(approach.get('center_xy_m'))
        body = subject.get('body_xy_m')
        if not isinstance(body, list) or len(body) != 4:
            raise ValueError('saved subject footprint absent')
        vertices = [_point(v) for v in body]
        if len(set(vertices)) != 4 or abs(sum(x for x, _ in vertices) / 4 - center[0]) > .1 or abs(sum(y for _, y in vertices) / 4 - center[1]) > .1:
            raise ValueError('saved subject footprint/center differs')
        speed, heading = float(subject.get('speed_mps', float('nan'))), float(subject.get('heading_deg', float('nan')))
        if not math.isfinite(speed) or speed < 0 or not math.isfinite(heading):
            raise ValueError('saved speed or heading invalid')
        centers.append(center)
        outer_edges.append(min(y for _, y in vertices))
        gaps.append(center[0] - other[0])
        speeds.append(speed)
        headings.append(heading)
    move = next((i for i, center in enumerate(centers) if center[1] < centers[0][1] - .1), None)
    edge = next((i for i, center in enumerate(centers)
                 if center[1] <= -5.95 and outer_edges[i] >= -7.0), None)
    catchup = next((i for i, gap in enumerate(gaps) if gap <= 4.5), None)
    stop = next((i for i in range(len(speeds) - 9) if max(speeds[i:i + 10]) <= .1), None)
    if catchup is None:
        raise ValueError('saved approach never catches subject')
    return {'format': 'c405647-1b-saved-geometry-v1', 'case_suffix': scope['case_suffix'],
            'scope_sha256': sha(scope_path), 'actor_frames_sha256': sha(actor_path),
            'source_kind': kind, 'frames': len(packet),
            'first_lateral_motion_frame': move, 'first_edge_target_frame': edge,
            'first_ten_frame_stop': stop, 'approach_catchup_frame': catchup,
            'edge_before_catchup': edge is not None and edge < catchup,
            'stop_center_xy_m': list(centers[stop]) if stop is not None else None,
            'stop_outer_body_y_m': outer_edges[stop] if stop is not None else None,
            'stop_heading_deg': headings[stop] if stop is not None else None,
            'authored_road_has_no_intersection': True,
            'vehicle_authority_or_lamps_qualified': False,
            'legal_immediacy_or_edge_verdict': None}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('folder')
    args = parser.parse_args()
    print(json.dumps(measure(args.folder), indent=2))
