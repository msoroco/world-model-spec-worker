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
    return {'case_id': config['case_id'], 'config': config, 'context': context,
            'value': measured['value'], 'report_sha256': sha(attempt / 'analysis-report.json'),
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
    excluded = {'case_id', 'owner_controller_family_invitee'}
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
    elif comparison == 'private_authority':
        require(a['case_id'].endswith('__probe_02') and b['case_id'].endswith('__probe_03'),
                'Authority comparison case order differs')
        require(abs(ga - gb) <= 1e-6 and 0 < ga < FIVE_FEET_M,
                'Authority comparison driveway distance differs')
        require(xa['owner_controller_family_invitee'] is False and xb['owner_controller_family_invitee'] is True and
                xa['driveway_kind'] == xb['driveway_kind'] == 'private',
                'Authority comparison did not isolate private owner or invitee status')
    else:
        raise ValueError('Unknown controlled driveway comparison')
    return {'format': 'worker-driveway-comparison-audit', 'comparison_id': AID + '__' + comparison,
            'case_ids': [a['case_id'], b['case_id']], 'source_report_sha256':
            {a['case_id']: a['report_sha256'], b['case_id']: b['report_sha256']},
            'observed_gap_m': [ga, gb], 'private_authority':
            [xa['owner_controller_family_invitee'], xb['owner_controller_family_invitee']],
            'fixed_conditions_checked': ['cell', 'law', 'actor', 'rate', 'duration', 'cameras',
                                         'recording_description', 'road', 'source camera bytes',
                                         'driveway context except declared authority', 'rest interval'],
            'passed': True, 'diagnostic_only': True, 'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--a', required=True)
    parser.add_argument('--b', required=True)
    parser.add_argument('--comparison', choices=('distance_boundary', 'private_authority'), required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    receipt = compare(load(args.a), load(args.b), args.comparison)
    Path(args.output).write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'comparison_id': receipt['comparison_id'], 'passed': True}))


if __name__ == '__main__':
    main()
