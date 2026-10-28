"""Finalize measured native evidence without resolving physical or legal judgments."""
import json
from pathlib import Path
from worker_exchange.native_output import write_result


def finalize(attempt, report):
    attempt = Path(attempt)
    cfg = json.loads((attempt / 'config.json').read_text())
    case = cfg['case']
    trace = [json.loads(row) for row in (attempt / 'trace.jsonl').read_text().splitlines()]
    fields = {'commanded_speed_mps': 'realized_mean_speed_mps',
              'commanded_release_delay_s': 'entry_time_difference_s',
              'commanded_signal_distance': 'measured_traveled_distance_m'}
    checks = []
    for name, assignment in case['variable_assignments'].items():
        if assignment.get('kind') not in ('controller', 'world_setup'):
            continue
        requested = assignment.get('value')
        source = fields.get(name)
        measured = report.get(source) if source else None
        method = ('original source analysis: ' + source) if source else 'original source analysis did not identify a comparable physical value'
        if measured is None:
            measured = 'unresolved_from_original_acquisition'
        tolerance = 0.1 if isinstance(requested, (int, float)) and not isinstance(requested, bool) else 0
        matched = isinstance(requested, (int, float)) and isinstance(measured, (int, float)) and abs(requested-measured) <= tolerance
        checks.append({'target': name, 'requested': requested, 'measured': measured,
                       'method': method, 'tolerance': tolerance, 'matched': bool(matched),
                       'physical_cause_confirmed': False, 'cause_evidence': 'analysis-report.json'})
    if not checks:
        checks.append({'target': 'recorded_frame_count', 'requested': 1,
                       'measured': len(trace), 'method': 'count original trace rows',
                       'tolerance': 0, 'matched': len(trace) == 1,
                       'physical_cause_confirmed': False, 'cause_evidence': 'trace.jsonl'})
    evidence = [{'name': ch['name'], 'unit': ch['unit'],
                 'reference': 'channels/' + ch['name'] + '.jsonl'}
                for ch in case['recording_description']['channels']]
    evidence += [{'name': ctx['name'], 'unit': ctx['unit'], 'reference': 'context.json'}
                 for ctx in case['recording_description']['context_inputs']]
    realized = {}
    for axis in case.get('sweep_measurements', []):
        name = axis['observable']
        value = report.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            definition = axis['measurement']
            summary = {'unit': axis['unit'], 'method': definition['method'],
                       'time_window': definition['time_window'], 'statistic': definition['statistic'],
                       'reference': 'realized-sweep.json', 'value': value}
            realized[name] = summary
            evidence.append({'name': name, 'unit': axis['unit'], 'reference': 'realized-sweep.json'})
    if realized:
        (attempt / 'realized-sweep.json').write_text(json.dumps({k:v['value'] for k,v in realized.items()}, indent=2) + '\n')
    videos = [p.name for p in sorted(attempt.glob('view*.mkv'))]
    if not videos and (attempt/'fixture-provenance.json').is_file() and (attempt/'raw.mkv').is_file():
        videos = ['raw.mkv']
    result = {'case_id': case['case_id'], 'measured_values': report,
              'target_checks': checks, 'setup_confirmed': False,
              'behavior_attempted': len(trace) > 3, 'maneuver_completed': False,
              'termination_reason': 'diagnostic subset only' if len(trace) <= 3 else 'physical setup and completion pending independent review',
              'physical_failure_flags': {'physical_cause_unverified': True},
              'trace_reference': 'trace.jsonl', 'video_references': videos,
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': case['recording_description'],
              'recording_evidence': evidence, 'realized_observables': realized}
    write_result(attempt, result)
    return result
