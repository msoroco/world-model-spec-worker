"""Independent selected reference/contrast Walk source comparison."""
import argparse
import hashlib
import json
from pathlib import Path

from delivery_audit import HERE, audit as audit_delivery, require


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def same_config(a, b):
    variable = {'case_id', 'selected_case_id', 'case_suffix',
                'supported_case_ids', 'case'}
    return {k: v for k, v in a.items() if k not in variable} == \
           {k: v for k, v in b.items() if k not in variable}


def compare(reference_attempt, reference_processing,
            contrast_attempt, contrast_processing, *, diagnostic=False):
    reference_attempt = Path(reference_attempt)
    contrast_attempt = Path(contrast_attempt)
    case_reference = HERE.name + '__reference'
    case_contrast = HERE.name + '__contrast'
    delivery_reference = audit_delivery(case_reference, 'primary', reference_attempt,
                                        reference_processing, diagnostic=diagnostic)
    delivery_contrast = audit_delivery(case_contrast, 'primary', contrast_attempt,
                                       contrast_processing, diagnostic=diagnostic)
    require(same_config(read(reference_attempt / 'config.json'),
                        read(contrast_attempt / 'config.json')),
            'Controlled Walk construction settings differ')
    roads = [read(path / 'road_geometry.json') for path in
             (reference_attempt, contrast_attempt)]
    road_keys = ('cell_id', 'native_map_sha256', 'crosswalk_y_range_m',
                 'bus_lane_x_range_m', 'authored_walk_signal_id')
    require(all(roads[0].get(key) == roads[1].get(key) for key in road_keys),
            'Controlled Walk road/signal geometry differs')
    samples = [rows(path / 'native_samples.jsonl') for path in
               (reference_attempt, contrast_attempt)]
    maps = [rows(path / 'video_frames.jsonl') for path in
            (reference_attempt, contrast_attempt)]
    require(all(len(data) == 480 for data in (*samples, *maps)),
            'Controlled Walk source frame count differs')
    changed_bus = 0
    for index, (ref, con, ref_map, con_map) in enumerate(zip(
            samples[0], samples[1], maps[0], maps[1])):
        ped_ref = ref.get('pedestrian_body_xy_m')
        ped_con = con.get('pedestrian_body_xy_m')
        require(isinstance(ped_ref, list) and isinstance(ped_con, list) and
                len(ped_ref) == len(ped_con) == 4 and
                all(abs(a[axis] - b[axis]) <= (0 if diagnostic else 0.35)
                    for a, b in zip(ped_ref, ped_con) for axis in (0, 1)) and
                ref_map['video_frame'] == con_map['video_frame'] == index and
                abs(ref_map['time_s'] - con_map['time_s']) < 0.051 and
                ref.get('walk_display_request') == con.get('walk_display_request') and
                ref.get('speed_provenance') == con.get('speed_provenance'),
                'Controlled pedestrian, Walk request or sampled time differs')
        changed_bus += int(ref.get('bus_body_xy_m') != con.get('bus_body_xy_m'))
    require(changed_bus > 0, 'Selected bus response did not change')
    if not diagnostic:
        reviews = [read(path / 'official-walk-review.json') for path in
                   (reference_attempt, contrast_attempt)]
        require(all(a['display'] == b['display'] and
                    a['pedestrian_facing_signal'] == b['pedestrian_facing_signal']
                    for a, b in zip(reviews[0]['observations'],
                                    reviews[1]['observations'])),
                'Independent official Walk observation differs across cases')
        result_ref = read(reference_processing.parent / 'analysis/result.json')
        result_con = read(contrast_processing.parent / 'analysis/result.json')
        measured_ref = result_ref['measured_values']['walk_crossing']
        measured_con = result_con['measured_values']['walk_crossing']
        require(delivery_reference['passed'] and delivery_contrast['passed'] and
                measured_ref['simultaneous_conflict_frames'] == 0 and
                measured_con['simultaneous_conflict_frames'] > 0 and
                measured_ref['directed_pedestrian_conflict_frames'] > 0 and
                measured_con['directed_pedestrian_conflict_frames'] > 0,
                'Original controlled Walk response comparison incomplete')
    return {'format': 'c111256-independent-walk-comparison-v1',
            'comparison_id': HERE.name + '__comparison_main',
            'case_ids': [case_reference, case_contrast],
            'passed': not diagnostic, 'diagnostic_source_shape_passed': True,
            'changed_bus_body_frames': changed_bus,
            'fixed_conditions_checked': ['construction settings', 'road geometry',
                'pedestrian body trajectory', 'Walk request', 'frame time',
                'observed official Walk display and facing' if not diagnostic
                else 'synthetic source shape only'],
            'source_sha256': {'reference': sha(reference_attempt / 'native_samples.jsonl'),
                              'contrast': sha(contrast_attempt / 'native_samples.jsonl')},
            'original_physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    for suffix in ('reference', 'contrast'):
        parser.add_argument('--' + suffix + '-attempt', type=Path, required=True)
        parser.add_argument('--' + suffix + '-processing', type=Path, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Retain prior comparison audit output')
    result = compare(args.reference_attempt, args.reference_processing,
                     args.contrast_attempt, args.contrast_processing,
                     diagnostic=args.diagnostic)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'comparison_id': result['comparison_id'],
                      'passed': result['passed']}))


if __name__ == '__main__':
    main()
