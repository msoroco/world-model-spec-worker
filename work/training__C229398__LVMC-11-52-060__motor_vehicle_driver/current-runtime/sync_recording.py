"""Synchronize retained pose/speed streams with every selected construction."""
import hashlib
import json
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent.parent
MANIFEST = PACKAGE / 'execution-manifest.json'
FINALIZER = PACKAGE / 'finalize_saved.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def sync_construction(path, pose):
    value = json.loads(path.read_text())
    channels = value['recording_description']['channels']
    if [row['name'] for row in channels] != [
            'ego_pose', 'ego_speed', 'maximum_projection_perpendicular_to_curb']:
        raise ValueError('Unexpected recording channels: ' + str(path))
    channels[0] = pose
    finalizers = [row for row in value['files'] if row['path'] == 'finalize_saved.py']
    if len(finalizers) != 1:
        raise ValueError('Finalizer omitted from construction: ' + str(path))
    finalizers[0]['content'] = FINALIZER.read_text()
    write(path, value)


def main():
    pose = {'name': 'ego_pose', 'unit': 'structured record', 'sampling_rate_hz': 20,
            'time_window': 'all 600 frames / 30 seconds', 'reference_frame': 'Native world',
            'method': 'frame-joined source trace position_m and heading_deg readback',
            'unit_views': [{'unit': 'm and deg',
                            'fields': {'/value/position_m': 'm', '/value/heading_deg': 'deg'}}],
            'uncertainty': 'synthetic trace proves schema; original Native pose remains unverified'}
    root = PACKAGE / 'construction.json'
    sync_construction(root, pose)
    proposal_path = PACKAGE / 'proposals/cases.json'
    proposal = json.loads(proposal_path.read_text())
    for row in proposal['cases']:
        if row['recording_description']['channels'][0]['name'] != 'ego_pose':
            raise ValueError('Proposal missing ego_pose')
        row['recording_description']['channels'][0] = pose
    write(proposal_path, proposal)
    index_path = PACKAGE / 'proposals/semantic-index.json'
    index = json.loads(index_path.read_text())
    index['stages']['cases']['sha256'] = sha(proposal_path)
    write(index_path, index)
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        for candidate in (entry, *entry['candidates']):
            path = PACKAGE / candidate['construction']
            sync_construction(path, pose)
            candidate['construction_sha256'] = sha(path)
            candidate['offline']['construction_sha256'] = candidate['construction_sha256']
    write(MANIFEST, manifest)
    print(json.dumps({'manifest_sha256': sha(MANIFEST),
                      'finalizer_sha256': sha(FINALIZER),
                      'semantic_index_sha256': sha(index_path)}))


if __name__ == '__main__':
    main()
