"""Expand the selected red-curb statute into exact source-gated comparisons."""

import json
from pathlib import Path

from red_curb import CASES
from source_packet import ASSIGNMENT

ROOT = Path(__file__).resolve().parent


def write():
    path = ROOT / 'case-plan.json'
    plan = json.loads(path.read_text())
    previous = {case['case_id'].rsplit('__', 1)[1]: case for case in plan['cases']}
    cases = []
    for case in CASES:
        old = previous.get(case.name, previous['ordinary_park'])
        row = dict(old)
        row.update(case_id=ASSIGNMENT + '__' + case.name,
                   vehicle_kind=case.vehicle_kind, sign=case.sign,
                   activity=case.activity, requested_duration_s=case.duration_s,
                   purpose=case.purpose, mail_dropbox_adjacent=case.mail_adjacent,
                   physical_risk='Primary camera may hide original red edge, sign or mail activity; '
                                 'fallback camera pose preserves exact case variables.',
                   legal_judgment='unresolved')
        cases.append(row)
    plan['cases'] = cases
    existing = {item['comparison_id']: item for item in plan['comparisons']}
    additions = (
        ('ordinary_stop_vs_stand', 'ordinary_stop_unattended', 'ordinary_stand',
         'same ordinary vehicle, unsigned red curb and governed halt position',
         ['original stopping versus standing activity']),
        ('signed_ordinary_vs_tour', 'ordinary_park_signed', 'tour_bus_1800',
         'same restricted signed red zone and original parking interval',
         ['eligible vehicle class and passenger-loading purpose']),
        ('tour_sign', 'tour_bus_wrong_sign', 'tour_bus_1800',
         'same tour-bus status, 1800-second parking and passenger loading',
         ['required restricted-zone sign absent versus present']),
        ('tour_purpose', 'tour_bus_nonloading', 'tour_bus_1800',
         'same tour-bus status, sign and 1800-second parking',
         ['ordinary purpose versus passenger loading']),
        ('rtc_below_vs_at', 'rtc_bus_1799', 'rtc_bus_1800',
         'same RTC status, sign, curb and passenger-loading purpose',
         ['requested original duration 1799 versus 1800 seconds']),
        ('rtc_at_vs_above', 'rtc_bus_1800', 'rtc_bus_1801',
         'same RTC status, sign, curb and passenger-loading purpose',
         ['requested original duration 1800 versus 1801 seconds']),
        ('armored_business_purpose', 'armored_nonbusiness', 'armored_business',
         'same armored-car status, red curb and original parking duration',
         ['ordinary purpose versus reviewed business activity']),
        ('emergency_business_purpose', 'emergency_nonbusiness', 'emergency_business',
         'same emergency-vehicle status, red curb and original parking duration',
         ['ordinary purpose versus reviewed business activity']),
        ('mail_deposit_purpose', 'mail_stop_no_deposit', 'mail_stop',
         'same ordinary vehicle, adjacent U.S. mail box and stop duration',
         ['ordinary purpose versus actual mail deposit activity']),
    )
    for ident, left, right, fixed, different in additions:
        existing[ident] = {'comparison_id': ident,
                           'case_ids': [ASSIGNMENT + '__' + left, ASSIGNMENT + '__' + right],
                           'fixed_conditions': fixed,
                           'deliberate_differences': different}
    plan['comparisons'] = list(existing.values())
    descriptions = (
        ('red_curb_location', 'original reviewed red paint and exact edge extent'),
        ('sign_and_vehicle_status', 'original sign text and verified vehicle classification'),
        ('original_halt_activity', 'full original stop, standing or parking interval'),
        ('exception_purpose', 'passenger, business or U.S. mail activity and source context'),
        ('attendance_and_engine', 'attended and motor-running status separately retained'),
        ('governing_context', 'traffic conflict and police or device directions'),
        ('camera_frame_identity', 'four original synchronized camera frame joins'),
    )
    plan['observations'] = [
        {'name': name, 'mandatory': True, 'method': method,
         'source': 'reviewed municipal sources and original 20 Hz Native trace'}
        for name, method in descriptions]
    source = plan['sources'][0]
    clauses = (
        ('Red paint baseline prohibition for stopping, standing and parking',
         ('ordinary_park', 'ordinary_stop_unattended', 'ordinary_stand', 'ordinary_park_signed')),
        ('Signed tour, shuttle and limo passenger exception and 30-minute boundary',
         ('tour_bus_1799', 'tour_bus_1800', 'tour_bus_1801', 'tour_bus_wrong_sign',
          'tour_bus_nonloading', 'shuttle_bus_1800', 'limo_1800')),
        ('Signed RTC bus passenger exception and 30-minute boundary',
         ('rtc_bus_1799', 'rtc_bus_1800', 'rtc_bus_1801')),
        ('Armored and emergency vehicle necessary-business exception',
         ('armored_business', 'armored_nonbusiness',
          'emergency_business', 'emergency_nonbusiness')),
        ('Adjacent U.S. mail box expeditious-deposit stop exception',
         ('mail_stop', 'mail_stop_no_deposit')),
    )
    plan['requirement_dispositions'] = [
        {'requirement': requirement, 'source': source,
         'status': 'selected_required',
         'evidence_or_gap': 'No accepted exact recording; original source and Native interval required.',
         'case_ids': [ASSIGNMENT + '__' + name for name in names]}
        for requirement, names in clauses]
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': 1806,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'governed red edge, complete vehicle and municipal context',
             'interval': 'all 1806 seconds'},
            {'view': 'approach', 'subject': 'vehicle approach, halt and departure',
             'interval': 'all 1806 seconds'},
            {'view': 'reference_corner', 'subject': 'sign face or U.S. mail box and red painted edge',
             'interval': 'all 1806 seconds'},
            {'view': 'driver_reference', 'subject': 'operator attendance and passenger, business or mail activity',
             'interval': 'all 1806 seconds'},
        ]}
    plan['source_observation_mapping'] = {}
    plan['planning_status'] = 'partial_source_gated_native_capture'
    path.write_text(json.dumps(plan, indent=2) + '\n')
    return plan


if __name__ == '__main__':
    plan = write()
    print(len(plan['cases']), len(plan['comparisons']))
