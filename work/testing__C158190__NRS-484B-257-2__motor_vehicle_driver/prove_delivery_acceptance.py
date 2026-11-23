"""Exercise exact delivery checks on diagnostic sources; Native acceptance stays pending."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
sys.path.insert(1, str(REPO / 'runtime/python'))
from worker_exchange.physical_preparation import validate as validate_physical


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--mode', choices=('positive', 'negative'), required=True)
    args = parser.parse_args()
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next(e for e in manifest['cases'] if e['case_id'] == args.case)
    construction = HERE / entry['construction']
    if sha(construction) != entry['construction_sha256']:
        raise ValueError('Exact construction changed')
    attempt = Path(args.attempt).resolve()
    if REPO / '.runtime-work' not in attempt.parents:
        raise ValueError('Diagnostic attempt outside runtime work')
    selection = json.loads((attempt / 'candidate-selection.json').read_text())
    if selection['case_id'] != args.case or selection['candidate_id'] != 'primary' or selection['construction_sha256'] != entry['construction_sha256']:
        raise ValueError('Exact candidate source changed')
    provenance = json.loads((attempt / 'acquisition-provenance.json').read_text())
    if provenance.get('provenance_kind') != 'diagnostic' or provenance.get('diagnostic_fixture') is not True:
        raise ValueError('CPU proof requires explicit diagnostic provenance')
    validate_physical(REPO, HERE, entry)
    frame_map = rows(attempt / 'video_frames.jsonl')
    entry_history = rows(attempt / 'entry_history.jsonl')
    trace = rows(attempt / 'trace.jsonl')
    if not frame_map or len(frame_map) != len(entry_history) or len(frame_map) != len(trace):
        raise ValueError('Original frame join changed')
    if args.mode == 'negative':
        frame_map[0]['video_frame'] = -1
    for index, (frame, history, measured) in enumerate(zip(frame_map, entry_history, trace)):
        if frame.get('video_frame') != index or history.get('video_frame') != index:
            raise ValueError('Original frame join changed')
        other = history.get('other_actor_id')
        absent_other = args.case.endswith('__stop_no_other') and other is None
        if not isinstance(history.get('ego'), dict) or not (isinstance(other, int) or absent_other):
            raise ValueError('Original participant source missing')
        if not isinstance(measured, dict):
            raise ValueError('Original trace source missing')
    for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
        video = attempt / (name + '.mkv')
        decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(video), '-f', 'null', '-'],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if decoded.returncode:
            raise ValueError('Original camera video decode failed: ' + name)
    sample = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(attempt / 'overview.mkv'),
                             '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if sample.returncode or not sample.stdout:
        raise ValueError('Diagnostic camera frame could not be decoded')
    if len(set(sample.stdout[::1000])) != 1 or sample.stdout[0] != 0:
        raise ValueError('Expected blank diagnostic frame changed; review actual pixels independently')
    print(json.dumps({'case_id': args.case, 'checks': ['native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion'], 'frames': len(frame_map),
          'diagnostic_fixture': True, 'blank_pixel_rejected_for_delivery': True,
          'physical_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
