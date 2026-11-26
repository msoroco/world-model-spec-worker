"""Saved-only source-bound lamp measurements; no legal conclusion."""

import argparse
import hashlib
import json
from pathlib import Path

from lamp_direction import require
from saved_audit import audit_saved


SOURCES = ('source-packet.json', 'original-lamp-ticks.jsonl',
           'camera-source-manifest.json')


def source_hashes(attempt):
    bound = {}
    for name in SOURCES:
        path = Path(attempt) / name
        require(path.is_file(), 'Missing required source: ' + name)
        bound[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return bound


def measure_vehicle_context(report, sources):
    return {'value': {'frame_count': report['frame_count'],
                      'map_sha256': report['map_sha256'],
                      'vehicle_class_source_sha256': report['vehicle_class_source_sha256']},
            'method': 'measure_vehicle_context', 'sources': sources}


def measure_device_direction(report, sources):
    return {'value': {'directs_lamps': report['device_directs'],
                      'source_packet_sha256': report['source_packet_sha256'],
                      'route_source_sha256': report['route_source_sha256']},
            'method': 'measure_device_direction', 'sources': sources}


def measure_required_lamps(report, sources):
    return {'value': {'on_frame_counts': report['lamp_on_frame_counts'],
                      'provisions_source_sha256': report['required_lamp_provisions_source_sha256']},
            'method': 'measure_required_lamps', 'sources': sources}


def measure_time_visibility(report, sources):
    return {'value': report['statutory_context'],
            'method': 'measure_time_visibility', 'sources': sources}


def finalize(attempt, case_name):
    attempt = Path(attempt).resolve()
    sources = source_hashes(attempt)
    audit = audit_saved(attempt, case_name)
    report = json.loads((attempt / 'lamp-measurement.json').read_text())
    measurements = {
        'vehicle_context': measure_vehicle_context(report, sources),
        'device_direction': measure_device_direction(report, sources),
        'required_lamp_states': measure_required_lamps(report, sources),
        'time_visibility_context': measure_time_visibility(report, sources),
    }
    return {'format': 'worker-analysis-report', 'case_id': audit['case_id'],
            'measurements': measurements,
            'original_source_audit': audit, 'legal_verdict': None,
            'physical_acceptance_claimed': False,
            'limitations': ['Original device face, actual emitted light and legal sufficiency require independent local review.']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    config = json.loads((Path(args.attempt) / 'config.json').read_text())
    case_name = config['selected_case_id'].rsplit('__', 1)[-1]
    report = finalize(args.attempt, case_name)
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
