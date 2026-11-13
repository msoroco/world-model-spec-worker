"""Exercise full-duration physical classifiers for staged signal cases.

Original-shaped software histories are synthetic and make no Native claim.
"""

import copy
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.native_output import physical_result
from inside_yield_observation import observe as observe_yield
from signal_advance_audit import measure as measure_signal


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def classify(entry, candidate):
    case = entry['case_id']
    target_m = entry['signal_target_m']
    source = ROOT / 'cases' / case.rsplit('__', 1)[1] / 'diagnostic.json'
    files = json.loads(source.read_text())['files']
    construction_path = ROOT / (entry['construction'] if candidate == 'primary' else
                                next(row['construction'] for row in entry['candidates']
                                     if row['id'] == candidate))
    construction = json.loads(construction_path.read_text())
    config = json.loads(next(row['content'] for row in construction['files']
                             if row['path'] == 'config.json'))
    original = [json.loads(line) for line in files['interaction_history.jsonl'].splitlines()]
    require(len(original) == 210 and config['duration_s'] == 45
            and config['rate_hz'] == 20, 'Exact source/capture contract differs')
    count = config['duration_s'] * config['rate_hz']
    with tempfile.TemporaryDirectory(prefix='c109749-signal-physical-',
                                     dir=REPO / '.runtime-work') as temp:
        attempt = Path(temp)
        write_json(attempt / 'config.json', config)
        (attempt / 'intersection_geometry.json').write_text(files['intersection_geometry.json'])
        history, mapping, trace = [], [], []
        base_frame = original[0]['frame']
        for index in range(count):
            row = copy.deepcopy(original[min(index, len(original) - 1)])
            frame = base_frame + index
            time_s = round((index + 1) / config['rate_hz'], 6)
            row['frame'], row['time_s'] = frame, time_s
            history.append(row)
            mapping.append({'video_frame': index, 'carla_frame': frame,
                            'native_frame': frame, 'time_s': time_s})
            trace.append({'frame': frame, 'time_s': time_s})
        write_rows(attempt / 'interaction_history.jsonl', history)
        write_rows(attempt / 'video_frames.jsonl', mapping)
        write_rows(attempt / 'trace.jsonl', trace)
        write_json(attempt / 'acquisition-provenance.json',
                   {'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
                    'scope': 'CPU full-duration classifier only; no physical acceptance'})
        yield_observation = observe_yield(attempt)
        signal = measure_signal(history, probes_m=(30.48,))
        met = signal['probes']['30.48']['observable_distance_met']
        require(met == (target_m >= 30.48)
                and signal['probes']['30.48']['full_signal_onset_observed'] is True,
                'Full-duration source signal differs')
        result = physical_result(attempt, {
            'case_id': case,
            'measured_values': {
                'initial_oncoming_clearance_frame': yield_observation['initial_oncoming_clearance_frame'],
                'ego_turn_start_frame': yield_observation['ego_turn_start_frame'],
                'subject_yield_frames': yield_observation['subject_yield_frames'],
                'observed_continuous_signal_advance_m': signal['observed_continuous_approach_distance_m']},
            'target_checks': [{'target': 'continuous_left_signal_at_least_30_48_m',
                               'requested': met, 'measured': met, 'matched': True,
                               'method': 'original-shaped software trajectory and indicator readback',
                               'tolerance': 0, 'physical_cause_confirmed': False,
                               'cause_evidence': ['interaction_history.jsonl']}],
            'realized_observables': {}, 'setup_confirmed': False,
            'behavior_attempted': False, 'maneuver_completed': False})
        checks = result['physical_checks']
        require(checks['setup']['status'] == 'met'
                and checks['maneuver']['status'] == 'met'
                and result['diagnostic_fixture'] is True
                and result['physical_acceptance_claimed'] is False,
                'Full-duration physical classifier did not reach diagnostic met state')
        # A short capture must never pass the full-duration setup classifier.
        write_rows(attempt / 'interaction_history.jsonl', history[:210])
        write_rows(attempt / 'video_frames.jsonl', mapping[:210])
        write_rows(attempt / 'trace.jsonl', trace[:210])
        short = physical_result(attempt, {'target_checks': [], 'realized_observables': {},
                                          'setup_confirmed': False,
                                          'behavior_attempted': False,
                                          'maneuver_completed': False})
        require(short['physical_checks']['setup']['status'] == 'not_met',
                'Short capture passed planned duration')
        return {'case_id': case, 'candidate_id': candidate,
                'construction_sha256': hashlib.sha256(construction_path.read_bytes()).hexdigest(),
                'diagnostic_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'frames': count, 'measured_m': signal['observed_continuous_approach_distance_m'],
                'observable_30_48_m_met': met,
                'short_capture_rejected': True,
                'physical_acceptance_claimed': False}


def main():
    manifest = json.loads((ROOT / 'signal-distance-draft-manifest.json').read_text())
    rows = [classify(entry, candidate) for entry in manifest['cases']
            for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3')]
    require(len(rows) == 8, 'All staged candidates need full-duration classifier proof')
    print(json.dumps({'format': 'worker-signal-distance-full-motion-fixture',
                      'proofs': rows, 'source_kind': 'synthetic software diagnostics',
                      'native_or_legal_acceptance_claimed': False}, indent=2))


if __name__ == '__main__':
    main()
