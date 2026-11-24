"""Selected saved-source measurement CLI for exact C125751 timing cases."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from saved_finalizer import finalize


def source(attempt, name):
    path = attempt/name
    if not path.is_file():
        raise ValueError('Missing required source: '+name)
    return path


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure_entry_timing(result):
    return result['measured_values']['ego_minus_other_upper_entry_s']


def measure_observed_response(result):
    return result['measured_values']['observed_ego_response']


def measure_governing_device(result):
    return result['measured_values']['governing_device_states']


def measure_crossing_context(survey):
    """Report surveyed physical context without deciding statutory applicability."""
    return {'crossing_kind': survey['crossing_kind'],
            'crossing_bounds_xy_m': survey['crossing_bounds_xy_m'],
            'approach_road_ids': survey['approach_road_ids'],
            'governing_device': survey['governing_device']}


def run(attempt, output):
    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    if output.parent != attempt or output.name != 'analysis-report.json':
        raise ValueError('analysis report must be inside the saved attempt')
    if output.exists():
        raise ValueError('retain prior analysis report')
    # Saved processing omits root source-* files. Restore the byte-identical
    # original manifest from the acquisition archive that it copies.
    manifest = attempt/'source-manifest.json'
    archived = attempt/'acquisition'/'source-manifest.json'
    if not manifest.exists() and archived.is_file():
        shutil.copy2(archived, manifest)
    if manifest.is_file() and archived.is_file() and checksum(manifest) != checksum(archived):
        raise ValueError('Original source manifest differs from acquisition archive')
    names = ('crossing-survey.json', 'source-manifest.json',
             'original-trace.json', 'original-camera-index.json',
             'video_frames.jsonl', 'raw.mkv')
    evidence = {name: checksum(source(attempt, name)) for name in names}
    result_path = finalize(attempt, attempt/'crossing-survey.json', 'raw.mkv')
    result = json.loads(result_path.read_text())
    survey = json.loads((attempt/'crossing-survey.json').read_text())
    measures = {
        'crossing_context': {'value': measure_crossing_context(survey),
                             'method': 'measure_crossing_context',
                             'sources': {name: evidence[name] for name in
                                         ('crossing-survey.json', 'source-manifest.json')}},
        'entry_time_difference_s': {'value': measure_entry_timing(result),
                                    'method': 'measure_entry_timing',
                                    'sources': {name: evidence[name] for name in
                                                ('crossing-survey.json', 'original-trace.json',
                                                 'source-manifest.json')}},
        'observed_ego_response': {'value': measure_observed_response(result),
                                  'method': 'measure_observed_response',
                                  'sources': {name: evidence[name] for name in
                                              ('crossing-survey.json', 'original-trace.json',
                                               'source-manifest.json')}},
        'governing_device_states': {'value': measure_governing_device(result),
                                    'method': 'measure_governing_device',
                                    'sources': {name: evidence[name] for name in
                                                ('crossing-survey.json', 'original-trace.json',
                                                 'source-manifest.json')}}}
    report = {'format': 'worker-analysis-report', 'case_id': result['case_id'],
              'measurements': measures, 'physical_checks': {
                  'setup_confirmed': result['setup_confirmed'],
                  'behavior_attempted': result['behavior_attempted'],
                  'maneuver_completed': result['maneuver_completed']},
              'realized_observables': result['realized_observables'],
              'analysis_complete': True, 'source_hashes': evidence,
              'physical_acceptance_claimed': False,
              'legal_acceptance_claimed': False}
    output.write_text(json.dumps(report, indent=2)+'\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.attempt, args.output), indent=2))


if __name__ == '__main__':
    main()
