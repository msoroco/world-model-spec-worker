"""Compare source-bound synthetic RTC primary boundary and activity controls."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASES = {'below': (36120, 1799.95, 'below', 1),
         'at': (36121, 1800.0, 'at', 1),
         'above': (36122, 1800.05, 'above', 1),
         'no-loading': (36121, 1800.0, 'at', 0)}
VARIABLE = {'capture_frames', 'requested_stationary_duration_s',
            'requested_boundary', 'activity_request', 'case_id',
            'selected_case_id', 'supported_case_ids', 'frames',
            'stationary_frames', 'duration_s'}


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def same_prefix(a, b, lines=36120):
    with a.open('rb') as left, b.open('rb') as right:
        for index in range(lines):
            require(left.readline() == right.readline(),
                    f'Fixed bus actor changed at frame {index}')


def audit():
    records = []
    configs = {}
    attempts = {}
    for slug, (frames, seconds, boundary, activities) in CASES.items():
        version = REPO / '.runtime-work' / f'c150142-rtc-{slug}-primary-result-v1' / 'v0001'
        attempt = REPO / '.runtime-work' / f'c150142-rtc-{slug}-primary-native-v1'
        summary_path = ROOT / f'update037-rtc-{slug}-primary-pinned-saved-v1.json'
        negative_path = ROOT / f'update037-rtc-{slug}-primary-negative.json'
        summary, negative = read(summary_path), read(negative_path)
        processing, report, config = (read(version / 'processing.json'),
                                      read(version / 'analysis/analysis-report.json'),
                                      read(attempt / 'config.json'))
        measured = report['measurements']['signed_curb_observation']['value']
        require(summary['processing_sha256'] == sha(version / 'processing.json') and
                summary['processing_passed'] is True and processing['passed'] is True and
                processing['candidate_id'] == 'primary' and
                processing['missing_evidence'] is False and
                processing['originals_preserved'] is True and
                summary['timestamp_join_frames'] == summary['final_decode_frames'] == frames and
                summary['reported_duration_s'] == measured['red_curb_stationary_duration_s'] == seconds and
                summary['reported_boundary'] == measured['duration_relative_to_30_minutes'] == boundary and
                summary['reported_activity_events'] == len(measured['recorded_activity_events']) == activities and
                measured['legal_verdict'] is None and
                negative['rejected'] is True and negative['positive_processing_sha256'] == summary['processing_sha256'],
                'Pinned RTC boundary or negative proof differs: ' + slug)
        require(config['capture_frames'] == frames and
                config['requested_stationary_duration_s'] == seconds and
                config['requested_boundary'] == boundary and
                config['activity_request'] == (None if activities == 0 else 'passenger_loading'),
                'RTC request differs: ' + slug)
        configs[slug], attempts[slug] = config, attempt
        records.append({'case': slug, 'frames': frames, 'duration_s': seconds,
                        'activity_events': activities,
                        'summary_sha256': sha(summary_path),
                        'negative_sha256': sha(negative_path)})
    base = configs['below']
    for slug in ('at', 'above', 'no-loading'):
        other = configs[slug]
        changed = {key for key in base.keys() | other.keys()
                   if base.get(key) != other.get(key)}
        require(changed <= VARIABLE and
                sha(attempts[slug] / 'native-map-readback.json') ==
                sha(attempts['below'] / 'native-map-readback.json') and
                sha(attempts[slug] / 'red-curb-road.xodr') ==
                sha(attempts['below'] / 'red-curb-road.xodr'),
                'Fixed RTC map or scene changed: ' + slug)
        same_prefix(attempts['below'] / 'native-raw-actors.jsonl',
                    attempts[slug] / 'native-raw-actors.jsonl')
    return {'format': 'c150142-rtc-boundary-comparison-v1',
            'passed': True, 'original_native_observed': False,
            'fixed_bus_prefix_frames': 36120, 'records': records}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
