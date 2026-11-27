"""Saved-source bridge-speed diagnostic; physical and legal review stay open."""
import argparse
import hashlib
import json
from pathlib import Path
from bridge_speed_measure import ASSIGNMENT, measure


def require(ok, message):
    if not ok:
        raise ValueError(message)


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def finalize(attempt, output, diagnostic_fixture=False):
    attempt, output = Path(attempt), Path(output)
    survey_path = attempt / 'original_bridge_survey.json'
    trace_path = attempt / 'bridge-native.jsonl'
    mapping_path = attempt / 'video_frames.jsonl'
    require(all(path.is_file() for path in (survey_path, trace_path, mapping_path)),
            'Missing original bridge survey, Native trace or frame map')
    survey = json.loads(survey_path.read_text())
    expected_kind = 'synthetic_native_sample' if diagnostic_fixture else 'original_native_bridge_survey'
    require(survey.get('assignment_id') == ASSIGNMENT and survey.get('source_kind') == expected_kind,
            'Original bridge survey identity missing' if not diagnostic_fixture else 'Synthetic fixture identity missing')
    trace = rows(trace_path)
    mapping = rows(mapping_path)
    require(len(trace) == len(mapping) == 600, '30-second original source join missing')
    require(all(row.get('frame') == i and maprow.get('video_frame') == i
                and row.get('native_frame') == maprow.get('native_frame')
                for i, (row, maprow) in enumerate(zip(trace, mapping))),
            'Original Native/video frame join missing')
    vehicle_ids = {row.get('vehicle_id') for row in trace}
    require(len(vehicle_ids) == 1 and None not in vehicle_ids, 'Original vehicle identity missing')
    trace_kind = 'synthetic_native_sample' if diagnostic_fixture else 'original_native_observation'
    require(all(row.get('source_kind') == trace_kind
                and row.get('structure_occupancy_source') == survey.get('structure_source_id')
                and type(row.get('on_structure_verified')) is bool for row in trace),
            'Original structure occupancy source missing')
    converted = {'assignment_id': ASSIGNMENT, 'source_kind': trace_kind,
                 'vehicle_id': next(iter(vehicle_ids)),
                 'frames': [{'frame': row['frame'], 't_s': row['t_s'],
                             'vehicle_id': row['vehicle_id'],
                             'structure_id': row['structure_source_id'],
                             'on_structure': row['on_structure_verified'],
                             'velocity_xyz_mps': row['velocity_xyz_mps'],
                             'requested_speed_mph': row['requested_speed_mph']}
                            for row in trace]}
    normalized_survey = dict(survey, source_kind=trace_kind)
    finding = measure(json.dumps(normalized_survey, sort_keys=True).encode(),
                      json.dumps(converted, sort_keys=True).encode())
    finding['original_bridge_survey_sha256'] = hashlib.sha256(survey_path.read_bytes()).hexdigest()
    finding['original_native_trace_sha256'] = hashlib.sha256(trace_path.read_bytes()).hexdigest()
    finding['original_frame_map_sha256'] = hashlib.sha256(mapping_path.read_bytes()).hexdigest()
    finding['case_id'] = json.loads((attempt / 'config.json').read_text())['case_id']
    finding['diagnostic_fixture'] = diagnostic_fixture
    finding['physical_completion'] = False
    finding['legal_result'] = None
    finding['source_review_pending'] = ['original structural designation and administrative records',
                                         'sign pixel/source position review',
                                         'physical bridge crossing review']
    output.write_text(json.dumps(finding, indent=2, sort_keys=True) + '\n')
    return finding


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--diagnostic-fixture', action='store_true')
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output, args.diagnostic_fixture), sort_keys=True))
