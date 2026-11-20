"""Exact C223016 CPU acceptance audit over retained saved diagnostic sources."""
import argparse
import json
import shlex
import sys
from pathlib import Path

from delivery_audit import audit as audit_sources, physical_fixture

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime' / 'scenario_pipeline'))
from worker_exchange.media import audit as audit_video

CAMERAS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
           'driver_reference.mkv')


def verify(case_id, negative=False, *, attempt_override=None, receipt_override=None,
           candidate='primary'):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next((x for x in manifest['cases'] if x['case_id'] == case_id), None)
    if entry is None or entry['kind'] != 'delivery':
        raise ValueError('Unknown exact C223016 delivery case')
    proof = entry['saved_processing_proof']
    command = shlex.split(proof['command'])
    attempt = Path(command[command.index('--attempt') + 1])
    receipt = HERE / proof['log']
    attempt = Path(attempt_override) if attempt_override else attempt
    receipt = Path(receipt_override) if receipt_override else receipt
    source = audit_sources(candidate, attempt, receipt, tamper=negative)
    saved = json.loads(receipt.read_text())
    if saved['missing_evidence'] or not saved['recorded_only']:
        raise ValueError('Saved source analysis incomplete')
    result = json.loads(Path(saved['result']).read_text())
    if not result['measured_values'] or not all(x.get('matched') for x in result['target_checks']):
        raise ValueError('Exact case measurement absent or unmatched')
    mapping_hash = saved['original_source_hashes']['video_frames.jsonl']
    frames = source['joined_direction_frames']
    decoded = []
    for name in CAMERAS:
        row = audit_video(attempt / name, frames, mapping_sha256=mapping_hash)
        if not row['passed'] or not row['rgb_sequence_sha256']:
            raise ValueError('Full camera decode or pixel source absent')
        decoded.append({'camera': name, 'frames': row['frames'],
                        'source_sha256': row['video_sha256'],
                        'decoded_rgb_sha256': row['rgb_sequence_sha256']})
    physical = [physical_fixture(kind, str((attempt / 'config.json').resolve()))
                for kind in ('complete', 'incomplete', 'missing')]
    return {'case_id': case_id, 'checks': ['native_source', 'all_participants',
            'time_join', 'full_video_decode', 'actual_pixels', 'physical_completion'],
            'source_audit': source, 'camera_decode': decoded,
            'physical_checker_fixtures': physical,
            'measured_values': result['measured_values'],
            'synthetic_diagnostic_only': True, 'native_pixels_claimed': False,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--attempt')
    parser.add_argument('--receipt')
    parser.add_argument('--candidate', default='primary')
    args = parser.parse_args()
    print(json.dumps(verify(args.case, args.negative,
                            attempt_override=args.attempt,
                            receipt_override=args.receipt,
                            candidate=args.candidate)))
