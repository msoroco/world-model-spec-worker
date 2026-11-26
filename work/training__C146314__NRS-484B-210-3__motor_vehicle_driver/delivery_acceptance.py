"""Independent source, pass, camera and provenance audit for one exact case."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('native_motion.jsonl', 'trace.jsonl', 'video_frames.jsonl',
           'capture/evidence.jsonl', 'road.xodr')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing delivery source: ' + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit(attempt, case, diagnostic=False, source_root=REPO):
    attempt, source_root = Path(attempt), Path(source_root)
    config = json.loads(required(attempt, 'config.json').read_text())
    if config.get('selected_case_id') != case or case not in (HERE.name + '__probe_a', HERE.name + '__probe_b'):
        raise ValueError('Wrong exact delivery case')
    plan = json.loads((HERE / 'case-plan.json').read_text())
    accepted = {}
    for item in plan['sources']:
        source = required(source_root, item['path'])
        if sha(source) != item['sha256']:
            raise ValueError('Changed accepted-source input: ' + item['path'])
        accepted[item['path']] = item['sha256']
    if not diagnostic:
        required(attempt, 'capture-seal.json')
        required(attempt, 'native-capture-report.json')
    provenance = json.loads(required(attempt, 'acquisition-provenance.json').read_text())
    if bool(provenance.get('diagnostic_fixture')) != diagnostic:
        raise ValueError('Delivery source provenance differs')
    motion, trace, frames, evidence = [rows(required(attempt, name)) for name in SOURCES[:4]]
    if any(len(stream) != 600 for stream in (motion, trace, frames, evidence)):
        raise ValueError('Incomplete delivery source frames')
    road_sha = sha(required(attempt, 'road.xodr'))
    overlap, off_paved, infeasible = 0, 0, 0
    for index, (native, state, frame, event) in enumerate(zip(motion, trace, frames, evidence)):
        fid = native['native_frame']
        if (native['video_frame'] != index or state['frame'] != fid or frame['native_frame'] != fid
                or event['original_frame'] != fid or native['case_id'] != case
                or native['native_map_sha256'] != road_sha or abs(state['time_s'] - frame['time_s']) > 1e-6
                or frame['camera_native_frames'] != {name: fid for name in CAMERAS}
                or event['actor_id'] != native['ego']['actor_id']
                or not any(a.get('actor_id') == native['lead']['actor_id'] for a in event['other_actors'])):
            raise ValueError('Delivery source participant/camera/time join failed')
        ego_x = native['ego']['center_xyz_m'][0]
        lead_x = native['lead']['center_xyz_m'][0]
        if abs(ego_x - lead_x) < 4.5 and native['ego']['center_xyz_m'][1] < native['lead']['center_xyz_m'][1]:
            overlap += 1
            if min(corner[1] for corner in native['ego']['body_xy_m']) < native['paved_right_edge_y_m']:
                off_paved += 1
            clearance = native['lead']['center_xyz_m'][1] - .9 - native['paved_right_edge_y_m']
            if clearance < 2.2:
                infeasible += 1
    if overlap < 1:
        raise ValueError('No original source right-pass overlap')
    digest = {name: sha(required(attempt, name)) for name in SOURCES}
    decoded = {}
    for name in CAMERAS:
        video = required(attempt, name + '.mkv')
        run = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(video),
                              '-map', '0:v:0', '-f', 'framemd5', '-'],
                             capture_output=True, text=True, check=True)
        frames_decoded = [line for line in run.stdout.splitlines() if line and not line.startswith('#')]
        if len(frames_decoded) != 600:
            raise ValueError('Incomplete decoded source camera: ' + name)
        decoded[name] = hashlib.sha256(run.stdout.encode()).hexdigest()
        digest[name + '.mkv'] = sha(video)
    return {'format': 'c146314-3-independent-delivery-audit-v1', 'case_id': case,
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion'],
            'frames': 600, 'right_pass_overlap_frames': overlap,
            'off_paved_overlap_frames': off_paved,
            'insufficient_paved_corridor_overlap_frames': infeasible,
            'source_hashes': digest, 'accepted_source_hashes': accepted,
            'decoded_frame_hashes': decoded, 'diagnostic_fixture': diagnostic,
            'physical_acceptance': False, 'original_material_review_pending': True}


def main():
    parser = argparse.ArgumentParser()
    for key in ('attempt', 'case', 'output'):
        parser.add_argument('--' + key, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--source-root')
    args = parser.parse_args()
    result = audit(args.attempt, args.case, args.diagnostic,
                   Path(args.source_root) if args.source_root else REPO)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': args.case, 'frames': result['frames'],
                      'diagnostic_fixture': args.diagnostic}))


if __name__ == '__main__':
    main()
