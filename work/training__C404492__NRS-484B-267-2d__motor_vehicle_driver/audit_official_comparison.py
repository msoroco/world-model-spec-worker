"""Audit the regulatory-vehicle follow/abreast pair from saved source rows."""
import argparse
import json
import math
from pathlib import Path

from measure_emergency import AID, measure, rows


def audit(reference_root, contrast_root):
    reference_root, contrast_root = Path(reference_root), Path(contrast_root)
    reference = measure(reference_root, branch='regulatory_moving')
    contrast = measure(contrast_root, branch='regulatory_moving')
    ref_poses = rows(reference_root / 'vehicle_poses.jsonl')
    alt_poses = rows(contrast_root / 'vehicle_poses.jsonl')
    if rows(reference_root / 'video_frames.jsonl') != rows(contrast_root / 'video_frames.jsonl'):
        raise ValueError('Original frame and time plan differs')
    if len(ref_poses) != 600 or len(alt_poses) != 600:
        raise ValueError('Complete 600-frame trajectory required')
    for left, right in zip(ref_poses, alt_poses):
        if left['emergency'] != right['emergency']:
            raise ValueError('Regulatory vehicle trajectory or light phase differs')
        for key in ('actor_id', 'heading_rad', 'half_length_m', 'half_width_m'):
            if left['ego'][key] != right['ego'][key]:
                raise ValueError('Subject fixed geometry or identity differs')
        heading = left['emergency']['heading_rad']
        def lateral(pose):
            delta_x = pose['ego']['x_m'] - pose['emergency']['x_m']
            delta_y = pose['ego']['y_m'] - pose['emergency']['y_m']
            return delta_y * math.cos(heading) - delta_x * math.sin(heading)
        if abs(lateral(left) - lateral(right)) > 1e-6:
            raise ValueError('Subject lateral lane position differs')
    for key in ('actor_id', 'x_m', 'y_m', 'heading_rad', 'half_length_m', 'half_width_m'):
        if ref_poses[0]['ego'][key] != alt_poses[0]['ego'][key]:
            raise ValueError('Initial subject pose or extent differs')
    ref_context = json.loads((reference_root / 'emergency_context.json').read_text())
    alt_context = json.loads((contrast_root / 'emergency_context.json').read_text())
    if (ref_context.get('case_id') != AID + '__official_1'
            or alt_context.get('case_id') != AID + '__official_2'):
        raise ValueError('Exact regulatory case identities differ')
    for key in ('assignment_id', 'review_kind', 'official_regulatory_vehicle',
                'regulatory_agency_vehicle_source', 'qualifying_flash_equipment_reviewed',
                'officer_directed_otherwise', 'ego_actor_id', 'emergency_actor_id',
                'ego_driver_source', 'ego_vehicle_source',
                'qualifying_flash_equipment_source', 'flashing_light_visual_source',
                'lane_boundary_source', 'officer_direction_review_source'):
        if ref_context.get(key) != alt_context.get(key):
            raise ValueError('Qualifying regulatory context differs: ' + key)
    if (ref_context['official_regulatory_vehicle'] is not True
            or ref_context['qualifying_flash_equipment_reviewed'] is not True
            or ref_context['officer_directed_otherwise'] is not False
            or not ref_context.get('regulatory_agency_vehicle_source')):
        raise ValueError('Regulatory moving branch lacks reviewed source context')
    ref_overlap = sum(x['longitudinal_overlap_length_m'] > 0 for x in reference['per_frame_geometry'])
    alt_overlap = sum(x['longitudinal_overlap_length_m'] > 0 for x in contrast['per_frame_geometry'])
    if ref_overlap or alt_overlap <= 0:
        raise ValueError('Regulatory overlap distinction absent')
    if reference['relative_order_crossings'] or contrast['relative_order_crossings']:
        raise ValueError('Overtaking order crossing confounds abreast pair')
    return {'format': 'c404492-official-regulatory-comparison',
            'reference_source_sha256': reference['source_sha256'],
            'contrast_source_sha256': contrast['source_sha256'],
            'reference_overlap_frames': ref_overlap,
            'contrast_overlap_frames': alt_overlap,
            'fixed_regulatory_trajectory': True,
            'fixed_initial_subject_pose': True,
            'legal_result': None, 'physical_acceptance_claimed': False, 'passed': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--contrast', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.reference, args.contrast), indent=2))


if __name__ == '__main__':
    main()
