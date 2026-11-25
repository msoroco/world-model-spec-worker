"""Independent fixed-condition and source-completeness check for exact cases."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from bicycle_encounter import ASSIGNMENT, CASE_VARIANTS
from delivery_audit import audit as audit_delivery

class ComparisonError(ValueError):
    pass

def audit(left,right):
    expected=('maintain_clearance','cross_rider_path')
    if (left.get('mode'),right.get('mode'))!=expected:
        raise ComparisonError('wrong exact mode pair')
    fixed=('map_sha256','bicycle_classification_sha256','rider_rules_sha256','rider_inventory_sha256','rider_kind','ego_route_sha256','rider_route_sha256','camera_profile_sha256','duration_frames','ego_blueprint_id','bicycle_blueprint_id')
    for key in fixed:
        if not left.get(key) or left[key]!=right.get(key):
            raise ComparisonError('fixed condition missing or differs: '+key)
    for record in (left,right):
        if record.get('frame_count')!=record['duration_frames']:
            raise ComparisonError('incomplete Original history')
        if not record.get('original_sources') or not record.get('visual_rider_witness'):
            raise ComparisonError('original classification/visual source missing')
        if record.get('lawful_riding_verdict') is not None or record.get('intent_verdict') is not None or record.get('interference_verdict') is not None:
            raise ComparisonError('unsupported legal verdict supplied')
    if left.get('waiting_command_frames',0)<=0 or right.get('travel_command_frames',0)<=0:
        raise ComparisonError('commanded behavior difference not evidenced')
    return {'comparison_id':'bicycle_encounter_behavior','fixed_conditions_checked':len(fixed),'legal_verdict':None,'physical_acceptance':False}


def audit_saved(left_attempt, right_attempt, left_review, right_review, rider_kind):
    """Compare two source-bound Originals only after both independent audits pass."""
    variants = [(suffix, row) for suffix, row in CASE_VARIANTS.items()
                if row['rider_kind'] == rider_kind]
    by_mode = {row['mode']: ASSIGNMENT + '__' + suffix for suffix, row in variants}
    if set(by_mode) != {'maintain_clearance', 'cross_rider_path'}:
        raise ComparisonError('unknown exact rider modality')
    attempts = (Path(left_attempt).resolve(), Path(right_attempt).resolve())
    if attempts[0] == attempts[1]:
        raise ComparisonError('comparison requires distinct Original attempts')
    ids = (by_mode['maintain_clearance'], by_mode['cross_rider_path'])
    receipts = [audit_delivery(path, case, review)
                for path, case, review in zip(attempts, ids, (left_review, right_review))]
    sites = [json.loads((path / 'capture' / 'site.json').read_text(encoding='utf-8'))
             for path in attempts]
    configs = [json.loads((path / 'config.json').read_text(encoding='utf-8'))
               for path in attempts]
    selections = [json.loads((path / 'candidate-selection.json').read_text(encoding='utf-8'))
                  for path in attempts]
    if any(config.get('selected_case_id') != case or
           selection.get('case_id') != case or
           selection.get('candidate_id') not in ('primary', 'fallback1') or
           not isinstance(config.get('rider_throttle_scale'), (int, float))
           for config, selection, case in zip(configs, selections, ids)):
        raise ComparisonError('selected candidate or rider throttle source differs')
    if (selections[0]['candidate_id'] != selections[1]['candidate_id'] or
            configs[0]['rider_throttle_scale'] != configs[1]['rider_throttle_scale']):
        raise ComparisonError('paired candidate or rider throttle setting differs')
    fixed = ('cell_id', 'layout', 'maneuver', 'control', 'rider_kind',
             'native_map_name', 'jurisdiction', 'ego_blueprint_id',
             'bicycle_blueprint_id', 'bicycle_classification', 'ego_route_xy',
             'rider_route_xy', 'camera_poses', 'rider_throttle', 'spawn_z_m')
    for key in fixed:
        if sites[0].get(key) is None or sites[0][key] != sites[1].get(key):
            raise ComparisonError('fixed condition missing or differs: ' + key)
    source_keys = ('map_source_path', 'bicycle_classification_source_path',
                   'rider_rules_source_path', 'rider_inventory_source_path')
    for key in source_keys:
        values = []
        for path, site in zip(attempts, sites):
            relative = site.get(key)
            if not isinstance(relative, str):
                raise ComparisonError('fixed source missing: ' + key)
            capture = path / 'capture'
            target = (capture / relative).resolve()
            if not target.is_relative_to(capture) or not target.is_file():
                raise ComparisonError('fixed source unavailable: ' + key)
            values.append(hashlib.sha256(target.read_bytes()).hexdigest())
        if values[0] != values[1]:
            raise ComparisonError('fixed source differs: ' + key)
    comparison_prefix = ('bicycle' if rider_kind == 'human_powered_bicycle'
                         else rider_kind)
    return {'format': 'c111260-independent-comparison-v1',
            'comparison_id': comparison_prefix + '_encounter_behavior',
            'case_ids': list(ids), 'delivery_audits': receipts,
            'fixed_conditions_checked': len(fixed) + len(source_keys),
            'legal_verdict': None, 'physical_acceptance': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--left-attempt', required=True)
    parser.add_argument('--right-attempt', required=True)
    parser.add_argument('--left-pixel-review', required=True)
    parser.add_argument('--right-pixel-review', required=True)
    parser.add_argument('--rider-kind', required=True,
                        choices=sorted({row['rider_kind'] for row in CASE_VARIANTS.values()}))
    args = parser.parse_args()
    print(json.dumps(audit_saved(args.left_attempt, args.right_attempt,
                                  args.left_pixel_review, args.right_pixel_review,
                                  args.rider_kind), indent=2))


if __name__ == '__main__':
    main()
