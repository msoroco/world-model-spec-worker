"""Recorded-only bridge speed measurement and source channel extraction."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from bridge_speed_measure import MPS_TO_MPH
from finalize_bridge import finalize as bridge_finalize


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bridge_speed(finding):
    return {'declared_maximum_mph': finding['declared_maximum_mph'],
            'max_observed_structure_speed_mph': finding['max_observed_structure_speed_mph'],
            'structure_frames_above_declared_maximum': finding['structure_frames_above_declared_maximum']}


def run(attempt, output):
    attempt, output = Path(attempt), Path(output)
    required = ('original_bridge_survey.json', 'bridge-native.jsonl',
                'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl')
    for name in required:
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    if output.exists():
        raise ValueError('Choose a fresh analysis report')
    config = json.loads((attempt / 'config.json').read_text())
    case = config['case_id']
    diagnostic = os.environ.get('SCENARIO_DIAGNOSTIC_FIXTURE') == '1'
    finding = bridge_finalize(attempt, attempt / 'bridge-findings.json', diagnostic)
    survey = json.loads((attempt / 'original_bridge_survey.json').read_text())
    trace = [json.loads(row) for row in (attempt / 'bridge-native.jsonl').read_text().splitlines() if row]
    channels = attempt / 'channels'
    channels.mkdir(exist_ok=False)
    names = [item['name'] for item in config['recording_description']['channels']]
    expected = ['st.elevated_structure', 'dev.speed_limit_sign', 'dev.position',
                'dev.governs', 'kin.speed', 'rel.occupies', 'drv.approaching']
    if names != expected:
        raise ValueError('Selected source channels changed')
    evidence = []
    for name in names:
        path = channels / (name + '.jsonl')
        with path.open('x') as stream:
            for row in trace:
                if name == 'st.elevated_structure':
                    value = {'structure_source_id': survey['structure_source_id'],
                             'on_structure': row['on_structure_verified']}
                elif name == 'dev.speed_limit_sign':
                    value = [{'source_id': sign['source_id'],
                              'maximum_mph': sign['maximum_mph']} for sign in survey['signs']]
                elif name == 'dev.position':
                    value = [sign.get('position_xyz_m') for sign in survey['signs']]
                elif name == 'dev.governs':
                    value = [sign['governed_approach_source_id'] for sign in survey['signs']]
                elif name == 'kin.speed':
                    value = (sum(v * v for v in row['velocity_xyz_mps']) ** 0.5) * MPS_TO_MPH
                elif name == 'rel.occupies':
                    value = row['on_structure_verified']
                else:
                    value = {'position_xyz_m': row['position_xyz_m'],
                             'governing_sign_sources': [sign['governed_approach_source_id']
                                                        for sign in survey['signs']]}
                stream.write(json.dumps({'time_s': row['t_s'], 'value': value}) + '\n')
        evidence.append({'name': name, 'unit': 'structured',
                         'reference': 'channels/' + path.name})
    from worker_exchange.native_output import physical_result, write_result
    result = {'case_id': case, 'measured_values': finding,
              'target_checks': [{'target': 'measured bridge speed relative to original DOT declaration',
                                 'requested': config['requested_offset_from_declared_maximum_mph'],
                                 'measured': bridge_speed(finding),
                                 'method': 'original 20 Hz Native velocity during surveyed structure occupancy',
                                 'tolerance': 'sampling interval 0.05 s; original source and legal review remain pending',
                                 'matched': False, 'physical_cause_confirmed': False,
                                 'cause_evidence': list(required)}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False, 'accepted': False,
              'termination_reason': 'Saved source measurement complete; physical and legal review pending',
              'physical_failure_flags': ['original_source_and_physical_review_pending'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in
                                   ('overview', 'approach', 'reference_corner', 'driver_reference', 'raw')],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    write_result(attempt, physical_result(attempt, result))
    sources = {name: sha(attempt / name) for name in required}
    report = {'format': 'worker-analysis-report', 'case_id': case,
              'measurements': {'bridge_speed': {'method': 'bridge_speed',
                                               'value': bridge_speed(finding),
                                               'sources': sources}},
              'source_complete': True, 'physical_or_legal_acceptance': False}
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.attempt, args.output), sort_keys=True))
