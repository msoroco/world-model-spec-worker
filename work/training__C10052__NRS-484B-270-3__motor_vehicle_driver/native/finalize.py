"""Saved-only C10052 diagnostic; occupancy and requested context remain distinct."""
import argparse
import json
from pathlib import Path

from measure_facility import measure


def facility_stop_observation(attempt):
    attempt = Path(attempt)
    result = measure(attempt/'native_samples.jsonl', attempt/'road_geometry.json',
                     attempt/'exception_context.json')
    return {'method': 'facility_stop_observation',
            'value': {'max_stopped_overlap_m2': result['max_stopped_overlap_m2'],
                      'mean_stopped_overlap_m2': result['mean_stopped_overlap_m2'],
                      'stop_duration_s': result['stop_duration_s'],
                      'native_facility_design_verified': result['native_facility_design_verified'],
                      'observed_exception_status': result['observed_exception_status'],
                      'yield_duty_measured': result['yield_duty_measured'],
                      'legal_verdict_claimed': False},
            'sources': result['source_sha256']}


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists():
        raise ValueError('Retain original finalization; use a fresh output')
    observation = facility_stop_observation(attempt)
    report = {'format': 'c10052-synthetic-saved-occupancy-diagnostic-v1',
              'measurements': {'facility_stop_observation': observation},
              'scope': 'saved synthetic original-sample diagnostic; no Native designation, exception finding, yield finding or legal verdict'}
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))


if __name__ == '__main__':
    main()
