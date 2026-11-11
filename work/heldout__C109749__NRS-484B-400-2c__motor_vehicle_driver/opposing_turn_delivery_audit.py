"""Independent original-source and full-decode audit for opposing-turn delivery."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'runtime'))
from scenario_pipeline.worker_exchange import media

from opposing_turn_measurement import measure


PREFIX = 'heldout__C109749__NRS-484B-400-2c__motor_vehicle_driver__'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('subject_original.jsonl', 'opposing_original.jsonl',
           'topology_original.json', 'devices_original.json',
           'video_frames.jsonl', 'trace.jsonl')


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit(case, attempt, *, diagnostic_fixture=False):
    root = Path(attempt)
    config = json.loads((root / 'config.json').read_text())
    report = json.loads((root / 'analysis-report.json').read_text())
    result = json.loads((root / 'result.json').read_text())
    if (not case.startswith(PREFIX) or config.get('selected_case_id') != case
            or report.get('case_id') != case or result.get('case_id') != case):
        raise ValueError('Exact opposing-turn delivery identity differs')
    measured = measure(*(root / name for name in SOURCES[:4]))
    recorded = report['measurements']['opposing_turn_geometry']
    if measured != recorded.get('value') or measured != result['measured_values'].get('opposing_turn_geometry'):
        raise ValueError('Original opposing-turn measurement differs')
    for name in SOURCES:
        if recorded['sources'].get(name) != digest(root / name):
            raise ValueError('Stale original opposing-turn source: ' + name)
    frame_map, subject, opposing, trace = (rows(root / name) for name in
                                            (SOURCES[4], SOURCES[0], SOURCES[1], SOURCES[5]))
    if not frame_map or len(frame_map) != len(subject) or len(frame_map) != len(opposing) or len(frame_map) != len(trace):
        raise ValueError('Original opposing-turn participant/frame count differs')
    actor_ids = set()
    for index, (mapping, a, b, state) in enumerate(zip(frame_map, subject, opposing, trace)):
        if (mapping.get('video_frame') != index or
                mapping.get('carla_frame') != a.get('frame') or
                a.get('frame') != b.get('frame') or a.get('frame') != state.get('frame') or
                abs(mapping.get('time_s', -1) - a.get('time_s', -2)) > 1e-6 or
                abs(a.get('time_s', -1) - b.get('time_s', -2)) > 1e-6 or
                abs(a.get('time_s', -1) - state.get('time_s', -2)) > 1e-6):
            raise ValueError('Original opposing-turn participant/time join differs')
        actor_ids.update((a.get('native_actor_id'), b.get('native_actor_id')))
    if None in actor_ids or len(actor_ids) != 2:
        raise ValueError('Original opposing-turn participant identity incomplete')
    mapping_sha = digest(root / SOURCES[4])
    cameras = {name: media.audit(root / (name + '.mkv'), len(frame_map),
                                 mapping_sha256=mapping_sha,
                                 receipt=root / ('opposing-source-decode-' + name + '.json'))
               for name in CAMERAS}
    composed = media.audit(root / 'raw.mkv', len(frame_map),
                           mapping_sha256=mapping_sha,
                           receipt=root / 'opposing-source-decode-primary.json')
    review_receipt = None
    if diagnostic_fixture:
        if not (root / 'fixture-provenance.json').is_file() or (root / 'capture-seal.json').exists():
            raise ValueError('Diagnostic opposing-turn audit requires marked unsealed fixture')
    else:
        seal_path, exit_path = root / 'capture-seal.json', root / 'native-exit.json'
        if not seal_path.is_file() or not exit_path.is_file():
            raise ValueError('Native opposing-turn closure and owner exit missing')
        seal, owner = json.loads(seal_path.read_text()), json.loads(exit_path.read_text())
        if (seal.get('provenance_kind') != 'native' or
                seal.get('restoration', {}).get('restored') is not True or
                owner.get('event') != 'native_exit' or
                owner.get('capture_seal_sha256') != digest(seal_path) or
                any(seal.get('sources', {}).get(name) != digest(root / name) for name in SOURCES)):
            raise ValueError('Native opposing-turn source closure differs')
        review_path = root / 'opposing-physical-pixel-review.json'
        if not review_path.is_file():
            raise ValueError('Native opposing-turn physical/pixel review missing')
        review = json.loads(review_path.read_text())
        if review.get('case_id') != case or not review.get('reviewer'):
            raise ValueError('Native opposing-turn review identity incomplete')
        if any(review.get('original_sha256', {}).get(name) != digest(root / name)
               for name in SOURCES):
            raise ValueError('Native opposing-turn review original binding differs')
        for label in ('subject_body', 'opposing_body', 'crossing_area'):
            visible = review.get('visible', {}).get(label, {})
            camera = visible.get('camera')
            if (camera not in cameras or
                    visible.get('camera_sha256') != cameras[camera]['video_sha256'] or
                    type(visible.get('video_frame')) is not int or
                    not 0 <= visible['video_frame'] < len(frame_map) or
                    visible.get('observed') is not True):
                raise ValueError('Native opposing-turn pixel review missing: ' + label)
        physical = review.get('physical', {})
        if (physical.get('simultaneous_left_turns_observed') is not True or
                physical.get('both_turns_completed') is not True or
                physical.get('no_contact_observed') is not True or
                physical.get('crossing_order_reviewed') is not True):
            raise ValueError('Native opposing-turn physical completion review missing')
        review_receipt = {'path': review_path.name, 'sha256': digest(review_path),
                          'reviewer': review['reviewer']}
    return {
        'format': 'worker-delivery-audit', 'case_id': case,
        'scope': ('synthetic opposing-turn software diagnostic' if diagnostic_fixture
                  else 'source-bound Native opposing-turn review'),
        'original_sha256': {name: digest(root / name) for name in SOURCES},
        'participant_ids': sorted(actor_ids), 'frames': len(frame_map),
        'cameras': cameras,
        'source_decode_receipt_path': str(root / 'opposing-source-decode-primary.json'),
        'source_decode_receipt_sha256': digest(root / 'opposing-source-decode-primary.json'),
        'source_decode_auditor_sha256': composed['auditor_sha256'],
        'physical_pixel_review': review_receipt,
        'checks': {'native_source': not diagnostic_fixture, 'all_participants': True,
                   'time_join': True, 'full_video_decode': True,
                   'actual_pixels': review_receipt is not None,
                   'physical_completion': review_receipt is not None},
        'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--diagnostic-fixture', action='store_true')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.case, args.attempt, diagnostic_fixture=args.diagnostic_fixture)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': result['case_id'], 'frames': result['frames'],
                      'checks': result['checks']}))


if __name__ == '__main__':
    main()
