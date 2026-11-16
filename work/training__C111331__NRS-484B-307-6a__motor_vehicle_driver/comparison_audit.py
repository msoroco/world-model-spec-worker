"""Independent saved-source comparison for the yellow/red entry pair."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def audit(reference, contrast, diagnostic=False):
    reference, contrast = Path(reference), Path(contrast)
    report_r, report_c = read(reference / 'analysis-report.json'), read(contrast / 'analysis-report.json')
    config_r, config_c = read(reference / 'config.json'), read(contrast / 'config.json')
    request_r, request_c = rows(reference / 'native-requests.jsonl'), rows(contrast / 'native-requests.jsonl')
    require(report_r['case_id'].endswith('__reference') and report_c['case_id'].endswith('__contrast'),
            'Exact reference and contrast case IDs required')
    require(report_r['selected'] and report_c['selected'] and not report_r['draft_only'] and not report_c['draft_only'],
            'Selected delivery reports required')
    require(config_r['assignment_source_sha256'] == config_c['assignment_source_sha256'],
            'Assignment input changed across comparison')
    for key in ('road_sha256', 'frozen_cell', 'actor', 'rate_hz', 'duration_s'):
        require(config_r[key] == config_c[key], 'Fixed condition differs: ' + key)
    require(config_r['camera_plan'] == config_c['camera_plan'], 'Fixed camera plan differs')
    require(config_r['knobs']['speed_m_per_frame'] == config_c['knobs']['speed_m_per_frame'],
            'Fixed vehicle motion policy differs')
    require(len(request_r) == len(request_c) == 480, '480 synchronized requests required')
    for a, b in zip(request_r, request_c):
        for key in ('frame', 'time_s', 'native_center_xy_m', 'native_body_xy_m',
                    'native_yaw_deg_requested', 'intersection_entrance_authored_y_m'):
            require(a[key] == b[key], 'Fixed request differs: ' + key)
    mr = report_r['measurement_detail']
    mc = report_c['measurement_detail']
    require(mr['observed_full_body_entry_frame'] == mc['observed_full_body_entry_frame'],
            'Observed vehicle entry differs across comparison')
    require(mr['observed_yellow_start_frame'] == mc['observed_yellow_start_frame'],
            'Observed yellow warning onset differs')
    require(mr['observed_red_start_frame'] > mr['observed_full_body_entry_frame'] >= mc['observed_red_start_frame'],
            'Observed red exhibition did not bracket entry')
    require(mr['observed_signal_phase_at_entry'] == 'yellow' and
            mc['observed_signal_phase_at_entry'] == 'red', 'Observed phase comparison differs')
    for report in (report_r, report_c):
        require(not report['physical_acceptance_claimed'] and not report['legal_verdict_claimed'],
                'Diagnostic cannot claim physical or legal acceptance')
    if not diagnostic:
        require(mr['physical_native_evidence'] and mc['physical_native_evidence'],
                'Original Native sources required for physical comparison')
    return {'format': 'c111331-independent-comparison-audit-v1', 'passed': True,
            'diagnostic_only': diagnostic,
            'comparison_id': report_r['case_id'].removesuffix('__reference') + '__comparison_main',
            'case_ids': [report_r['case_id'], report_c['case_id']],
            'fixed_conditions_checked': ['assignment input', 'road', 'cell', 'actor', 'rate',
                                          'duration', 'camera', 'vehicle route', 'entry frame', 'yellow onset'],
            'deliberate_difference': 'observed red onset versus observed full-body entry',
            'entry_frame': mr['observed_full_body_entry_frame'],
            'red_frames': [mr['observed_red_start_frame'], mc['observed_red_start_frame']],
            'source_hashes': {'reference_report': sha(reference / 'analysis-report.json'),
                              'contrast_report': sha(contrast / 'analysis-report.json'),
                              'reference_requests': sha(reference / 'native-requests.jsonl'),
                              'contrast_requests': sha(contrast / 'native-requests.jsonl')},
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', required=True)
    parser.add_argument('--contrast', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    result = audit(args.reference, args.contrast, args.diagnostic)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
