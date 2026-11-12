"""Bind the matched far/near comparison to both full diagnostic delivery audits."""
import argparse
import json
import shutil
from pathlib import Path

from far_near_comparison_audit import compare, read, sha

FOLDER = Path(__file__).resolve().parent
FAR = 'testing__C109749__NRS-484B-253__motor_vehicle_driver__approaching_far'
NEAR = 'testing__C109749__NRS-484B-253__motor_vehicle_driver__approaching_no_yield'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def audit_binding(root, name, case_id, script):
    receipt = read(root / name)
    if (receipt.get('case_id') != case_id or receipt.get('frames') != 900 or
            receipt.get('passed') is not False or
            receipt.get('software_checks_passed') is not True or
            receipt.get('diagnostic_fixture') is not True or
            receipt.get('physical_acceptance_claimed') is not False):
        raise ValueError('Full diagnostic delivery audit missing: ' + case_id)
    seal = read(root / 'capture-seal.json')
    required = {'config.json', 'intersection_geometry.json',
                'interaction_history.jsonl', 'video_frames.jsonl', 'trace.jsonl',
                *(camera + '.mkv' for camera in CAMERAS)}
    if not required <= set(seal.get('sources', {})):
        raise ValueError('Diagnostic delivery seal omits an original: ' + case_id)
    for name, digest in seal['sources'].items():
        source = (root / name).resolve()
        if root.resolve() not in source.parents or not source.is_file() or digest != sha(source):
            raise ValueError('Sealed original source changed: ' + name)
    if (receipt.get('original_sources', {}).get('history_sha256') !=
            sha(root / 'interaction_history.jsonl') or
            receipt.get('source_result_sha256') != sha(root / 'result.json') or
            receipt.get('video_sha256') != sha(root / 'raw.mkv') or
            receipt.get('auditor_sha256') != sha(FOLDER / script)):
        raise ValueError('Diagnostic delivery audit differs from retained source: ' + case_id)
    return sha(root / ('far-diagnostic-audit.json' if case_id == FAR
                       else 'matched-diagnostic-audit.json'))


def prove(far_root, near_root, output):
    if output.exists():
        raise ValueError('Use a fresh audited-comparison output')
    far_audit = audit_binding(far_root, 'far-diagnostic-audit.json', FAR,
                              'far_delivery_audit.py')
    near_audit = audit_binding(near_root, 'matched-diagnostic-audit.json', NEAR,
                               'approaching_delivery_audit.py')
    result = compare(far_root, near_root)
    negative = output / 'missing-camera-negative'
    negative.mkdir(parents=True)
    for name in ('capture-seal.json', 'matched-diagnostic-audit.json',
                 'result.json', 'raw.mkv',
                 *(name for name in read(near_root / 'capture-seal.json')['sources']
                   if name != 'overview.mkv')):
        shutil.copy2(near_root / name, negative / name)
    try:
        audit_binding(negative, 'matched-diagnostic-audit.json', NEAR,
                      'approaching_delivery_audit.py')
    except ValueError as error:
        if 'Sealed original source changed: overview.mkv' not in str(error):
            raise
    else:
        raise ValueError('Missing near original camera was accepted')
    result.update({'far_delivery_audit_sha256': far_audit,
                   'near_delivery_audit_sha256': near_audit,
                   'audited_attempts': True, 'missing_camera_rejected': True})
    (output / 'comparison.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'receipt_sha256': sha(output / 'comparison.json'), **result},
                     sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--far-root', type=Path, required=True)
    parser.add_argument('--near-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    prove(args.far_root.resolve(), args.near_root.resolve(), args.output.resolve())


if __name__ == '__main__':
    main()
