"""Expand the exact bus-stop standing branch without treating pixels as law."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    assignment = json.loads((REPO / 'inputs' / AID / 'assignment.json').read_text())
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    src = {'path': f'inputs/{AID}/assignment.json',
           'sha256': sha(REPO / 'inputs' / AID / 'assignment.json')}
    plan['cases'] = []
    for conduct in ('stand', 'park'):
        for relation in ('inside', 'outside'):
            plan['cases'].append({
                'case_id': AID + '__' + conduct + '_' + relation,
                'kind': 'delivery', 'target_law_id': assignment['law_id'],
                'conduct': conduct, 'location_relation': relation,
                'gap_ids': ['no_accepted_original_source', 'no_reviewed_designation_and_termini'],
                'site_source_requirement': 'original public-street and stop designation, signs, boundary, route origin/destination and bus/operator identity',
                'note': 'Inside/outside is a measured body-to-reviewed-boundary relation; other permissible termini must be checked before legal interpretation.'})
    def ids(*suffixes):
        return [AID + '__' + suffix for suffix in suffixes]
    plan['comparisons'] = [
        {'comparison_id': 'stand_stop_boundary',
         'case_ids': ids('stand_inside', 'stand_outside'),
         'fixed_conditions': ['same reviewed one-way public street and designated bus stop', 'same covered non-tour bus, operator and assigned route', 'same standing activity and complete 45 s four-camera capture', 'same bus dimensions, approach and stop duration'],
         'deliberate_differences': ['source-measured standing body position inside versus outside designated stop boundary']},
        {'comparison_id': 'park_stop_boundary',
         'case_ids': ids('park_inside', 'park_outside'),
         'fixed_conditions': ['same reviewed one-way public street and designated bus stop', 'same covered non-tour bus, operator and assigned route', 'same parking activity and complete 45 s four-camera capture', 'same bus dimensions, approach and stop duration'],
         'deliberate_differences': ['source-measured parking body position inside versus outside designated stop boundary']},
        {'comparison_id': 'stand_versus_park_inside',
         'case_ids': ids('stand_inside', 'park_inside'),
         'fixed_conditions': ['same reviewed one-way public street and designated bus stop', 'same covered non-tour bus, operator and assigned route', 'same source-measured inside-stop body position and complete 45 s four-camera capture'],
         'deliberate_differences': ['source-reviewed standing versus parking conduct']},
    ]
    plan['camera_plan'] = {'profile': 'overview1080-capability', 'rate_hz': 20,
        'duration_s': 45, 'composition': 'synchronized_four_view_primary',
        'views': ['overview', 'approach', 'reference_corner', 'driver_reference'],
        'coverage': [
            {'view': 'overview', 'subject': 'complete bus body, public one-way street, stop boundary and route context', 'interval': 'full 45 s capture'},
            {'view': 'approach', 'subject': 'bus approach, stopped interval and departure', 'interval': 'full 45 s capture'},
            {'view': 'reference_corner', 'subject': 'official stop designation, signs and source-reviewed boundary', 'interval': 'full 45 s capture'},
            {'view': 'driver_reference', 'subject': 'body position, door side and standing or parking activity', 'interval': 'full 45 s capture'}]}
    plan['evidence_review'] = {'reviewer': 'CPU worker',
        'method': 'Reviewed the frozen evidence inventory: zero accepted recordings. The conditional witness supplies no original City Traffic Engineer stop designation, boundary, route termini or public-street proof. No equivalent recording is available.',
        'facts': [], 'gaps': [
            {'id': 'no_accepted_original_source', 'requirement': 'Original covered bus, operator, public street and continuous conduct evidence', 'source': src,
             'why_existing_insufficient': 'Frozen accepted evidence inventory is empty.'},
            {'id': 'no_reviewed_designation_and_termini', 'requirement': 'Official bus stop designation, signed boundary and assigned route origin/destination exclusion', 'source': src,
             'why_existing_insufficient': 'The frozen conditional witness contains no independent original site or route designation.'}]}
    plan['observations'] = [
        {'name': 'bus_stopped_interval', 'mandatory': True, 'channels': ['native.json', 'activity.json', 'identity.json'], 'source': '900 original Native frames and independently reviewed complete standing or parking activity'},
        {'name': 'designated_stop_and_alternatives', 'mandatory': True, 'channels': ['site.json', 'designation.json'], 'source': 'official designation, signs, stop polygon, public-street status and route origin/destination locations'},
        {'name': 'body_inside_stop', 'mandatory': True, 'channels': ['native.json', 'site.json'], 'source': 'Native bus footprint against official stop polygon during complete activity'},
        {'name': 'four_camera_frame_identity', 'mandatory': True, 'channels': ['overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv', 'video_frames.jsonl'], 'source': 'four synchronized original camera streams and Native frame map'}]
    requirements = [
        'covered bus operator and non-tour-bus exclusion',
        'public street and applicable city jurisdiction',
        'official bus stop, bus stand and assigned-route origin/destination designation and boundary',
        'standing or parking activity with complete interval',
        'observed bus-body position relative to designated stop and other permitted locations',
    ]
    plan['requirement_dispositions'] = [
        {'disposition_index': i, 'requirement': item, 'status': 'selected_required',
         'case_ids': [case['case_id'] for case in plan['cases']], 'source': src,
         'evidence_or_gap': 'No accepted original recording; retained as source-required original observation.'}
        for i, item in enumerate(requirements)]
    plan['source_observation_mapping'] = {}
    plan['judgment_range_inventory'] = []
    plan['planning_status'] = 'selected_source_gated_stop_boundary_cases'
    plan['runtime_uncertainties'] = [
        'Original stop designation, signs, exact boundary and assigned route termini require independent source review.',
        'Standing versus parking and continuous interval require independent original activity review.',
        'Actual Native motion, footprint, pixels and complete camera coverage remain unverified until CARLA/original review.',
        'The C386411 bus-stop cell does not itself construct a bus stand or route origin/destination alternative; comparison checks their absence at the selected outside position.']
    (ROOT / 'case-plan.json').write_text(json.dumps(plan, indent=2, sort_keys=True) + '\n')
    print('four exact stop-boundary and conduct cases planned')


if __name__ == '__main__':
    build()
