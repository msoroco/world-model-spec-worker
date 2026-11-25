"""Exercise all three saved original-frame paths without claiming physical delivery."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace

from comparison_audit import audit_attempt_pair
from delivery_audit import audit_delivery
from native_capture import capture
from saved_crossing import ASSIGNMENT, CAMERAS, process_saved


class World:
    def __init__(self):
        self.frame = 0

    def tick(self):
        self.frame += 1
        return self.frame

    def get_snapshot(self):
        stamp = SimpleNamespace(elapsed_seconds=self.frame / 20)
        return SimpleNamespace(frame=self.frame, timestamp=stamp)


def main():
    repo = Path(__file__).resolve().parents[2]
    scratch = repo / '.runtime-work/c111329-diagnostic-lifecycle'
    scratch.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='proof-', dir=scratch))
    source = root / 'source'
    source.mkdir(exist_ok=True)
    sources = {}
    for name in ('map', 'corner_survey', 'authorization', 'device_inventory',
                 'exception_review'):
        path = source / (name + '.txt')
        path.write_text('diagnostic only ' + name + '\n')
        sources[name] = {'path': str(path),
                         'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    site = {'sources': sources, 'coordinate_frame': 'map_xy_m',
            'corners_clockwise': [[0, 0], [10, 0], [10, 10], [0, 10]],
            'pedestrian_route': [[0, 0], [5, 5], [10, 10]],
            'governing_device': {'id': 'diagnostic-ped-1',
                                 'authority_record_id': 'diagnostic-order',
                                 'instruction_record_id': 'diagnostic-instruction',
                                 'placement_record_id': 'diagnostic-survey',
                                 'governs': 'pedestrian_diagonal',
                                 'diagonal_authorized': True},
            'observed_device_ids': ['diagnostic-ped-1'],
            'exception_484b_290_review': 'unresolved'}
    profile = {name: (2, 2) for name in CAMERAS}

    def walker(snapshot):
        coordinate = 10 * (snapshot.frame - 1) / 899
        return {'source_kind': 'native_walker_readback',
                'original_frame': snapshot.frame, 'walker_id': 7,
                'center_xy': [coordinate, coordinate]}

    def cameras(snapshot):
        return {name: snapshot.frame for name in CAMERAS}

    def images(snapshot):
        return {name: SimpleNamespace(frame=snapshot.frame, width=2, height=2,
                                      raw_data=bytes((snapshot.frame % 251, 25, 40, 255)) * 4)
                for name in CAMERAS}

    results = {}
    attempts = {}
    for suffix in ('permissive_whole_crossing', 'prohibitive_whole_crossing',
                   'instruction_changes_during_crossing'):
        case = ASSIGNMENT + '__' + suffix
        attempt = root / suffix
        attempt.mkdir(exist_ok=True)
        attempts[suffix] = attempt

        def device(snapshot, identity, selected=suffix):
            instruction = ('diagonal_dont_walk' if selected == 'prohibitive_whole_crossing'
                           or (selected == 'instruction_changes_during_crossing'
                               and snapshot.frame >= 500) else 'diagonal_walk')
            return {'source_kind': 'native_device_readback',
                    'original_frame': snapshot.frame, 'device_id': identity,
                    'source_sha256': sources['device_inventory']['sha256'],
                    'pedestrian_governance': 'diagonal', 'instruction': instruction}

        capture(World(), site, case, attempt, walker, device, cameras,
                [[2, 2], [8, 2], [8, 8], [2, 8]], diagnostic=True,
                camera_image_reader=images, diagnostic_camera_profile=profile)
        saved = process_saved(attempt, case, attempt / 'saved-only.json',
                              allow_diagnostic=True)
        delivery = audit_delivery(attempt, case, allow_diagnostic=True)
        if not saved['full_video_decode'] or not delivery['software_checks_passed']:
            raise ValueError('diagnostic lifecycle proof incomplete')
        results[suffix] = {'case_id': case, 'original_frames': saved['original_frames'],
                           'four_original_views_full_decoded': saved['full_video_decode'],
                           'delivery_software_checks_passed': delivery['software_checks_passed'],
                           'physical_completion': delivery['physical_completion']}
    comparisons = {}
    for name, variant in (('diagonal_instruction_permissive_vs_prohibitive',
                           'prohibitive_whole_crossing'),
                          ('diagonal_instruction_phase_change',
                           'instruction_changes_during_crossing')):
        receipt = audit_attempt_pair(name, attempts['permissive_whole_crossing'],
                                     attempts[variant], allow_diagnostic=True)
        if not receipt['comparison_verified']:
            raise ValueError('diagnostic comparison not verified')
        comparisons[name] = receipt
    removed = attempts['instruction_changes_during_crossing'] / 'overview.mkv'
    removed.unlink()
    try:
        process_saved(attempts['instruction_changes_during_crossing'],
                      ASSIGNMENT + '__instruction_changes_during_crossing',
                      root / 'unexpected-missing-source-result.json',
                      allow_diagnostic=True)
    except ValueError as exc:
        if 'missing' not in str(exc) and 'escapes' not in str(exc):
            raise
        negative = str(exc)
    else:
        raise ValueError('missing original camera source was accepted')
    receipt = {'format': 'c111329-diagnostic-lifecycle-proof',
               'scope': 'software diagnostic only; synthetic site and pixels',
               'cases': results, 'comparisons': comparisons,
               'missing_original_camera_rejection': negative,
               'official_diagonal_device_verified': False,
               'exception_484b_290_resolved': False,
               'physical_completion': False}
    target = Path(__file__).resolve().parent / 'diagnostic-lifecycle-receipts.json'
    target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    shutil.rmtree(root)
    print('three saved-only cases, two comparison audits, diagnostic delivery paths and missing-original negative passed')


if __name__ == '__main__':
    main()
