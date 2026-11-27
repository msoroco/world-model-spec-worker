"""Bind the exact source observation and four-camera plan after CPU proofs."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / 'case-plan.json'


def main():
    plan = json.loads(PLAN.read_text())
    plan['camera_plan'] = {'profile': 'overview1080-capability',
        'duration_s': 30, 'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'entire highway curb, ego and curbside vehicle plus exception context',
             'interval': '600 original 20 Hz frames'},
            {'view': 'approach', 'subject': 'ego approach, halt and highway-side lateral relation',
             'interval': '600 original 20 Hz frames'},
            {'view': 'reference_corner', 'subject': 'curbside vehicle body, curb and ego overlap',
             'interval': '600 original 20 Hz frames'},
            {'view': 'driver_reference', 'subject': 'driver-side sight line to curbside body and context',
             'interval': '600 original 20 Hz frames'}]}
    plan['observations'] = [
        {'name': name, 'mandatory': True, 'reason': reason} for name, reason in (
            ('ego_pose', 'original subject motion and rest'),
            ('curbside_pose', 'original stopped curbside vehicle'),
            ('curb_geometry', 'surveyed road edge and highway side'),
            ('ego_highway_side_of_curbside', 'two-body side relation'),
            ('longitudinal_overlap_m', 'body abreast relation'),
            ('lateral_surface_gap_m', 'body surface separation'),
            ('concurrent_overlap_at_rest', 'joint stationary double-parking interval'),
            ('longest_concurrent_run_frames', 'source-bound duration without legal threshold'),
            ('activity_context', 'separate stop, stand or park purpose review'),
            ('traffic_conflict_context', 'necessity exception source'),
            ('law_compliance_context', 'applicable law exception source'),
            ('police_direction_context', 'officer authority and direction source'),
            ('device_direction_context', 'official device authority and direction source'),
            ('source_camera_frame_join', 'four-view original frame join'))]
    evidence = 'Original Native source and independently reviewed context required; CPU fixture only verifies shape.'
    source = 'inputs/' + HERE.name + '/assignment.json'
    mapping = {
        'drv.standing_or_parked': ['concurrent_overlap_at_rest',
                                  'longest_concurrent_run_frames', 'activity_context'],
        'st.road_edge': ['curb_geometry', 'curbside_pose'],
        'rel.bearing': ['ego_highway_side_of_curbside'],
        'rel.longitudinal_overlap': ['longitudinal_overlap_m'],
        'rel.surface_gap': ['lateral_surface_gap_m'],
        'drv.forced_halt': ['traffic_conflict_context'],
    }
    plan['source_observation_mapping'] = {term: {'evidence': evidence,
        'channels': channels, 'source_refs': [source,
        'native/double_parking_meter.py', 'native/finalize.py']}
        for term, channels in mapping.items()}
    for row in plan.get('mandatory_observation_terms', []):
        row['status'] = 'selected_source_mapping_original_review_pending'
    PLAN.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + '\n')
    print({'observations': len(plan['observations']),
           'source_terms': len(plan['source_observation_mapping'])})


if __name__ == '__main__':
    main()
