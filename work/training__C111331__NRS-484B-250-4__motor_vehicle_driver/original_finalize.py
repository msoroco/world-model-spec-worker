"""Finalize saved original Native rows without replaying a CARLA scene."""
import json
from pathlib import Path

from original_measure import measure
from worker_exchange.native_output import write_result


def finalize_original(attempt, output, case):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain prior original analysis; use a fresh version')
    for name in ('config.json', 'construction.json', 'road.xodr', 'raw.mkv',
                 'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                 'driver_reference.mkv', 'capture-seal.json'):
        if not (attempt / name).is_file():
            raise ValueError('Missing required original source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    if config.get('case_id') != case or construction.get('case_id') != case:
        raise ValueError('Original case identity differs')
    metric = measure(attempt)
    actors = [json.loads(x) for x in (attempt / 'native-raw-actors.jsonl').read_text().splitlines()]
    signals = [json.loads(x) for x in (attempt / 'native-signal-readback.jsonl').read_text().splitlines()]
    channels = attempt / 'channels'
    channels.mkdir()
    evidence = []
    for name in ('ego_front', 'signal_request'):
        path = channels / (name + '.jsonl')
        with path.open('x') as stream:
            for actor, signal in zip(actors, signals):
                value = (max(v[0] for v in actor['ego']['body_native_xyz_m'])
                         if name == 'ego_front' else
                         {key: head['state'] for key, head in signal['governing_heads'].items()})
                stream.write(json.dumps({'time_s': actor['time_s'], 'value': value}) + '\n')
        evidence.append({'name': name, 'unit': 'structured', 'reference': 'channels/' + path.name})
    requested_stop = case.endswith('controlled_1')
    observed_stop = bool(metric['pre_line_low_speed_frames'])
    result = {'case_id': case, 'measured_values': metric,
              'target_checks': [{'target': 'original low speed before marked line',
                                 'requested': requested_stop, 'measured': observed_stop,
                                 'method': 'measure_stop', 'tolerance': None,
                                 'matched': observed_stop == requested_stop,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': list(metric['source_sha256'])}],
              'setup_confirmed': False, 'behavior_attempted': True,
              'maneuver_completed': True,
              'termination_reason': '600 original Native frames; independent physical review pending',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': ['overview.mkv', 'approach.mkv',
                                   'reference_corner.mkv', 'driver_reference.mkv'],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'provenance_kind': 'native', 'accepted': False}
    write_result(attempt, result)
    report = {'format': 'worker-analysis-report', 'case_id': case,
              'measurements': {'inoperative_signal_stop_measurement': {
                  'method': 'measure_stop', 'value': metric,
                  'sources': metric['source_sha256']}},
              'source_complete': True, 'diagnostic_fixture': False,
              'physical_or_legal_acceptance': False}
    output.write_text(json.dumps(report, indent=2) + '\n')
    return report
