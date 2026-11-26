"""Independent CPU audit of controlled driveway contrasts, never a legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path

AID = 'training__C150094__LVMC-11-52-130-A7__motor_vehicle_driver'
FIVE_FEET_M = 1.524
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(attempt):
    attempt = Path(attempt).resolve()
    report = json.loads((attempt / 'analysis-report.json').read_text())
    config = json.loads((attempt / 'config.json').read_text())
    context = json.loads((attempt / 'driveway_context.json').read_text())
    require(report.get('analysis_complete') is True and report.get('legal_verdict_claimed') is False,
            'Comparison needs completed source analysis without legal verdict')
    require(report.get('case_id') == config.get('case_id') == context.get('case_id'),
            'Comparison case/source identity differs')
    require(config.get('assignment_id') == context.get('assignment_id') == AID,
            'Comparison assignment differs')
    measured = report['measurements']['driveway_observation']
    require(measured.get('method') == 'driveway_observation', 'Driveway measurement method differs')
    hashes = measured['sources']
    for name, checksum in hashes.items():
        require(sha(attempt / name) == checksum, 'Comparison source hash differs: ' + name)
    require(set(name + '.mkv' for name in CAMERAS) <= set(hashes),
            'Comparison lacks original four-camera source binding')
    require(measured['value']['sample_count'] == 600 and measured['value']['review_kind'] == 'synthetic_diagnostic',
            'CPU comparison proof needs joined diagnostic sources')
    bounds = context['driveway_curb_interval_m']
    trace = [json.loads(line) for line in (attempt / 'native_parking_trace.jsonl').read_text().splitlines() if line]
    require(len(trace) == 600, 'Comparison requires all original footprint rows')
    overlap_depths = []
    for row in trace:
        if row['ego_speed_mps'] <= .05:
            station, half = row['ego_curb_station_m'], row['ego_half_length_m']
            overlap_depths.append(max(0.0, min(station + half, bounds[1]) -
                                      max(station - half, bounds[0])))
    value = dict(measured['value'])
    value['strict_front_overlap_frame_count'] = sum(depth > 1e-9 for depth in overlap_depths)
    value['maximum_front_overlap_m'] = max(overlap_depths, default=0.0)
    value['parking_brake_frame_count'] = sum(row.get('park_brake_engaged') is True for row in trace)
    return {'case_id': config['case_id'], 'config': config, 'context': context,
            'value': value, 'report_sha256': sha(attempt / 'analysis-report.json'),
            'source_hashes': hashes}


def compare(first, second, comparison):
    a, b = first, second
    ca, cb = a['config'], b['config']
    require(a['case_id'] != b['case_id'] and all(x['case_id'].startswith(AID + '__probe_') for x in (a, b)),
            'Comparison needs two distinct exact driveway cases')
    for key in ('cell_id', 'law_id', 'actor', 'rate_hz', 'duration_s', 'frames', 'cameras', 'recording_description'):
        require(ca.get(key) == cb.get(key), 'Fixed capture condition differs: ' + key)
    require(ca['rate_hz'] == 20 and ca['duration_s'] == 30 and ca['frames'] == 600,
            'Comparison capture rate or duration differs')
    require(a['source_hashes']['road.xodr'] == b['source_hashes']['road.xodr'],
            'Fixed road source differs')
    for name in CAMERAS:
        require(a['source_hashes'][name + '.mkv'] == b['source_hashes'][name + '.mkv'],
                'Fixed camera source differs: ' + name)
    xa, xb = a['context'], b['context']
    excluded = {'case_id'}
    if comparison in ('private_authority', 'private_controller', 'private_family', 'private_invitee'):
        excluded |= {'owner_controller_family_invitee', 'private_driveway_authority_role'}
    if comparison == 'public_private_driveway':
        excluded.add('driveway_kind')
    if comparison == 'usps_official_business':
        excluded |= {'usps_vehicle', 'usps_official_business'}
    if comparison in ('action_stop', 'action_stand', 'action_stop_stand'):
        excluded |= {'vehicle_action', 'vehicle_action_source'}
    exception_comparisons = {
        'necessary_traffic_conflict': ('13', 'necessary_to_avoid_traffic_conflict', 'traffic_conflict_source'),
        'complying_with_law': ('14', 'complying_with_law', 'applicable_law_source'),
        'officer_direction': ('15', 'officer_direction', 'officer_direction_source'),
        'traffic_device_direction': ('16', 'traffic_device_direction', 'traffic_device_direction_source')}
    if comparison in exception_comparisons:
        _, flag, source = exception_comparisons[comparison]
        excluded |= {flag, source}
    require({k:v for k,v in xa.items() if k not in excluded} ==
            {k:v for k,v in xb.items() if k not in excluded},
            'Uncontrolled driveway context differs')
    ga = a['value']['minimum_footprint_gap_m_at_rest']
    gb = b['value']['minimum_footprint_gap_m_at_rest']
    require(a['value']['rest_frame_count'] == b['value']['rest_frame_count'] == 600,
            'Fixed parking interval differs')
    if comparison == 'distance_boundary':
        require(a['case_id'].endswith('__probe_01') and b['case_id'].endswith('__probe_02'),
                'Distance comparison case order differs')
        require(xa['owner_controller_family_invitee'] is False and xb['owner_controller_family_invitee'] is False,
                'Distance comparison authority differs')
        require(ga > FIVE_FEET_M and 0 < gb < FIVE_FEET_M,
                'Distance comparison does not straddle exact five-foot boundary')
    elif comparison == 'five_foot_equality_below':
        require(a['case_id'].endswith('__probe_02') and b['case_id'].endswith('__probe_04'),
                'Below/equality comparison case order differs')
        require(0 < ga < FIVE_FEET_M and abs(gb-FIVE_FEET_M) <= 1e-6,
                'Below/equality comparison misses five feet')
    elif comparison == 'five_foot_equality_above':
        require(a['case_id'].endswith('__probe_04') and b['case_id'].endswith('__probe_01'),
                'Equality/above comparison case order differs')
        require(abs(ga-FIVE_FEET_M) <= 1e-6 and gb > FIVE_FEET_M,
                'Equality/above comparison misses five feet')
    elif comparison == 'front_overlap':
        require(a['case_id'].endswith('__probe_05') and b['case_id'].endswith('__probe_02'),
                'Front/side comparison case order differs')
        require(a['value']['strict_front_overlap_frame_count'] == 600 and
                a['value']['maximum_front_overlap_m'] > 0 and
                b['value']['strict_front_overlap_frame_count'] == 0 and
                ga == 0 and 0 < gb < FIVE_FEET_M,
                'Front/side comparison lacks positive interior body overlap')
    elif comparison == 'public_private_driveway':
        require(a['case_id'].endswith('__probe_02') and b['case_id'].endswith('__probe_06'),
                'Private/public comparison case order differs')
        require(abs(ga-gb) <= 1e-6 and 0 < ga < FIVE_FEET_M and
                xa['driveway_kind'] == 'private' and xb['driveway_kind'] == 'public' and
                xa['private_driveway_authority_role'] == xb['private_driveway_authority_role'] == 'none',
                'Private/public comparison did not isolate driveway kind')
    elif comparison == 'private_authority':
        require(a['case_id'].endswith('__probe_02') and b['case_id'].endswith('__probe_03'),
                'Authority comparison case order differs')
        require(abs(ga - gb) <= 1e-6 and 0 < ga < FIVE_FEET_M,
                'Authority comparison driveway distance differs')
        require(xa['owner_controller_family_invitee'] is False and xb['owner_controller_family_invitee'] is True and
                xa['private_driveway_authority_role'] == 'none' and
                xb['private_driveway_authority_role'] == 'owner' and
                xa['driveway_kind'] == xb['driveway_kind'] == 'private',
                'Authority comparison did not isolate private owner status')
    elif comparison == 'private_controller':
        require(a['case_id'].endswith('__probe_02') and b['case_id'].endswith('__probe_07'),
                'Controller comparison case order differs')
        require(abs(ga-gb) <= 1e-6 and 0 < ga < FIVE_FEET_M and
                xa['owner_controller_family_invitee'] is False and
                xb['owner_controller_family_invitee'] is True and
                xa['private_driveway_authority_role'] == 'none' and
                xb['private_driveway_authority_role'] == 'controller' and
                xa['driveway_kind'] == xb['driveway_kind'] == 'private',
                'Controller comparison did not isolate specific private authority')
    elif comparison in ('private_family', 'private_invitee'):
        probe, role = ('08', 'family_member') if comparison == 'private_family' else ('09', 'invitee')
        require(a['case_id'].endswith('__probe_02') and b['case_id'].endswith('__probe_' + probe),
                'Private role comparison case order differs')
        require(abs(ga-gb) <= 1e-6 and 0 < ga < FIVE_FEET_M and
                xa['owner_controller_family_invitee'] is False and
                xb['owner_controller_family_invitee'] is True and
                xa['private_driveway_authority_role'] == 'none' and
                xb['private_driveway_authority_role'] == role and
                xa['driveway_kind'] == xb['driveway_kind'] == 'private',
                'Private role comparison did not isolate specific authority')
    elif comparison == 'usps_official_business':
        require(a['case_id'].endswith('__probe_02') and b['case_id'].endswith('__probe_10'),
                'USPS comparison case order differs')
        require(abs(ga-gb) <= 1e-6 and 0 < ga < FIVE_FEET_M and
                xa['usps_vehicle'] is False and xa['usps_official_business'] is False and
                xb['usps_vehicle'] is True and xb['usps_official_business'] is True and
                xa['owner_controller_family_invitee'] is xb['owner_controller_family_invitee'] is False,
                'USPS comparison did not isolate official-business vehicle facts')
    elif comparison in ('action_stop', 'action_stand', 'action_stop_stand'):
        expected = {'action_stop': ('02', '11', None, 'stop', 600, 0),
                    'action_stand': ('02', '12', None, 'stand', 600, 0),
                    'action_stop_stand': ('11', '12', 'stop', 'stand', 0, 0)}[comparison]
        pa, pb, aa, ab, ba, bb = expected
        require(a['case_id'].endswith('__probe_' + pa) and
                b['case_id'].endswith('__probe_' + pb),
                'Action comparison case order differs')
        require(abs(ga-gb) <= 1e-6 and 0 < ga < FIVE_FEET_M and
                xa.get('vehicle_action') == aa and xb.get('vehicle_action') == ab and
                a['value']['parking_brake_frame_count'] == ba and
                b['value']['parking_brake_frame_count'] == bb and
                (aa is None or xa.get('vehicle_action_source')) and
                xb.get('vehicle_action_source'),
                'Action comparison did not isolate source-declared service-brake action')
    elif comparison in exception_comparisons:
        probe, flag, source = exception_comparisons[comparison]
        require(a['case_id'].endswith('__probe_02') and
                b['case_id'].endswith('__probe_' + probe),
                'Exception comparison case order differs')
        require(abs(ga-gb) <= 1e-6 and 0 < ga < FIVE_FEET_M and
                xa.get(flag) is False and xb.get(flag) is True and xb.get(source) and
                xa['owner_controller_family_invitee'] is xb['owner_controller_family_invitee'] is False,
                'Exception comparison did not isolate a source-declared reason')
    else:
        raise ValueError('Unknown controlled driveway comparison')
    return {'format': 'worker-driveway-comparison-audit', 'comparison_id': AID + '__' + comparison,
            'case_ids': [a['case_id'], b['case_id']], 'source_report_sha256':
            {a['case_id']: a['report_sha256'], b['case_id']: b['report_sha256']},
            'observed_gap_m': [ga, gb], 'private_authority':
            [xa['owner_controller_family_invitee'], xb['owner_controller_family_invitee']],
            'strict_front_overlap_frames': [a['value']['strict_front_overlap_frame_count'],
                                            b['value']['strict_front_overlap_frame_count']],
            'driveway_kinds': [xa['driveway_kind'], xb['driveway_kind']],
            'private_authority_roles': [xa['private_driveway_authority_role'], xb['private_driveway_authority_role']],
            'operator_actions': [xa.get('vehicle_action'), xb.get('vehicle_action')],
            'parking_brake_frames': [a['value']['parking_brake_frame_count'],
                                     b['value']['parking_brake_frame_count']],
            'fixed_conditions_checked': ['cell', 'law', 'actor', 'rate', 'duration', 'cameras',
                                         'recording_description', 'road', 'source camera bytes',
                                         'driveway context except declared comparison variable', 'rest interval'],
            'passed': True, 'diagnostic_only': True, 'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--a', required=True)
    parser.add_argument('--b', required=True)
    parser.add_argument('--comparison', choices=('distance_boundary', 'private_authority', 'private_controller',
                                                  'private_family', 'private_invitee',
                                                  'five_foot_equality_below', 'five_foot_equality_above',
                                                  'front_overlap', 'public_private_driveway',
                                                  'usps_official_business', 'action_stop', 'action_stand',
                                                  'action_stop_stand', 'necessary_traffic_conflict',
                                                  'complying_with_law', 'officer_direction',
                                                  'traffic_device_direction'), required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    receipt = compare(load(args.a), load(args.b), args.comparison)
    Path(args.output).write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'comparison_id': receipt['comparison_id'], 'passed': True}))


if __name__ == '__main__':
    main()
