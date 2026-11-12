"""Independent saved-source and video audit for C228508 delivery cases.

Diagnostic fixtures establish software joins and decode only. Native mode
requires sealed ownership and an independent source-bound physical review.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'runtime'))
from scenario_pipeline.worker_exchange import media

from window_audit import audit as audit_window


PREFIX = 'heldout__C228508__NRS-484B-650-1__motor_vehicle_driver__'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('video_frames.jsonl', 'trace.jsonl', 'driving_trace.jsonl',
           'following_sources.jsonl', 'event_annotations.json')


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _physical_review(root, case, camera_receipts, frames, source_hashes):
    path = root / 'independent-physical-review.json'
    if not path.is_file():
        raise ValueError('Independent physical review missing')
    review = json.loads(path.read_text())
    if (review.get('case_id') != case or not review.get('reviewer')
            or review.get('source_sha256') != source_hashes):
        raise ValueError('Independent physical review source identity differs')
    for subject in ('ego_body', 'lead_body', 'governing_speed_source',
                    'hazard_target'):
        item = review.get('visible', {}).get(subject, {})
        camera, frame = item.get('camera'), item.get('video_frame')
        if (camera not in camera_receipts or
                item.get('camera_sha256') != camera_receipts[camera]['video_sha256']
                or type(frame) is not int or not 0 <= frame < frames
                or item.get('observed') is not True):
            raise ValueError('Original physical/pixel evidence missing: ' + subject)
    return {'path': path.name, 'sha256': digest(path),
            'reviewer': review['reviewer']}


def audit(case, attempt, *, diagnostic_fixture=False):
    root = Path(attempt)
    config = json.loads((root / 'config.json').read_text())
    report = json.loads((root / 'analysis-report.json').read_text())
    result = json.loads((root / 'result.json').read_text())
    if (not case.startswith(PREFIX) or
            any(item.get('case_id') != case for item in (report, result)) or
            config.get('selected_case_id') != case):
        raise ValueError('Exact aggressive-driving audit identity differs')
    observed = report['measurements']['aggressive_window_observation']['value']
    if result['measured_values'].get('aggressive_window_observation') != observed:
        raise ValueError('Saved aggressive-driving measurement differs')
    audit_window(root, root / 'analysis-report.json')
    source_hashes = {name: digest(root / name) for name in SOURCES}
    map_rows, trace, drive, lead = (_rows(root / name) for name in SOURCES[:4])
    if not map_rows or not (len(map_rows) == len(trace) == len(drive) == len(lead)):
        raise ValueError('Original aggressive-driving body/time join incomplete')
    for index, (video, native, path, actor) in enumerate(zip(map_rows, trace, drive, lead)):
        identity = (video['carla_frame'], video['time_s'])
        if (video['video_frame'] != index or
                (native['frame'], native['time_s']) != identity or
                (path['frame'], path['time_s']) != identity or
                (actor['frame'], actor['time_s']) != identity):
            raise ValueError('Original aggressive-driving body/time join differs')
    mapping_sha = source_hashes['video_frames.jsonl']
    cameras = {name: media.audit(root / (name + '.mkv'), len(map_rows),
                                 mapping_sha256=mapping_sha,
                                 receipt=root / ('following-source-decode-' + name + '.json'))
               for name in CAMERAS}
    composed = media.audit(root / 'raw.mkv', len(map_rows),
                           mapping_sha256=mapping_sha,
                           receipt=root / 'following-source-decode-primary.json')
    review = None
    if diagnostic_fixture:
        if not (root / 'fixture-provenance.json').is_file() or (root / 'capture-seal.json').exists():
            raise ValueError('Marked unsealed diagnostic fixture required')
    else:
        seal_path, exit_path = root / 'capture-seal.json', root / 'native-exit.json'
        if not seal_path.is_file() or not exit_path.is_file():
            raise ValueError('Sealed Native source and owner exit missing')
        seal, owner = json.loads(seal_path.read_text()), json.loads(exit_path.read_text())
        if (seal.get('provenance_kind') != 'native' or
                seal.get('restoration', {}).get('restored') is not True or
                owner.get('event') != 'native_exit' or
                owner.get('capture_seal_sha256') != digest(seal_path)):
            raise ValueError('Native source/owner closure differs')
        review = _physical_review(root, case, cameras, len(map_rows), source_hashes)
    return {'format': 'worker-delivery-audit', 'case_id': case,
            'scope': 'synthetic software diagnostic' if diagnostic_fixture else 'source-bound Native review',
            'original_sha256': source_hashes, 'frames': len(map_rows),
            'cameras': cameras,
            'auditor_path': str(Path(__file__).resolve()),
            'auditor_sha256': digest(__file__),
            'source_decode_receipt_path': str(root / 'following-source-decode-primary.json'),
            'source_decode_receipt_sha256': digest(root / 'following-source-decode-primary.json'),
            'source_decode_auditor_sha256': composed['auditor_sha256'],
            'pixel_review': review,
            'checks': {'native_source': not diagnostic_fixture,
                       'all_participants': review is not None,
                       'time_join': True, 'full_video_decode': True,
                       'actual_pixels': review is not None,
                       'physical_completion': review is not None},
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--diagnostic-fixture', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.attempt,
                           diagnostic_fixture=args.diagnostic_fixture), indent=2))


if __name__ == '__main__':
    main()
