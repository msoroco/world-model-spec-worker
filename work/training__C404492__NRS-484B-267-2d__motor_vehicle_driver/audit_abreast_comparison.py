"""Audit fixed emergency trajectory and changed subject approach from original sources."""
import argparse
import json
from pathlib import Path

from measure_emergency import measure, rows


def audit(reference_root, contrast_root):
    reference_root, contrast_root = Path(reference_root), Path(contrast_root)
    reference = measure(reference_root)
    contrast = measure(contrast_root)
    ref_poses = rows(reference_root / 'vehicle_poses.jsonl')
    alt_poses = rows(contrast_root / 'vehicle_poses.jsonl')
    ref_frames = rows(reference_root / 'video_frames.jsonl')
    alt_frames = rows(contrast_root / 'video_frames.jsonl')
    if ref_frames != alt_frames:
        raise ValueError('Original frame and time plan differs')
    for left, right in zip(ref_poses, alt_poses):
        if left['emergency'] != right['emergency']:
            raise ValueError('Emergency vehicle trajectory or light phase differs')
        for key in ('actor_id', 'y_m', 'heading_rad', 'half_length_m', 'half_width_m'):
            if left['ego'][key] != right['ego'][key]:
                raise ValueError('Subject fixed geometry or identity differs')
    for key in ('actor_id', 'x_m', 'y_m', 'heading_rad', 'half_length_m', 'half_width_m'):
        if ref_poses[0]['ego'][key] != alt_poses[0]['ego'][key]:
            raise ValueError('Initial subject pose or extent differs')
    ref_context = json.loads((reference_root / 'emergency_context.json').read_text())
    alt_context = json.loads((contrast_root / 'emergency_context.json').read_text())
    for key in ('assignment_id', 'emergency_vehicle_authorized',
                'qualifying_flash_equipment_reviewed', 'officer_directed_otherwise',
                'ego_actor_id', 'emergency_actor_id'):
        if ref_context[key] != alt_context[key]:
            raise ValueError('Qualifying statutory context differs')
    ref_overlap = sum(x['longitudinal_overlap_length_m'] > 0 for x in reference['per_frame_geometry'])
    alt_overlap = sum(x['longitudinal_overlap_length_m'] > 0 for x in contrast['per_frame_geometry'])
    if ref_overlap or alt_overlap <= 0:
        raise ValueError('Controlled overlap difference absent')
    if reference['relative_order_crossings'] or contrast['relative_order_crossings']:
        raise ValueError('Overtaking order crossing confounds abreast pair')
    return {'format': 'c404492-abreast-controlled-comparison',
            'reference_source_sha256': reference['source_sha256'],
            'contrast_source_sha256': contrast['source_sha256'],
            'reference_overlap_frames': ref_overlap,
            'contrast_overlap_frames': alt_overlap,
            'relative_order_crossings': 0,
            'fixed_emergency_trajectory': True,
            'fixed_initial_subject_pose': True,
            'legal_result': None,
            'physical_acceptance_claimed': False,
            'passed': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--contrast', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.reference, args.contrast), indent=2))


if __name__ == '__main__':
    main()
