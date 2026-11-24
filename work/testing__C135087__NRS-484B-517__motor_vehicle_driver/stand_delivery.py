"""Saved-only full source and four-video audit for one taxicab stand attempt.

Both independent source and media auditors run against the same sealed original
attempt. This is a software receipt; sign adequacy, expedience and interference
remain review judgments.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from stand import SourceError, audit_saved_attempt
from stand_media_audit import audit as audit_media


def audit(root, *, dimensions=None):
    root = Path(root)
    source = root / 'attempt-source.json'
    if source.is_symlink() or not source.is_file():
        raise SourceError('sealed original attempt source required')
    attempt = json.loads(source.read_text(encoding='utf-8'))
    inventory = audit_saved_attempt(attempt, root)
    media = audit_media(attempt, root, dimensions=dimensions)
    if inventory['case_id'] != media['case_id'] or media['decoded_view_frames'] != 3600:
        raise SourceError('original source and four-camera case/frame join differs')
    if any(media['camera_streams'][name]['sha256'] != sha for name, sha in
           inventory['source_sha256']['cameras'].items()):
        raise SourceError('original camera source changed across audits')
    return {'format': 'c135087-saved-delivery-source-audit-v1',
            'case_id': inventory['case_id'],
            'attempt_source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'source_sha256': inventory['source_sha256'],
            'original_frame_count': inventory['measurement']['source_frame_count'],
            'decoded_camera_frames': media['decoded_view_frames'],
            'camera_streams': media['camera_streams'],
            'physical_completion': False, 'pixel_visibility': 'unreviewed',
            'legal_judgment': None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.attempt)
    with Path(args.output).open('x', encoding='utf-8') as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
