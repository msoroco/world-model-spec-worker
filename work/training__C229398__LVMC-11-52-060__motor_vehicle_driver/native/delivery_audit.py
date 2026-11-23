"""Independently audit C229398 saved sources; synthetic runs remain diagnostic."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent
VIDEOS = ('raw.mkv', 'overview.mkv', 'approach.mkv',
          'reference_corner.mkv', 'driver_reference.mkv')
PARTS = ('vehicle', 'load', 'trailer')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit(case_id, attempt, saved_path, reject_frame_join=False):
    manifest = read(PACKAGE / 'execution-manifest.json')
    case = next((item for item in manifest['cases'] if item['case_id'] == case_id), None)
    if case is None:
        raise ValueError('Unselected case')
    if digest(PACKAGE / case['construction']) != case['construction_sha256']:
        raise ValueError('Selected construction changed')
    selection = read(attempt / 'candidate-selection.json')
    if (selection['case_id'] != case_id or selection['candidate_id'] != 'primary'
            or selection['construction_sha256'] != case['construction_sha256']
            or selection['manifest_sha256'] != digest(PACKAGE / 'draft-primary-manifest.json')):
        raise ValueError('Candidate selection differs')
    saved = read(saved_path)
    if (saved.get('case_id') != case_id or saved.get('candidate_id') != 'primary'
            or saved.get('passed') is not True or saved.get('recorded_only') is not True
            or saved.get('originals_preserved') is not True
            or saved.get('missing_evidence') is not False
            or saved.get('timestamp_joins') != {'frames': 600, 'passed': True,
                                                 'missing_original_trace_or_map': False}
            or saved.get('physical_acceptance_claimed') is not False
            or saved.get('legal_acceptance_claimed') is not False):
        raise ValueError('Saved processing receipt incomplete')
    if digest(saved_path) != case['saved_processing']['sha256']:
        raise ValueError('Selected saved receipt changed')
    hashes = saved['original_source_hashes']
    for name, expected in hashes.items():
        path = attempt / name
        if not path.is_file() or digest(path) != expected:
            raise ValueError('Saved original source changed: ' + name)
    if not set(VIDEOS).issubset(hashes):
        raise ValueError('Camera or raw source missing')
    trace = rows(attempt / 'trace.jsonl')
    actors = rows(attempt / 'native-raw-actors.jsonl')
    frames = rows(attempt / 'video_frames.jsonl')
    if reject_frame_join:
        frames[-1] = dict(frames[-1], native_frame=frames[-1]['native_frame'] + 1)
    if not (len(trace) == len(actors) == len(frames) == 600):
        raise ValueError('Original actor/frame/trace count differs')
    for index, (pose, actor, frame) in enumerate(zip(trace, actors, frames)):
        if (pose['frame'] != actor['native_frame'] or
                pose['frame'] != frame['native_frame'] or
                actor['frame'] != frame['video_frame'] or
                abs(pose['time_s'] - frame['time_s']) > 1e-6 or
                abs(pose['time_s'] - actor['time_s']) > 1e-6):
            raise ValueError('Original actor/frame/trace join differs at ' + str(index))
        if set(actor['actors']) != set(PARTS):
            raise ValueError('Vehicle, load or trailer absent at ' + str(index))
        for part in PARTS:
            data = actor['actors'][part]
            if not (len(data['center_xy_m']) == 2 and
                    len(data['half_extent_xy_m']) == 2 and
                    all(value > 0 for value in data['half_extent_xy_m'])):
                raise ValueError('Participant footprint incomplete at ' + str(index))
    result_path = Path(saved['result'])
    if not result_path.is_file() or digest(result_path) != saved['result_sha256']:
        raise ValueError('Saved result changed')
    result = read(result_path)
    if (result['case_id'] != case_id or result.get('accepted') is not False or
            result.get('legal_verdict_claimed') is not False):
        raise ValueError('Saved result identity or acceptance differs')
    capture = read(attempt / 'capture/manifest.json')
    if capture['case_id'] != case_id or capture['frames'] != 600:
        raise ValueError('Capture identity differs')
    # Decode every frame from each retained stream. A metadata-only probe is insufficient.
    for video in VIDEOS:
        run = subprocess.run(('ffmpeg', '-v', 'error', '-i', str(attempt / video),
                              '-map', '0:v:0', '-f', 'null', '-'),
                             capture_output=True, text=True)
        if run.returncode or run.stderr.strip():
            raise ValueError('Full video decode failed: ' + video + ': ' + run.stderr[-300:])
    if capture.get('synthetic_diagnostic') is not True or not all(
            row.get('synthetic_diagnostic') is True for row in trace):
        raise ValueError('This audit requires an explicitly synthetic fixture')
    return {'format': 'c229398-independent-delivery-audit', 'case_id': case_id,
            'candidate_id': 'primary', 'diagnostic_only': True, 'accepted': False,
            'source_kind': 'synthetic_native_sample', 'frames_joined': 600,
            'participants_checked': list(PARTS), 'videos_fully_decoded': list(VIDEOS),
            'saved_receipt_sha256': digest(saved_path),
            'original_source_count': len(hashes),
            'original_native_verified': False, 'actual_pixels_verified': False,
            'physical_completion_verified': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--saved', type=Path, required=True)
    parser.add_argument('--reject-frame-join', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.attempt, args.saved, args.reject_frame_join)))
