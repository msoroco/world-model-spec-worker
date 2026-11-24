"""Bind existing Native trace pose and speed to mandatory recording channels."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent.parent
MANIFEST = HERE / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    manifest = json.loads(MANIFEST.read_text())
    root = json.loads((HERE / 'construction.json').read_text())
    channels = root['recording_description']['channels']
    if [channel['name'] for channel in channels] != ['maximum_projection_perpendicular_to_curb']:
        raise ValueError('Expected earlier one-channel recording contract')
    additions = [
        {'name': 'ego_pose', 'unit': 'm and deg', 'sampling_rate_hz': 20,
         'time_window': 'all 600 frames / 30 seconds', 'reference_frame': 'Native world',
         'method': 'frame-joined source trace position_m and heading_deg readback',
         'uncertainty': 'synthetic trace proves schema; original Native pose remains unverified'},
        {'name': 'ego_speed', 'unit': 'm/s', 'sampling_rate_hz': 20,
         'time_window': 'all 600 frames / 30 seconds', 'reference_frame': 'Native ego actor',
         'method': 'frame-joined source trace speed_mps readback',
         'uncertainty': 'synthetic trace proves schema; original Native speed remains unverified'},
    ]
    for group in ('below_15_ft', 'at_15_ft', 'above_15_ft'):
        trace = HERE / 'diagnostic-fixture' / group / 'sources/trace.jsonl'
        rows = [json.loads(line) for line in trace.read_text().splitlines()]
        if len(rows) != 600 or not all('position_m' in row and 'heading_deg' in row and 'speed_mps' in row for row in rows):
            raise ValueError('Retained Native-shaped trace does not supply channels: ' + group)
    root['recording_description']['channels'] = additions + channels
    write(HERE / 'construction.json', root)
    proposal = json.loads((HERE / 'proposals/cases.json').read_text())
    for row in proposal['cases']:
        row['recording_description']['channels'] = additions + row['recording_description']['channels']
    write(HERE / 'proposals/cases.json', proposal)
    semantic = json.loads((HERE / 'proposals/semantic-index.json').read_text())
    semantic['stages']['cases']['sha256'] = sha(HERE / 'proposals/cases.json')
    write(HERE / 'proposals/semantic-index.json', semantic)
    for entry in manifest['cases']:
        for candidate in (entry, *entry['candidates']):
            path = HERE / candidate['construction']
            construction = json.loads(path.read_text())
            construction['recording_description']['channels'] = additions + construction['recording_description']['channels']
            write(path, construction)
            candidate['construction_sha256'] = sha(path)
            candidate['offline']['construction_sha256'] = candidate['construction_sha256']
        entry['acquisition']['ego_pose'] = {
            'entrypoint': 'runner.py', 'method': 'retain frame-joined Native ego position_m and heading_deg',
            'evidence': 'trace.jsonl position_m, heading_deg and native frame readback'}
        entry['acquisition']['ego_speed'] = {
            'entrypoint': 'runner.py', 'method': 'retain frame-joined Native ego speed_mps',
            'evidence': 'trace.jsonl speed_mps and native frame readback'}
    write(MANIFEST, manifest)
    print(json.dumps({'manifest_sha256': sha(MANIFEST),
                      'semantic_index_sha256': sha(HERE / 'proposals/semantic-index.json')}))


if __name__ == '__main__':
    main()
