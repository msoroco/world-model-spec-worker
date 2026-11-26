"""Independently verify original two-vehicle source, frame and camera joins."""
import hashlib
import json
from pathlib import Path
import subprocess

from contest_aid import CASES, SOURCE_FIELDS
from package_spec import AID, CAMERA_NAMES


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def decode(path):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                            '-count_frames', '-show_entries', 'stream=nb_read_frames',
                            '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
                           check=True, text=True, capture_output=True)
    need(probe.stdout.strip() == '900', 'original camera frame count differs')
    subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(path),
                    '-f', 'null', '-'], check=True, capture_output=True)


def audit(attempt, case_id):
    attempt = Path(attempt).resolve()
    receipt_path = attempt / 'original-source-receipt.json'
    receipt = json.loads(receipt_path.read_text())
    need(receipt.get('source_kind') == 'original_native_capture' and
         receipt.get('diagnostic_fixture') is False and
         receipt.get('case_id') == case_id and receipt.get('fps') == 20 and
         receipt.get('frame_count') == 900,
         'original Native contest receipt differs')
    for name, key in [('contest-packet.json', 'packet_sha256'),
                      ('contest-measurement.json', 'measurement_sha256'),
                      ('trace.jsonl', 'trace_sha256'),
                      ('video_frames.jsonl', 'frame_map_sha256')]:
        target = attempt / name
        need(target.is_file() and sha(target) == receipt.get(key),
             'original contest source hash differs: ' + name)
    packet = json.loads((attempt / 'contest-packet.json').read_text())
    case = next((item for item in CASES if case_id == AID + '__' + item.name), None)
    need(case is not None and packet.get('case_id') == case_id and
         packet.get('assignment_id') == AID, 'exact original contest case differs')
    scene = packet['scene']
    trace = rows(attempt / 'trace.jsonl')
    mapping = rows(attempt / 'video_frames.jsonl')
    body = packet['frames']
    need(len(body) == len(trace) == len(mapping) == 900,
         '900 original two-vehicle frames required')
    previous = None
    cue_frames = []
    for index, (row, motion, mapped) in enumerate(zip(body, trace, mapping)):
        frame, time_s = row.get('native_frame'), row.get('native_time_s')
        need(row.get('original_frame') == mapped.get('video_frame') == index and
             mapped.get('carla_frame') == mapped.get('native_frame') ==
             motion.get('frame') == frame and
             mapped.get('time_s') == motion.get('time_s') == time_s and
             row.get('highway') is case.highway and
             row.get('candidate_contest') is case.candidate_contest,
             'original two-vehicle frame/context join differs')
        for name in SOURCE_FIELDS:
            need(row.get(name + '_source_sha256') ==
                 scene.get(name + '_source_sha256'),
                 'original contest source changed: ' + name)
        for name in ('ego_person_id', 'other_person_id', 'ego_vehicle_id', 'other_vehicle_id'):
            need(row.get(name) == scene.get(name),
                 'original participant identity changed: ' + name)
        if row.get('cue_observed') is True:
            cue_frames.append(index)
        if previous is not None:
            need(frame == previous[0] + 1 and abs(time_s - previous[1] - .05) <= .002,
                 'original Native cadence differs')
        previous = frame, time_s
    need(cue_frames == ([scene['cue_frame']] if case.cue else []),
         'physical cue frame differs')
    cameras = receipt.get('cameras')
    need(isinstance(cameras, dict) and set(cameras) == set(CAMERA_NAMES),
         'four original contest cameras required')
    bindings = {}
    for name, ref in cameras.items():
        video = (attempt / ref['path']).resolve()
        need(video.parent == attempt and video.is_file() and
             sha(video) == ref.get('sha256') and ref.get('frame_count') == 900,
             'original camera source hash differs: ' + name)
        decode(video)
        bindings[name + '.mkv'] = sha(video)
    return {'format': 'contest-original-source-audit', 'case_id': case_id,
            'receipt_sha256': sha(receipt_path), 'frame_count': 900,
            'full_decode': True, 'source_bindings': bindings,
            'actual_pixels_reviewed': False, 'source_verified': True,
            'legal_verdict': None}
