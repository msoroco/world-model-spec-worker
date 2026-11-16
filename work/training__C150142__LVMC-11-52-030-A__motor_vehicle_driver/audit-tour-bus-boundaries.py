"""Compare pinned synthetic tour-bus boundary and no-loading controls."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PREFIX = 'c150142-tour-bus-pinned-saved-'
CASES = {
    'below': ('below-result-v7', 'below-v6', 'update032-below-primary-pinned-saved-recheck.json', 36120, 1799.95, 'below', 1),
    'at': ('at-result-v1', 'at-v1', 'update033-tour-bus-at-primary-recheck.json', 36121, 1800, 'at', 1),
    'above': ('above-result-v1', 'above-v1', 'update033-tour-bus-above-primary-recheck.json', 36122, 1800.05, 'above', 1),
    'no_loading': ('no-loading-result-v1', 'no-loading-v2', 'update033-tour-bus-no-loading-primary-recheck.json', 36121, 1800, 'at', 0),
}
VARIABLE = {'requested_stationary_duration_s', 'requested_boundary',
            'stationary_frames', 'selected_case_id', 'duration_s',
            'supported_case_ids', 'case_id', 'capture_frames', 'frames',
            'activity_request'}


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare_prefix(left, right, count):
    with Path(left).open('rb') as a, Path(right).open('rb') as b:
        for i in range(count):
            if a.readline() != b.readline():
                raise ValueError('Fixed bus actor source differs at frame ' + str(i))


def audit():
    configs, sources, records = {}, {}, []
    for name, (result, attempt, summary_file, frames, duration, boundary, events) in CASES.items():
        version = REPO / '.runtime-work' / (PREFIX + result) / 'v0001'
        source = REPO / '.runtime-work' / (PREFIX + attempt)
        summary = read(ROOT / summary_file)
        processing = read(version / 'processing.json')
        config = read(source / 'config.json')
        report = read(version / 'analysis/analysis-report.json')
        measured = report['measurements']['signed_curb_observation']['value']
        negative_file = ('update032-below-primary-negative.json' if name == 'below'
                         else f'update032-tour-bus-{name.replace("_", "-")}-primary-negative.json')
        negative = read(ROOT / negative_file)
        require(summary['processing_sha256'] == sha(version / 'processing.json') and
                processing['passed'] is True and processing['candidate_id'] == 'primary' and
                processing['missing_evidence'] is False and
                processing['originals_preserved'] is True and
                summary['timestamp_join_frames'] == summary['final_decode_frames'] == frames and
                summary['reported_duration_s'] == measured['red_curb_stationary_duration_s'] == duration and
                summary['reported_boundary'] == measured['duration_relative_to_30_minutes'] == boundary and
                summary['reported_activity_events'] == len(measured['recorded_activity_events']) == events and
                measured['legal_verdict'] is None and
                negative['rejected'] is True and
                negative['positive_processing_sha256'] == summary['processing_sha256'],
                'Pinned primary or negative proof differs: ' + name)
        require(config['capture_frames'] == frames and
                config['requested_stationary_duration_s'] == duration and
                config['requested_boundary'] == boundary and
                config['activity_request'] == (None if name == 'no_loading' else 'passenger_loading'),
                'Requested boundary or activity differs: ' + name)
        configs[name], sources[name] = config, source
        records.append({'case': name, 'frames': frames, 'duration_s': duration,
                        'activity_events': events,
                        'summary_sha256': sha(ROOT / summary_file),
                        'processing_sha256': summary['processing_sha256'],
                        'negative_sha256': sha(ROOT / negative_file)})
    base = configs['below']
    for name in ('at', 'above', 'no_loading'):
        changed = {key for key in base.keys() | configs[name].keys()
                   if base.get(key) != configs[name].get(key)}
        require(changed <= VARIABLE and
                sha(sources[name] / 'native-map-readback.json') ==
                sha(sources['below'] / 'native-map-readback.json') and
                sha(sources[name] / 'red-curb-road.xodr') ==
                sha(sources['below'] / 'red-curb-road.xodr'),
                'Fixed scene or map source differs: ' + name)
        compare_prefix(sources['below'] / 'native-raw-actors.jsonl',
                       sources[name] / 'native-raw-actors.jsonl', 36120)
    return {'format': 'c150142-tour-bus-boundary-comparison-v1',
            'source_kind': 'synthetic_native_sample',
            'original_native_observed': False, 'passed': True,
            'fixed_bus_prefix_frames': 36120, 'records': records}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
