"""Recompute C183370 physical observations from retained Native sources.

The surveyed repair polygon is a planned region. Its newly repaired status,
human warning act and paving-worker exception need independent original review.
"""
import argparse
import hashlib
import json
import subprocess
from math import hypot, isfinite
from pathlib import Path

from shapely.geometry import MultiPoint, Point, Polygon

from capture import CAMERAS


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def analyze_rows(frames, actors, readback):
    if len(frames) < 600 or len(frames) != len(actors):
        raise ValueError('Original capture needs at least 600 joined frames')
    polygon = Polygon(readback['plan']['repair_polygon_xy_m'])
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError('Surveyed pavement polygon invalid')
    person_id = readback['warning_person_actor_id']
    crossings = []
    source_frames = []
    times = []
    for index, (frame, actor) in enumerate(zip(frames, actors)):
        if frame['index'] != index or actor['video_frame'] != index or actor['frame'] != frame['frame']:
            raise ValueError('Original actor/video frame join differs')
        native_frame, time = frame['frame'], frame['time_s']
        if type(native_frame) is not int or type(time) not in (int, float) or not isfinite(time):
            raise ValueError('Original frame/time identity invalid')
        if source_frames and (native_frame <= source_frames[-1] or
                              abs(time-times[-1]-0.05) > 0.001):
            raise ValueError('Original 20 Hz frame/time continuity failed')
        source_frames.append(native_frame); times.append(time)
        if actor.get('source_kind') != 'original_carla_actor_and_map_readback':
            raise ValueError('Original Native actor provenance absent')
        if actor.get('warning_person_actor_id') != person_id or not actor.get('warning_person_type_id','').startswith('walker.pedestrian.'):
            raise ValueError('Original warning-person identity differs')
        position = actor['warning_person_xyz_m']
        if len(position) != 3 or not all(type(v) in (int,float) and isfinite(v) for v in position):
            raise ValueError('Original warning-person position invalid')
        if Point(position[:2]).distance(polygon) > 15:
            raise ValueError('Original warning person left pavement vicinity')
        vertices = actor['ego_body_vertices_xyz_m']
        if len(vertices) != 8 or any(len(v) != 3 or not all(type(c) in (int,float) and isfinite(c) for c in v) for v in vertices):
            raise ValueError('Original ego body vertices invalid')
        body = MultiPoint([(v[0],v[1]) for v in vertices]).convex_hull
        if body.area <= 0:
            raise ValueError('Original ego body footprint invalid')
        if body.intersects(polygon):
            crossings.append(index)
    elapsed = times[-1]-times[0]+0.05
    if elapsed < 30.0-0.001:
        raise ValueError('Original source duration is shorter than 30 seconds')
    return {'source_frames': len(frames), 'source_elapsed_s': elapsed,
            'source_first_frame': source_frames[0],
            'source_last_frame': source_frames[-1],
            'pavement_footprint_contact_frames': crossings,
            'pavement_footprint_contact_observed': bool(crossings),
            'warning_person_present_near_pavement_frames': len(frames),
            'warning_act_verified': False,
            'newly_repaired_pavement_verified': False,
            'paving_employee_exception_verified': False,
            'physical_completion_claimed': False,
            'legal_acceptance_claimed': False}


def verify_media(path, expected_frames, *, camera_specs=CAMERAS):
    receipts = []
    for name, width, height, *_ in camera_specs:
        source = Path(path)/(name+'.mkv')
        if not source.is_file():
            raise ValueError('Missing original source camera: '+name)
        probe = subprocess.run([
            'ffprobe','-v','error','-count_frames','-select_streams','v:0',
            '-show_entries','stream=codec_name,width,height,nb_read_frames',
            '-of','json',str(source)],capture_output=True,text=True,check=True)
        streams = json.loads(probe.stdout)['streams']
        if len(streams) != 1:
            raise ValueError('Source camera has wrong video stream count: '+name)
        stream = streams[0]
        if (stream.get('codec_name') != 'ffv1' or stream.get('width') != width or
                stream.get('height') != height or
                int(stream.get('nb_read_frames', -1)) != expected_frames):
            raise ValueError('Source camera codec/shape/frame count differs: '+name)
        decoded = subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(source),
                                  '-f','null','-'],capture_output=True,text=True)
        if decoded.returncode:
            raise ValueError('Source camera decode failed: '+name+' '+decoded.stderr)
        receipts.append({'name': name, 'path': source.name,
                         'source_sha256': sha(source), 'decoded_frames': expected_frames,
                         'codec': 'ffv1', 'width': width, 'height': height})
    return receipts


def analyze(attempt):
    attempt = Path(attempt)
    receipt = json.loads((attempt/'capture-receipt.json').read_text())
    if receipt.get('source_kind') != 'original_carla_capture':
        raise ValueError('Original CARLA capture receipt required')
    readback = json.loads((attempt/'live-readback.json').read_text())
    frames = read_jsonl(attempt/'video_frames.jsonl')
    actors = read_jsonl(attempt/'native-actors.jsonl')
    if receipt['source_frames'] != len(frames):
        raise ValueError('Capture receipt frame count differs')
    observations = analyze_rows(frames, actors, readback)
    case = receipt['case']
    if case not in ('reference', 'contrast') or case not in readback['plan']['cases']:
        raise ValueError('Captured case differs from surveyed draft')
    requested_contact = readback['plan']['cases'][case]['requested_pavement_crossing']
    observations['requested_footprint_contact_matched'] = (
        observations['pavement_footprint_contact_observed'] == requested_contact)
    media = verify_media(attempt, len(frames))
    source_hashes = {name: sha(attempt/name) for name in
                     ('capture-receipt.json','live-readback.json','video_frames.jsonl',
                      'native-actors.jsonl','road.xodr')}
    result = {'format': 'c183370-original-source-analysis-v1',
              'source_kind': 'original_carla_capture',
              'case': case, 'source_hashes': source_hashes,
              'camera_sources': media, 'observations': observations}
    output = attempt/'source-analysis.json'
    if output.exists():
        raise ValueError('Preserve prior source analysis; use a fresh attempt')
    output.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    args = parser.parse_args()
    analyze(args.attempt)


if __name__ == '__main__':
    main()
