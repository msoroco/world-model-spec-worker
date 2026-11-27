"""Expand the exact A2 loading-stop alternatives without issuing a legal verdict."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    source = {'path': f'inputs/{AID}/assignment.json',
              'sha256': sha(REPO / 'inputs' / AID / 'assignment.json')}
    definitions = [
        ('outside_passenger', 'outside', 'passenger', 'ordinary', 'regular'),
        ('inside_bus_stop', 'bus_stop', 'passenger', 'ordinary', 'regular'),
        ('inside_bus_stand', 'bus_stand', 'passenger', 'ordinary', 'regular'),
        ('inside_loading_zone', 'passenger_loading_zone', 'passenger', 'ordinary', 'regular'),
        ('at_route_origin', 'route_origin', 'passenger', 'ordinary', 'regular'),
        ('at_route_destination', 'route_destination', 'passenger', 'ordinary', 'regular'),
        ('outside_baggage', 'outside', 'baggage', 'ordinary', 'regular'),
        ('outside_cargo', 'outside', 'cargo_only', 'ordinary', 'regular'),
        ('outside_emergency', 'outside', 'passenger', 'emergency', 'regular'),
        ('outside_tour_bus', 'outside', 'passenger', 'ordinary', 'tour'),
    ]
    gaps = ['no_original_loading_stop', 'no_official_location_designations',
            'no_original_purpose_or_exception_review']
    plan['cases'] = [
        {'case_id': AID + '__' + suffix, 'kind': 'delivery',
         'target_law_id': plan['law_id'], 'location_kind': location,
         'loading_purpose': purpose, 'stop_reason': reason, 'bus_class': bus_class,
         'gap_ids': gaps,
         'source_requirement': 'Original City designation and boundaries, assigned route, covered bus/operator, Native stopped history and independent passenger/baggage, emergency and bus-class review',
         'note': 'Case values are construction targets; original source measurements and jurisdiction control.'}
        for suffix, location, purpose, reason, bus_class in definitions]
    def ids(*suffixes):
        return [AID + '__' + suffix for suffix in suffixes]
    common = [
        'same reviewed business-district public street and all location polygons',
        'same covered bus operator, assigned route and nominal non-tour bus except the explicit exclusion pair',
        'same 45 s, 20 Hz four-camera acquisition, bus dimensions, approach and stop interval',
        'same independently reviewed passenger-loading purpose and no emergency except the explicit purpose/exception pairs']
    comparisons = []
    for suffix, title in [
        ('inside_bus_stop', 'bus_stop_boundary'),
        ('inside_bus_stand', 'bus_stand_location'),
        ('inside_loading_zone', 'passenger_loading_zone_location'),
        ('at_route_origin', 'assigned_route_origin'),
        ('at_route_destination', 'assigned_route_destination')]:
        comparisons.append({'comparison_id': title,
            'case_ids': ids('outside_passenger', suffix),
            'fixed_conditions': common,
            'deliberate_differences': ['measured stopped bus footprint outside every permitted location versus inside source-reviewed ' + title.replace('_', ' ')]})
    comparisons.extend([
        {'comparison_id': 'passenger_versus_baggage',
         'case_ids': ids('outside_passenger', 'outside_baggage'),
         'fixed_conditions': common[:3] + ['same ordinary non-emergency outside stop'],
         'deliberate_differences': ['independently reviewed passenger versus passenger baggage purpose']},
        {'comparison_id': 'passenger_versus_cargo',
         'case_ids': ids('outside_passenger', 'outside_cargo'),
         'fixed_conditions': common[:3] + ['same ordinary non-emergency outside stop'],
         'deliberate_differences': ['independently reviewed passenger versus cargo-only purpose']},
        {'comparison_id': 'emergency_exception',
         'case_ids': ids('outside_passenger', 'outside_emergency'),
         'fixed_conditions': common[:3] + ['same outside stop and passenger loading purpose'],
         'deliberate_differences': ['source-reviewed ordinary versus emergency circumstances']},
        {'comparison_id': 'tour_bus_exclusion',
         'case_ids': ids('outside_passenger', 'outside_tour_bus'),
         'fixed_conditions': ['same street, location, route, passenger purpose, stop interval and four-camera contract'],
         'deliberate_differences': ['source-reviewed regular non-tour bus versus excluded tour bus classification']},
    ])
    plan['comparisons'] = comparisons
    plan['camera_plan'] = {'profile': 'overview1080-capability', 'rate_hz': 20,
        'duration_s': 45, 'composition': 'synchronized_four_view_primary',
        'views': ['overview', 'approach', 'reference_corner', 'driver_reference'],
        'coverage': [
            {'view': 'overview', 'subject': 'entire bus, public street and designated stop/location geometry', 'interval': 'full 45 s capture'},
            {'view': 'approach', 'subject': 'bus arrival, stop and departure', 'interval': 'full 45 s capture'},
            {'view': 'reference_corner', 'subject': 'official designation, signs and measured location boundary', 'interval': 'full 45 s capture'},
            {'view': 'driver_reference', 'subject': 'bus doors, passenger/baggage purpose and actual stopped footprint', 'interval': 'full 45 s capture'}]}
    plan['evidence_review'] = {'reviewer': 'CPU worker',
        'method': 'Reviewed the frozen evidence inventory, which lists zero accepted recordings. The conditional witness is a planning prompt and supplies no original loading-stop footage, designation, bus identity or emergency facts. No equivalent source-backed recording can be reused.',
        'facts': [], 'gaps': [
            {'id': gaps[0], 'requirement': 'Original complete bus stop history on a covered public street', 'source': source, 'why_existing_insufficient': 'No accepted recording is listed.'},
            {'id': gaps[1], 'requirement': 'Official stop, stand, loading-zone and assigned-route termini designations and boundaries', 'source': source, 'why_existing_insufficient': 'No original designation or route document is supplied.'},
            {'id': gaps[2], 'requirement': 'Independent purpose, bus-class and emergency circumstances', 'source': source, 'why_existing_insufficient': 'The witness states conditional needs without reviewed original evidence.'}]}
    plan['observations'] = [
        {'name': 'original_bus_stop_history', 'mandatory': True, 'channels': ['native.json', 'activity.json', 'identity.json'], 'source': '900 joined Native bus footprint and velocity frames plus independently reviewed stop activity'},
        {'name': 'designated_location_and_route', 'mandatory': True, 'channels': ['site.json', 'designation.json', 'route.json'], 'source': 'independently reviewed official location polygons, route assignment and public-street jurisdiction'},
        {'name': 'passenger_baggage_purpose', 'mandatory': True, 'channels': ['activity.json', 'purpose.json'], 'source': 'independent intent and activity review; actual exchange is not prerequisite'},
        {'name': 'exception_and_bus_class', 'mandatory': True, 'channels': ['identity.json', 'circumstances.json'], 'source': 'independent covered-bus classification, operator and emergency review'},
        {'name': 'four_camera_frame_identity', 'mandatory': True, 'channels': ['overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv', 'video_frames.jsonl'], 'source': 'four synchronized original camera streams and Native frame map'}]
    requirements = [
        'covered operator of a bus other than a tour bus',
        'stopped on a street within applicable jurisdiction',
        'purpose of loading or unloading passengers or their baggage',
        'official bus stop location and boundary',
        'official bus stand location and boundary',
        'official passenger loading zone location and boundary',
        'assigned-route origin or destination and governing designation',
        'actual bus footprint throughout stop at or outside each permitted place',
        'case-of-emergency exception and excluded halt circumstances']
    plan['requirement_dispositions'] = [
        {'disposition_index': i, 'requirement': requirement,
         'status': 'selected_required', 'case_ids': [case['case_id'] for case in plan['cases']],
         'source': source, 'evidence_or_gap': 'No accepted original source; source-gated Native measurement and independent review required.'}
        for i, requirement in enumerate(requirements)]
    plan['source_observation_mapping'] = {}
    plan['judgment_range_inventory'] = []
    plan['planning_status'] = 'selected_source_gated_loading_stop_cases'
    plan['runtime_uncertainties'] = [
        'The scope of the designation qualifier, bus-stop definition, loading-zone terminology and emergency judgment remain legal questions for the local reviewer.',
        'Other permitted locations, route assignment, bus classification and passenger/baggage purpose require original independent source review.',
        'Fixture targets do not prove actual Native stop behavior, real pixels, valid designation or legal compliance.']
    (ROOT / 'case-plan.json').write_text(json.dumps(plan, indent=2, sort_keys=True) + '\n')
    print(f"planned {len(definitions)} exact cases and {len(comparisons)} controlled comparisons")


if __name__ == '__main__':
    build()
