"""Independent CPU source and video audit for an exact diagnostic fixture.

This checks saved bytes and complete decode; it does not certify actual pixels,
Native motion, legal sufficiency, or local delivery acceptance.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

from prove_physical import CASES
from delivery_audit import audit_decoded


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--case-id', required=True)
    parser.add_argument('--mode', choices=('positive', 'negative'), required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    args = parser.parse_args()
    package = Path(__file__).resolve().parent
    assignment = package.name
    case_id = assignment + '__' + args.case
    if args.case not in CASES:
        raise ValueError('Unknown exact case')
    if args.case_id != case_id:
        raise ValueError('Exact case identity mismatch')
    sys.path.insert(0, 'runtime/scenario_pipeline')
    from worker_exchange.fixture_recipe import materialize

    stage = args.scratch / ('delivery-' + args.case + '-' + args.mode)
    if stage.exists():
        shutil.rmtree(stage)
    recipe = package / ('diagnostic-' + args.case + '-recipe.json')
    materialize(package.parents[1], recipe, stage)
    acquisition = stage / 'acquisition.json'
    if args.mode == 'negative':
        source = json.loads(acquisition.read_text())
        source['camera_media']['overview']['sha256'] = '0' * 64
        acquisition.write_text(json.dumps(source) + '\n')
        audit_decoded(stage, acquisition, case_id)
        raise AssertionError('Corrupted original camera hash was accepted')
    report = audit_decoded(stage, acquisition, case_id)
    assert report['full_video_decode'] is True
    assert report['decoded_view_frames'] == 3600
    assert report['actual_pixels'] is False
    assert report['physical_completion'] is False
    print(json.dumps({'case_id': case_id, 'scope': 'diagnostic source and full decode only',
                      'decoded_view_frames': report['decoded_view_frames'],
                      'actual_pixels': False, 'physical_completion': False,
                      'acquisition_sha256': report['acquisition_sha256']}))


if __name__ == '__main__':
    main()
