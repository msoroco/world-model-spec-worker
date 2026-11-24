"""Independent CPU diagnostic source audit for an exact speed case."""
import argparse
import json
import shutil
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('case_id')
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    suffix = args.case_id.rsplit('__', 1)[-1]
    if suffix not in ('below', 'equal', 'above'):
        raise ValueError('unknown exact case')
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from delivery_audit import audit_decoded_media, audit_integrity

    source = args.scratch / f'acquisition-{suffix}-postbind'
    if args.negative:
        stage = args.scratch / f'audit-negative-{suffix}'
        if stage.exists():
            shutil.rmtree(stage)
        shutil.copytree(source, stage)
        (stage / 'original-speed.jsonl').unlink()
        # This path intentionally exits nonzero with the original-source error.
        audit_integrity(stage, args.case_id, allow_diagnostic=True)
        raise AssertionError('missing original speed source was accepted')
    proof = audit_decoded_media(source, args.case_id, allow_diagnostic=True)
    physical = json.loads((Path(__file__).resolve().parent /
                           f'physical-{suffix}-complete_motion.json').read_text())
    if physical['physical_checks']['maneuver']['status'] != 'met' or not physical['diagnostic_fixture']:
        raise ValueError('diagnostic physical completion proof missing')
    if not proof['full_video_decode']:
        raise ValueError('four-camera final decode failed')
    print(json.dumps({'case_id': args.case_id, 'checks':
                      ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
                      'full_video_decode': True, 'physical_completion': 'synthetic_fixture_met',
                      'diagnostic_fixture': True, 'physical_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
