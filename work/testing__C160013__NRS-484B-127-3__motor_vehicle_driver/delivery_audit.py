"""Independent CPU boundary for the exact caravan delivery pair."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CAMERAS = {'overview', 'approach', 'reference_corner', 'driver_reference'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def camera_decode(path, camera):
    probe = subprocess.run(
        ['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
         '-show_entries', 'stream=width,height,nb_read_frames', '-of', 'json', str(path)],
        capture_output=True, text=True, check=True)
    streams = json.loads(probe.stdout)['streams']
    if len(streams) != 1 or any(int(streams[0][key]) != value for key, value in
                                (('width', camera['width']), ('height', camera['height']),
                                 ('nb_read_frames', 900))):
        raise ValueError('Full camera inventory or frame count differs: ' + path.name)
    decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:v:0',
                              '-f', 'framemd5', '-'], capture_output=True, check=True)
    lines = [line for line in decoded.stdout.splitlines() if line and not line.startswith(b'#')]
    if len(lines) != 900:
        raise ValueError('Full decoded camera frame count differs: ' + path.name)
    return {'source_sha256': sha(path),
            'decoded_frames_sha256': hashlib.sha256(b'\n'.join(lines)).hexdigest(),
            'decoded_frames': len(lines)}


def audit(attempt, case_id):
    attempt = Path(attempt)
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next((item for item in manifest['cases'] if item['case_id'] == case_id), None)
    if entry is None:
        raise ValueError('Unselected exact caravan case')
    if sha(HERE / entry['construction']) != entry['construction_sha256']:
        raise ValueError('Exact construction changed')
    report = json.loads((attempt / 'analysis-report.json').read_text())
    result = json.loads((attempt / 'result.json').read_text())
    config = json.loads((attempt / 'config.json').read_text())
    if (report.get('case_id') != case_id or result.get('case_id') != case_id
            or config.get('selected_case_id') != case_id):
        raise ValueError('Exact saved case identity differs')
    if (result.get('provenance_kind') != 'synthetic_fixture'
            or result.get('diagnostic_fixture') is not True
            or result.get('physical_acceptance_claimed') is not False
            or report.get('legal_verdict_asserted') is not False):
        raise ValueError('Diagnostic provenance or acceptance boundary differs')
    source_names = ('road_context.json', 'caravan_history.jsonl', 'video_frames.jsonl')
    source_hashes = {name: sha(attempt / name) for name in source_names}
    if (report.get('source_hashes') != source_hashes
            or result.get('source_evidence_hashes') != source_hashes):
        raise ValueError('Changed original source hash')
    histories = rows(attempt / 'caravan_history.jsonl')
    frames = rows(attempt / 'video_frames.jsonl')
    if len(histories) != 900 or len(frames) != 900:
        raise ValueError('Full original 900-frame duration required')
    for index, (history, frame) in enumerate(zip(histories, frames)):
        if (history.get('frame') != 100 + index or frame.get('carla_frame') != 100 + index
                or frame.get('video_frame') != index
                or abs(history.get('time_s', -1) - (1 + .05 * index)) > 1e-4
                or abs(frame.get('time_s', -1) - history['time_s']) > 1e-4):
            raise ValueError('Original caravan/video frame join failed')
        members = history.get('caravan_members', [])
        entrant = history.get('entering_vehicle', {})
        ids = [member.get('actor_id') for member in members] + [entrant.get('actor_id')]
        if len(members) != 3 or len(set(ids)) != 4:
            raise ValueError('All original participants required')
    if any(result.get('physical_checks', {}).get(key, {}).get('status') != 'met'
           for key in ('setup', 'target', 'maneuver', 'attempt')):
        raise ValueError('Full-duration diagnostic physical checker incomplete')
    if report.get('physical_checks') != result.get('physical_checks'):
        raise ValueError('Saved physical report differs')
    cameras = {item['name']: item for item in config['cameras']}
    if set(cameras) != CAMERAS:
        raise ValueError('Four exact cameras required')
    decoded = {name: camera_decode(attempt / (name + '.mkv'), camera)
               for name, camera in cameras.items()}
    expected_occupancy = case_id.endswith('__entrant_can_occupy_gap')
    checks = result['physical_checks']['target']['details']['checks']
    if (len(checks) != 1 or checks[0].get('requested') is not expected_occupancy
            or checks[0].get('measured') is not expected_occupancy
            or checks[0].get('matched') is not True):
        raise ValueError('Exact selected gap occupancy outcome differs')
    return {'format': 'worker-c160013-delivery-cpu-boundary', 'case_id': case_id,
            'source_hashes': source_hashes, 'analysis_sha256': sha(attempt / 'analysis-report.json'),
            'result_sha256': sha(attempt / 'result.json'), 'joined_frames': 900,
            'camera_decodes': decoded, 'diagnostic_audit_passed': True,
            'native_source_accepted': False, 'actual_pixels_reviewed': False,
            'physical_acceptance_claimed': False, 'legal_conclusion': 'unresolved'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--mode', choices=('positive', 'negative'), required=True)
    args = parser.parse_args()
    if args.mode == 'positive':
        print(json.dumps(audit(args.attempt, args.case), sort_keys=True))
        return
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work', prefix='c160013-audit-negative-') as temp:
        changed = Path(temp) / 'attempt'
        shutil.copytree(args.attempt, changed, copy_function=os.link)
        frame_map = changed / 'video_frames.jsonl'
        original = frame_map.read_bytes()
        frame_map.unlink()
        frame_map.write_bytes(original.replace(b'"video_frame":0', b'"video_frame":1', 1))
        if sha(frame_map) == sha(args.attempt / 'video_frames.jsonl'):
            raise AssertionError('Negative proof did not alter the source')
        audit(changed, args.case)
    raise AssertionError('Changed original video frame map was accepted')


if __name__ == '__main__':
    main()
