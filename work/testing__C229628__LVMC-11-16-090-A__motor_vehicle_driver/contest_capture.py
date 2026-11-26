"""Acquire 900 original Native frames, two actors and four synchronized views."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from contest_aid import construct, measure_original
from native_source import CAMERAS


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True) + '\n', encoding='utf-8')


def capture(adapter, site, scene, case, destination):
    destination = Path(destination).resolve()
    need(destination.is_dir() and (destination / 'config.json').is_file() and
         (destination / 'construction.json').is_file() and
         '.runtime-work' in destination.parts,
         'materialized original attempt belongs under .runtime-work')
    need(not (destination / 'capture-seal.json').exists() and
         not (destination / 'trace.jsonl').exists(),
         'original attempt already acquired')
    need(getattr(adapter, 'native_attested', False) is True,
         'attested Native CARLA adapter required')
    stage = Path(tempfile.mkdtemp(prefix='contest-original-', dir=destination.parent))
    cleaned = False
    try:
        adapter.prepare()
        construct(adapter, scene, case)
        adapter.attach_cameras()
        folders = {name: stage / ('frames-' + name) for name in CAMERAS}
        for folder in folders.values():
            folder.mkdir()
        rows, mapping, trace = [], [], []
        previous = None
        for index in range(900):
            native_frame, time_s = adapter.tick(index)
            if previous is not None:
                need(native_frame == previous[0] + 1 and
                     abs(time_s - previous[1] - .05) <= .002,
                     'original Native 20 Hz cadence differs')
            previous = native_frame, time_s
            row = adapter.read(index, native_frame, time_s, scene, case)
            need(row['original_frame'] == index and
                 row['native_frame'] == native_frame,
                 'original Native frame identity differs')
            pixels = adapter.pixels(native_frame)
            need(set(pixels) == set(CAMERAS), 'four original camera streams required')
            hashes = {}
            for name in CAMERAS:
                raw = pixels[name]
                need(isinstance(raw, bytes) and raw.startswith(b'\x89PNG\r\n\x1a\n'),
                     'original camera pixels missing: ' + name)
                (folders[name] / f'{index:04d}.png').write_bytes(raw)
                hashes[name] = hashlib.sha256(raw).hexdigest()
            rows.append(row)
            mapping.append({'video_frame': index, 'carla_frame': native_frame,
                            'native_frame': native_frame, 'time_s': time_s,
                            'camera_png_sha256': hashes})
            trace.append({'frame': native_frame, 'time_s': time_s,
                          'position_m': [*row['ego_xy'], 0.0],
                          'position': {'x': row['ego_xy'][0],
                                       'y': row['ego_xy'][1], 'z': 0.0},
                          'heading_deg': adapter.ego.get_transform().rotation.yaw,
                          'speed_mps': row['ego_speed_mps'],
                          'speed_mph': row['ego_speed_mps'] / .44704})
        measurement = measure_original(rows, scene, case)
        write(stage / 'contest-packet.json', {
            'assignment_id': site['assignment_id'], 'case_id': site['case_id'],
            'source_kind': 'original_native_capture',
            'reviewed_site_sha256': site['site_sha256'],
            'scene': scene, 'frames': rows})
        write(stage / 'contest-measurement.json', measurement)
        (stage / 'video_frames.jsonl').write_text(
            ''.join(json.dumps(row, sort_keys=True) + '\n' for row in mapping))
        (stage / 'trace.jsonl').write_text(
            ''.join(json.dumps(row, sort_keys=True) + '\n' for row in trace))
        videos = {}
        for name, folder in folders.items():
            video = stage / (name + '.mkv')
            subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-framerate', '20',
                            '-i', str(folder / '%04d.png'), '-frames:v', '900',
                            '-c:v', 'ffv1', str(video)], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            videos[name] = {'path': video.name, 'sha256': sha(video),
                            'frame_count': 900}
            shutil.rmtree(folder)
        adapter.cleanup()
        cleaned = True
        write(stage / 'acquisition-provenance.json', {
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'case_id': site['case_id'], 'reviewed_site_sha256': site['site_sha256'],
            'world_restored': True, 'original_frame_count': 900})
        write(stage / 'original-source-receipt.json', {
            'source_kind': 'original_native_capture', 'diagnostic_fixture': False,
            'case_id': site['case_id'], 'fps': 20, 'frame_count': 900,
            'reviewed_site_sha256': site['site_sha256'],
            'packet_sha256': sha(stage / 'contest-packet.json'),
            'measurement_sha256': sha(stage / 'contest-measurement.json'),
            'trace_sha256': sha(stage / 'trace.jsonl'),
            'frame_map_sha256': sha(stage / 'video_frames.jsonl'),
            'cameras': videos, 'physical_acceptance': False,
            'legal_verdict': None})
        for source in stage.iterdir():
            target = destination / source.name
            need(not target.exists(), 'original attempt output already exists: ' + source.name)
            os.replace(source, target)
        from worker_exchange.native_output import seal_capture
        seal_capture(destination, frames=900, restoration={'restored': True,
            'method': 'CARLA settings readback and owned actor cleanup'},
            errors=[], encoder_exit_codes={name: 0 for name in CAMERAS},
            context={'reviewed_site_sha256': site['site_sha256'],
                     'case_id': site['case_id'], 'participant_count': 2})
        shutil.rmtree(stage)
        return destination
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    finally:
        if not cleaned:
            adapter.cleanup()
