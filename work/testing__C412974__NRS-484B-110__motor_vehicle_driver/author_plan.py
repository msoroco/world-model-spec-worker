"""Freeze the exact NRS 484B.110 alternatives and source-bound measurements."""
from __future__ import annotations

import json
from pathlib import Path

from zone_motion import CASES

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
LAW = 'NRS-484B-110'
SOURCE = 'inputs/' + AID + '/assignment.json'
CHANNELS = (
    'reviewed_site_source', 'highway_public_access', 'public_authority_dedication',
    'official_pedestrian_exclusive_designation', 'designation_interval',
    'zone_boundary', 'marking_or_sign', 'marking_visibility_history',
    'vehicle_classification', 'driver_attribution', 'vehicle_body_history',
    'vehicle_motion_history', 'zone_overlap_history', 'camera_frame_map',
)


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def main() -> None:
    path = ROOT / 'case-plan.json'
    plan = json.loads(path.read_text(encoding='utf-8'))
    gap = {
        'id': 'no-original-zone-travel-evidence',
        'requirement': 'Original highway, official pedestrian-only safety-zone designation and interval, visible marking/sign, driver/vehicle identity, and body-motion relative to original zone boundaries',
        'source': SOURCE,
        'why_existing_insufficient': 'Frozen evidence.json lists zero accepted recordings; the sole source witness is conditional and physically unverified.',
    }
    plan['evidence_review'] = {
        'reviewer': 'CPU worker',
        'method': 'Reviewed the exact NRS 484B.110 text, conditional witness and zero-entry accepted evidence inventory. No physical equivalence is claimed.',
        'facts': [],
        'gaps': [gap],
    }
    plan['cases'] = [
        {
            'case_id': AID + '__' + c.name,
            'target_law_id': LAW,
            'branch': 'driven through or within a safety zone',
            'route_variant': c.route,
            'designation_status': c.designation,
            'gap_ids': [gap['id']],
            'construction': 'zone_motion.validate_scene and Native source-gated construction: physical boundary markers, roadway, controlled vehicle route and 20 Hz original body capture',
            'measurement': 'zone_motion.measure_original: joined 900-frame original body, motion, zone boundary, designation and marking source histories',
            'physical_risk': 'Official designation and continuing marking/sign visibility need independent original-source review; actual body motion and camera coverage need later CARLA review.',
            'legal_judgment': 'unresolved',
        }
        for c in CASES
    ]
    pairs = (
        ('through_vs_beside', 'through_zone', 'beside_zone', 'ego trajectory relative to fixed safety-zone boundaries'),
        ('through_vs_within', 'through_zone', 'within_zone', 'ego terminal trajectory: exits zone versus remains inside'),
        ('through_vs_unverified', 'through_zone', 'through_unverified_designation', 'official pedestrian-only designation and visible marking/sign provenance'),
    )
    plan['comparisons'] = [
        {
            'comparison_id': name,
            'case_ids': [AID + '__' + a, AID + '__' + b],
            'fixed_conditions': 'same source-reviewed public highway, physical zone boundary, driver, motor vehicle, 20 Hz, 45 s, four-camera plan and unrelated context',
            'deliberate_differences': [difference],
        }
        for name, a, b, difference in pairs
    ]
    ids = [x['case_id'] for x in plan['cases']]
    plan['requirement_dispositions'] = [
        {
            'requirement': 'Vehicle driven through a designated safety zone or remaining within it',
            'source': SOURCE,
            'status': 'selected_required',
            'evidence_or_gap': gap['why_existing_insufficient'],
            'case_ids': ids,
        }
    ]
    plan['observations'] = [
        {'name': name, 'mandatory': True, 'description': 'Original source-bound ' + name.replace('_', ' ')}
        for name in CHANNELS
    ]
    plan['source_observation_mapping'] = {}
    plan['camera_plan'] = {
        'profile': 'overview1080-capability',
        'duration_s': 45,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'fixed zone boundaries and complete vehicle route', 'interval': 'whole encounter'},
            {'view': 'approach', 'subject': 'entry, exit and body footprint', 'interval': 'whole encounter'},
            {'view': 'reference_corner', 'subject': 'physical markings/signs and zone edge', 'interval': 'whole encounter'},
            {'view': 'driver_reference', 'subject': 'vehicle driver reference and zone marking/sign visibility', 'interval': 'whole encounter'},
        ],
    }
    plan['runtime_uncertainties'] = [
        'A physical marker or colored rendering alone does not establish official pedestrian-only designation.',
        'The unverified-designation contrast is an evidence-source contrast; it does not assert that the designation is legally absent.',
        'Any frame-overlap or synthetic fixture result is a geometric diagnostic, not a legal determination.',
    ]
    plan['planning_status'] = 'selected_cpu_package_in_progress'
    write(path, plan)
    write(ROOT / 'measurement-contract.json', {
        'format': 'worker-measurement-contract',
        'requirements': [
            {
                'disposition_index': 0,
                'requirement': plan['requirement_dispositions'][0]['requirement'],
                'source': SOURCE,
                'output_key': 'safety_zone_original_body_motion',
                'method': 'analyze',
                'value_type': 'object',
                'kind': 'measured',
                'inputs': ['safety-zone-history.jsonl', 'safety-zone-site.json', 'trace.jsonl', 'video_frames.jsonl'],
            }
        ],
        'negative': {'remove': ['safety-zone-site.json'], 'error_contains': 'Missing required source: safety-zone-site.json'},
    })


if __name__ == '__main__':
    main()
