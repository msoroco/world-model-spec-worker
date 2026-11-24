"""Bridge an original PNG/trace recording into canonical saved processing.

The Native owner exports graph/evidence files directly from its live sensors.
This bridge keeps original PNG archives and encodes synchronized view streams.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from zipfile import ZipFile

from analysis import canonical_trace_rows
from saved_delivery import CAMERAS


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def bridge(root: Path, original: Path, *, release: dict,
           expected_frames: int = 900) -> dict:
    root, original = root.resolve(), original.resolve()
    _require(original.parent == root and original.is_dir(),
             'original attempt must be a direct canonical capture child')
    _require(release.get('world_restored') is True and
             release.get('actors_released') is True and
             release.get('sensors_released') is True and
             release.get('readback_passed') is True,
             'Native owner restoration readback required before bridge')
    trace = json.loads((original / 'trace.json').read_text())
    frame_rows = [json.loads(line) for line in
                  (original / 'frame-map.jsonl').read_text().splitlines()]
    ego = trace['ego']
    _require(len(ego) == len(frame_rows) == expected_frames,
             'canonical original frame count differs')
    for index, (body, row) in enumerate(zip(ego, frame_rows)):
        _require(body['frame'] == row['frame'] and
                 abs(body['time_s'] - row['time_s']) < 1e-6 and
                 (index == 0 or body['frame'] == ego[index - 1]['frame'] + 1),
                 'canonical original frame identity differs')
    for name in ('trace.json', 'map-packet.json', 'authority.json', 'road.xodr'):
        destination = root / name
        _require(not destination.exists(), 'canonical source destination exists: ' + name)
        shutil.copyfile(original / name, destination)
        _require(_sha(original / name) == _sha(destination),
                 'canonical source copy differs: ' + name)
    mapping = [{'video_frame': index, 'carla_frame': row['frame'],
                'native_frame': row['frame'], 'time_s': row['time_s']}
               for index, row in enumerate(frame_rows)]
    (root / 'video_frames.jsonl').write_text(''.join(
        json.dumps(row, sort_keys=True) + '\n' for row in mapping))
    (root / 'trace.jsonl').write_text(''.join(
        json.dumps(row, sort_keys=True) + '\n'
        for row in canonical_trace_rows(ego)))
    for camera in CAMERAS:
        archive = original / (camera + '.zip')
        _require(archive.is_file(), 'original camera archive missing: ' + camera)
        destination = root / (camera + '.mkv')
        _require(not destination.exists(), 'canonical video destination exists')
        with ZipFile(archive) as media:
            _require(len(media.namelist()) == expected_frames and
                     len(set(media.namelist())) == expected_frames,
                     'original camera frame inventory differs')
            command = ['ffmpeg', '-v', 'error', '-f', 'image2pipe',
                       '-framerate', '20', '-vcodec', 'png', '-i', 'pipe:0',
                       '-an', '-c:v', 'libx264', '-preset', 'ultrafast',
                       '-crf', '18', '-pix_fmt', 'yuv420p', str(destination)]
            encoder = subprocess.Popen(command, stdin=subprocess.PIPE,
                                       stdout=subprocess.DEVNULL,
                                       stderr=subprocess.PIPE)
            try:
                for row in frame_rows:
                    reference = row['cameras'][camera]
                    data = media.read(reference['member'])
                    _require(hashlib.sha256(data).hexdigest() == reference['sha256'],
                             'original camera PNG hash differs')
                    encoder.stdin.write(data)
                encoder.stdin.close()
                error = encoder.stderr.read()
                if encoder.wait() != 0:
                    raise ValueError('original video encoder failed: ' +
                                     error.decode(errors='replace')[-1000:])
            except BaseException:
                encoder.kill()
                encoder.wait()
                raise
        _require(destination.is_file() and destination.stat().st_size > 0,
                 'canonical video encoding missing')
    native = root / 'capture'
    _require((native / 'manifest.json').is_file() and
             (native / 'evidence.jsonl').is_file() and
             (native / 'native/frames.jsonl').is_file(),
             'owner must export original Native graph/evidence sources')
    graph_manifest = json.loads((native / 'manifest.json').read_text())
    _require(graph_manifest.get('frames') == expected_frames and
             graph_manifest.get('observation_contract_version', 0) >= 2,
             'Native graph export frame/profile differs')
    from worker_exchange.native_output import seal_capture
    (root / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'native', 'diagnostic_fixture': False},
        sort_keys=True) + '\n')
    seal = seal_capture(root, frames=expected_frames,
                        restoration={'restored': True,
                                     'owner_release_readback': release},
                        errors=[], encoder_exit_codes={name: 0 for name in CAMERAS},
                        context={'source_record': 'reviewed_original_site'})
    return {'frame_count': expected_frames, 'capture_seal': seal,
            'physical_acceptance_claimed': False}
