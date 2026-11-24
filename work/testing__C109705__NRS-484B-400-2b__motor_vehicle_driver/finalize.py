"""Saved-only source-bound departure finalization for one exact case.

This emits measured geometry and source references after independent integrity
checks. It neither repairs original evidence nor gives a statutory verdict.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('departure_saved_finalizer_audit', HERE / 'saved_delivery.py')
saved = importlib.util.module_from_spec(spec)
spec.loader.exec_module(saved)


def finalize(attempt_dir, manifest_path, *, case_id, output_path, allow_diagnostic=False):
    root = Path(attempt_dir).resolve()
    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
    audited = saved.audit(root, manifest, case_id=case_id,
                          allow_diagnostic=allow_diagnostic)
    measurement = audited['departure_measurement']
    result = {
        'format': 'worker-saved-departure-measurement',
        'case_id': case_id,
        'law_id': 'NRS-484B-400-2b',
        'source_integrity': audited['source_integrity'],
        'source_manifest_sha256': hashlib.sha256(manifest_file.read_bytes()).hexdigest(),
        'original_frame_count': audited['original_frames'],
        'observation': {
            'name': 'full_body_signed_right_of_destination_centerline_m',
            'method': 'original departure body-corner projection onto the sourced destination right normal',
            'centerline_kind': measurement['centerline_kind'],
            'per_frame': measurement['per_frame'],
            'observed_right_min_m': measurement['observed_right_min_m'],
            'observed_right_max_m': measurement['observed_right_max_m'],
            'statutory_judgment': None,
        },
        'checks': {
            'native_source_integrity': True,
            'all_participants': False,
            'time_join': True,
            'full_video_decode': False,
            'actual_pixels': False,
            'physical_completion': False,
        },
        'limitations': audited['limitations'] + measurement['limitations'],
    }
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    return target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--allow-diagnostic', action='store_true')
    args = parser.parse_args()
    finalize(args.attempt, args.manifest, case_id=args.case, output_path=args.output,
             allow_diagnostic=args.allow_diagnostic)


if __name__ == '__main__':
    main()
