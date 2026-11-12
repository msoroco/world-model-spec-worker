"""Independent original-source delivery audit for C178759 two-pass cases.

Diagnostic mode proves software joins only. Native mode requires an independently
source-bound physical and pixel review; neither mode decides the legal offense.
"""

import argparse
from hashlib import sha256
import json
from math import hypot
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'runtime'))
from scenario_pipeline.worker_exchange import media

CASE = 'heldout__C178759__NRS-484B-650-1__motor_vehicle_driver__repeated_right_pass'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('video_frames.jsonl', 'trace.jsonl', 'driving_trace.jsonl',
           'following_sources.jsonl', 'right_pass_sources.jsonl')


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit(case, attempt, *, diagnostic_fixture=False):
    root = Path(attempt)
    if case != CASE:
        raise ValueError('Wrong exact C178759 delivery case')
    config = json.loads((root / 'config.json').read_text())
    report = json.loads((root / 'analysis-report.json').read_text())
    result = json.loads((root / 'result.json').read_text())
    if any(x != case for x in (config.get('selected_case_id'), report.get('case_id'),
                              result.get('case_id'))):
        raise ValueError('Exact delivery identity differs')
    measured = report['measurements']['two_right_pass_observation']['value']
    if result.get('measured_values', {}).get('two_right_pass_observation') != measured:
        raise ValueError('Saved two-pass measurement differs')
    sources = {name: digest(root / name) for name in SOURCES}
    frame_map, native, drive, following, passing = [rows(root / name) for name in SOURCES]
    count = len(frame_map)
    if count < 3 or any(len(x) != count for x in (native, drive, following, passing)):
        raise ValueError('Original two-pass frame coverage differs')
    actor_ids = set()
    for i, (frame, point, motion, bodies, road) in enumerate(
            zip(frame_map, native, drive, following, passing)):
        key = (frame['carla_frame'], frame['time_s'])
        if (frame['video_frame'] != i or
                any((row['frame'], row['time_s']) != key
                    for row in (point, motion, bodies, road))):
            raise ValueError('Original frame/time join differs')
        ids = (bodies['ego']['actor_id'], bodies['lead']['actor_id'])
        actor_ids.add(ids)
        if (road['ego_actor_id'], road['fixed_overtaken_actor_id']) != ids:
            raise ValueError('Original overtaken actor identity differs')
        xy = road['ego_xy_m']
        lead_xy = road['lead_xy_m']
        if (hypot(xy[0] - motion['x_m'], xy[1] - motion['y_m']) > 1e-3 or
                hypot(xy[0] - bodies['ego']['position_m'][0],
                      xy[1] - bodies['ego']['position_m'][1]) > 1e-3 or
                hypot(lead_xy[0] - bodies['lead']['position_m'][0],
                      lead_xy[1] - bodies['lead']['position_m'][1]) > 1e-3):
            raise ValueError('Original road/body position join differs')
        axis = road['right_axis_xy']
        edge = road['mapped_road_edge_xy_m']
        if (abs(hypot(*axis) - 1) > 1e-3 or
                abs(sum((x - e) * a for x, e, a in zip(xy, edge, axis)) -
                    road['right_of_mapped_road_edge_m']) > 1e-3):
            raise ValueError('Mapped outer-road-edge geometry differs')
    if len(actor_ids) != 1:
        raise ValueError('Fixed ego and overtaken actor changed')
    episodes = measured.get('episodes', [])
    if measured.get('source_status') == 'candidate':
        if len(episodes) != 2 or episodes[0]['end_frame'] >= episodes[1]['start_frame']:
            raise ValueError('Two distinct ordered passing candidates absent')
        if any(e['target_vehicle_id'] != next(iter(actor_ids))[1] or
               e['before_gap_m'] >= 0 or e['after_gap_m'] <= 0 or
               not e['off_pavement_frames'] for e in episodes):
            raise ValueError('Same-vehicle rightward reversal source absent')
    mapping_sha = sources['video_frames.jsonl']
    cameras = {name: media.audit(root / (name + '.mkv'), count,
                                 mapping_sha256=mapping_sha,
                                 receipt=root / ('two-pass-source-decode-' + name + '.json'))
               for name in CAMERAS}
    composed = media.audit(root / 'raw.mkv', count, mapping_sha256=mapping_sha,
                           receipt=root / 'two-pass-source-decode-primary.json')
    review = None
    if diagnostic_fixture:
        if not (root / 'fixture-provenance.json').is_file() or (root / 'capture-seal.json').exists():
            raise ValueError('Unsealed diagnostic fixture required')
    else:
        seal_path, exit_path = root / 'capture-seal.json', root / 'native-exit.json'
        if not seal_path.is_file() or not exit_path.is_file():
            raise ValueError('Sealed Native source and owner exit missing')
        seal, owner = json.loads(seal_path.read_text()), json.loads(exit_path.read_text())
        if (seal.get('provenance_kind') != 'native' or
                seal.get('restoration', {}).get('restored') is not True or
                owner.get('event') != 'native_exit' or
                owner.get('capture_seal_sha256') != digest(seal_path)):
            raise ValueError('Native source and owner closure differ')
        path = root / 'independent-physical-review.json'
        review = json.loads(path.read_text())
        if review.get('case_id') != case or review.get('source_sha256') != sources:
            raise ValueError('Independent physical review source identity differs')
        for subject in ('ego_body', 'fixed_overtaken_vehicle', 'paved_surface',
                        'first_right_pass', 'second_right_pass', 'governing_speed_source',
                        'hazard_target'):
            item = review.get('visible', {}).get(subject, {})
            camera, frame = item.get('camera'), item.get('video_frame')
            if (camera not in cameras or type(frame) is not int or
                    not 0 <= frame < count or item.get('observed') is not True or
                    item.get('camera_sha256') != cameras[camera]['video_sha256']):
                raise ValueError('Original physical/pixel evidence missing: ' + subject)
    return {'format': 'worker-delivery-audit', 'case_id': case,
            'scope': 'synthetic software diagnostic' if diagnostic_fixture else 'source-bound Native review',
            'original_sha256': sources, 'frames': count, 'cameras': cameras,
            'auditor_path': str(Path(__file__).resolve()), 'auditor_sha256': digest(__file__),
            'source_decode_receipt_path': str(root / 'two-pass-source-decode-primary.json'),
            'source_decode_receipt_sha256': digest(root / 'two-pass-source-decode-primary.json'),
            'source_decode_auditor_sha256': composed['auditor_sha256'],
            'pixel_review': review,
            'checks': {'native_source': not diagnostic_fixture, 'all_participants': review is not None,
                       'time_join': True, 'full_video_decode': True,
                       'actual_pixels': review is not None, 'physical_completion': review is not None},
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


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
