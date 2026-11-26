"""Independent parked-lamp source and saved processing audit."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit(case_id, attempt, saved_path, fixture=False, reject_frame_join=False):
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    selected = next((e for e in manifest['cases'] if e['case_id'] == case_id), None)
    if selected is None:
        raise ValueError('Case not selected')
    if sha(ROOT / selected['construction']) != selected['construction_sha256']:
        raise ValueError('Selected construction changed')
    receipt = json.loads(saved_path.read_text())
    if (receipt.get('case_id') != case_id or receipt.get('candidate_id') != 'primary' or
            receipt.get('passed') is not True or receipt.get('recorded_only') is not True or
            receipt.get('originals_preserved') is not True or
            receipt.get('timestamp_joins', {}).get('frames') != 600 or
            receipt.get('timestamp_joins', {}).get('passed') is not True or
            receipt.get('native_revision', {}).get('construction_sha256') != selected['construction_sha256'] or
            receipt.get('physical_acceptance_claimed') is not False or
            receipt.get('legal_acceptance_claimed') is not False):
        raise ValueError('Saved processing receipt incomplete')
    hashes = receipt['original_source_hashes']
    for name, expected in hashes.items():
        path = attempt / name
        if not path.is_file() or sha(path) != expected:
            raise ValueError('Original source changed: ' + name)
    for view in VIEWS:
        if view + '.mkv' not in hashes:
            raise ValueError('Original camera missing: ' + view)
    selection = json.loads((attempt / 'candidate-selection.json').read_text())
    if (selection.get('case_id') != case_id or selection.get('candidate_id') != 'primary' or
            selection.get('construction_sha256') != selected['construction_sha256']):
        raise ValueError('Candidate selection differs')
    if not fixture and selection.get('manifest_sha256') != sha(manifest_path):
        raise ValueError('Candidate selection binds another execution manifest')
    native = rows(attempt / 'native-rows.jsonl')
    reviewed = rows(attempt / 'lamp-review.jsonl')
    frames = rows(attempt / 'video_frames.jsonl')
    trace = rows(attempt / 'trace.jsonl')
    if reject_frame_join:
        frames[-1]['native_frame'] += 1
    if len(native) != len(reviewed) or len(native) != len(frames) or len(native) != len(trace) or len(native) != 600:
        raise ValueError('Original frame count differs')
    state = 'low_beam' if case_id.endswith('__probe_a') else 'high_beam'
    for i, (n, r, f, t) in enumerate(zip(native, reviewed, frames, trace)):
        if (n['native_frame'] != r['native_frame'] or n['native_frame'] != f['native_frame'] or
                n['native_frame'] != t['frame'] or f['video_frame'] != i or
                abs(n['time_s'] - r['time_s']) > 1e-6 or
                abs(n['time_s'] - f['time_s']) > 1e-6 or
                abs(n['time_s'] - t['time_s']) > 1e-6):
            raise ValueError('Original frame join differs at ' + str(i))
        if (n['ego_speed_mps'] != 0 or n['observed_curb_lane_id'] != -2 or
                not n['observed_footprint_xyz_m'] or r['parking_activity'] != 'parked' or
                not n['requested_headlamp_lit'] or n['observed_beam_state'] != state or
                not isinstance(r['aim_elevation_deg'], (int, float)) or
                not isinstance(r['relative_intensity'], (int, float))):
            raise ValueError('Parked/lamp source incomplete at ' + str(i))
    capture = json.loads((attempt / 'capture/manifest.json').read_text())
    synthetic = capture.get('synthetic_diagnostic') is True or any(
        row.get('source_kind') == 'synthetic_cpu_fixture' for row in native)
    if fixture:
        if not synthetic:
            raise ValueError('Fixture audit requires synthetic source declaration')
    elif synthetic:
        raise ValueError('Synthetic fixture rejected from original audit')
    for view in VIEWS:
        run = subprocess.run(('ffmpeg', '-v', 'error', '-i', str(attempt / (view + '.mkv')),
                              '-map', '0:v:0', '-f', 'null', '-'),
                             capture_output=True, text=True, timeout=120)
        if run.returncode or run.stderr.strip():
            raise ValueError('Full video decode failed: ' + view)
    return {'format': 'c276263-independent-delivery-audit', 'case_id': case_id,
            'diagnostic_only': fixture, 'original_native_verified': False,
            'actual_pixels_verified': False, 'physical_completion_verified': False,
            'accepted': False, 'joined_frames': 600,
            'source_hashes_verified': len(hashes), 'videos_fully_decoded': list(VIEWS),
            'saved_receipt_sha256': sha(saved_path), 'unresolved_legal_judgment': 'depressed or dimmed'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--saved', type=Path, required=True)
    parser.add_argument('--fixture', action='store_true')
    parser.add_argument('--reject-frame-join', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.attempt, args.saved,
                           args.fixture, args.reject_frame_join)))
