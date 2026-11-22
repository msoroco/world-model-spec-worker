"""Verify the frozen accepted-metadata inventory for this assignment.

This is a source-integrity audit, not physical or statutory acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path

ASSIGNMENT_ID = 'testing__C101303__NRS-484B-127-1__motor_vehicle_driver'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(root):
    source = Path(root) / 'inputs' / ASSIGNMENT_ID
    assignment = json.loads((source / 'assignment.json').read_text())
    inventory = json.loads((source / 'evidence.json').read_text())
    seen = set()
    rows = []
    for record in inventory['recordings']:
        rid = record['recording_id']
        if rid in seen:
            raise ValueError(f'duplicate recording: {rid}')
        seen.add(rid)
        if not record['sources']:
            raise ValueError(f'missing source: {rid}')
        if record['membership']['recording_id'] != rid:
            raise ValueError(f'membership mismatch: {rid}')
        if not set(assignment['selection_targets']).issubset(record['sets']):
            raise ValueError(f'target sets missing: {rid}')
        for ref in record['sources']:
            path = Path(root) / ref['path']
            if not path.is_file() or digest(path) != ref['sha256']:
                raise ValueError(f'source hash mismatch: {ref["path"]}')
            data = json.loads(path.read_text())
            for key, expected in (
                ('recording_id', rid), ('case_id', record['membership']['case_id']),
                ('law_id', assignment['law_id']), ('cell_id', assignment['cell_id']),
                ('actor', assignment['actor']), ('status', 'accepted'),
            ):
                if data.get(key) != expected:
                    raise ValueError(f'{rid}: {key} mismatch')
            if data.get('frames', 0) <= 0 or not data.get('trace_sha256') or not data.get('video_sha256'):
                raise ValueError(f'{rid}: incomplete metadata hashes or frames')
            acceptance = data.get('acceptance', {})
            if data['trace_sha256'] != data['reconstruction'].get('original_trace_sha256'):
                raise ValueError(f'{rid}: original trace hashes differ')
            if not acceptance.get('trace_sha256'):
                raise ValueError(f'{rid}: accepted adapted trace hash missing')
            if acceptance.get('video_sha256') != data['video_sha256']:
                raise ValueError(f'{rid}: acceptance and metadata video differ')
            rows.append({'recording_id': rid, 'case_id': data['case_id'], 'frames': data['frames'],
                         'metadata_sha256': ref['sha256']})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.')
    args = parser.parse_args()
    print(json.dumps({'metadata_verified': audit(args.root)}, indent=2))


if __name__ == '__main__':
    main()
