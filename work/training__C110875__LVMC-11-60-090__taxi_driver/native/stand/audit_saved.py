"""Independent readback of retained taxi source pair and exact receipts."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = ROOT / '.runtime-work' / 'c110875-saved-sources'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines()]


def main():
    proof_path = HERE / 'saved-source-proof.json'
    proof = json.loads(proof_path.read_text())
    checks = []
    for suffix, record in zip(('probe_01', 'probe_02'), proof['records']):
        folder = OUT / suffix
        raw = lines(folder / 'native-actors.jsonl')
        mapping = lines(folder / 'video_frames.jsonl')
        request = lines(HERE / 'drafts' / suffix / 'requested-tracks.jsonl')
        if len(raw) != len(mapping) or len(raw) != len(request) or len(raw) != 600:
            raise AssertionError('Source interval shortened')
        for name, digest in record['source_sha256'].items():
            if sha(folder / name) != digest:
                raise AssertionError('Source hash changed: ' + name)
        if sha(HERE / 'drafts' / suffix / 'requested-tracks.jsonl') != record['requested_tracks_sha256']:
            raise AssertionError('Request hash changed')
        first = None
        turn = None
        for i, (actor, frame, requested) in enumerate(zip(raw, mapping, request)):
            if (actor['frame'] != i or actor['native_frame'] != frame['native_frame'] or
                    frame['video_frame'] != i or actor['time_s'] != requested['time_s'] or
                    actor['ego_xy_m'] != [requested['requested_x_m'], requested['requested_y_m']] or
                    actor['heading_deg'] != requested['requested_heading_deg']):
                raise AssertionError('Actor/video/request join changed')
            x, y = actor['ego_xy_m']
            if first is None and x >= 80:
                first = i
            if turn is None and x == 80 and y < 0 and actor['heading_deg'] == -90:
                turn = 'right'
            if turn is None and x > 80 and y == 0 and actor['heading_deg'] == 0:
                turn = 'straight'
        if first != 299 or turn != record['measurement']['measured_first_turn']:
            raise AssertionError('First intersection or turn measurement changed')
        for name, digest in record['measurement']['camera_sha256'].items():
            path = folder / name
            if sha(path) != digest:
                raise AssertionError('Camera hash changed')
            probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
                                    '-select_streams', 'v:0', '-show_entries',
                                    'stream=codec_name,nb_read_frames', '-of', 'json',
                                    str(path)], capture_output=True, text=True, check=True)
            stream = json.loads(probe.stdout)['streams'][0]
            if stream['codec_name'] != 'ffv1' or stream['nb_read_frames'] != '600':
                raise AssertionError('Camera codec/frame count changed')
        checks.append({'case_suffix': suffix, 'joined_frames': 600,
                       'first_intersection_frame': first, 'first_turn': turn,
                       'camera_sources_decoded': 4})
    if checks[0]['first_turn'] != 'right' or checks[1]['first_turn'] != 'straight':
        raise AssertionError('Controlled turn distinction absent')
    receipt = {'format': 'c110875-independent-retained-source-audit-v1',
               'saved_receipt_sha256': sha(proof_path), 'checks': checks,
               'passed': True, 'scope': 'synthetic CPU source only; no Native or legal finding'}
    path = HERE / 'saved-source-audit.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'audit_sha256': sha(path)}))


if __name__ == '__main__':
    main()
