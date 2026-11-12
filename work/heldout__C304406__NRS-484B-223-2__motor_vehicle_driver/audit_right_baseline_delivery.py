"""Independent saved-source binding for the first exact three-lane case."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from three_lane_finalizer import PREFIX


CASE = PREFIX + 'right_baseline'
ORIGINALS = ('three_lane_frames.jsonl', 'three_lane_context.json',
             'three_lane_map_readback.json', 'trace.jsonl', 'video_frames.jsonl')


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def audit(attempt, processing):
    root = Path(attempt)
    receipt_path = Path(processing)
    receipt = json.loads(receipt_path.read_text())
    if (receipt.get('case_id') != CASE or receipt.get('passed') is not True or
            receipt.get('recorded_only') is not True or
            receipt.get('originals_preserved') is not True or
            receipt.get('missing_evidence') is not False or
            receipt.get('physical_acceptance_claimed') is not False or
            receipt.get('legal_acceptance_claimed') is not False):
        raise ValueError('Saved processing status or case identity differs')
    report_path = receipt_path.parent / 'analysis/analysis-report.json'
    result_path = receipt_path.parent / 'analysis/result.json'
    report, result = (json.loads(path.read_text()) for path in (report_path, result_path))
    if report.get('case_id') != CASE or result.get('case_id') != CASE:
        raise ValueError('Saved analysis selected another case')
    measurement = report['measurements']['three_lane_observation']
    if measurement.get('method') != 'measure_three_lane_sources':
        raise ValueError('Saved three-lane measurement method differs')
    hashes = measurement.get('sources')
    if not isinstance(hashes, dict) or set(hashes) != set(ORIGINALS):
        raise ValueError('Saved original-source inventory differs')
    for name in ORIGINALS:
        path = root / name
        if not path.is_file() or digest(path) != hashes[name]:
            raise ValueError('Saved original source differs: ' + name)
    if (result['measured_values']['three_lane_observation'] != measurement['value'] or
            result['physical_acceptance_claimed'] is not False or
            result['legal_acceptance_claimed'] is not False):
        raise ValueError('Saved result differs from measured original sources')
    observations = measurement['value']['observations']
    if (len(observations) < 2 or not all(
            row['body_lane_overlap_fraction']['right'] > 0.95
            for row in observations)):
        raise ValueError('Right-lane baseline original body occupancy missing')
    return {'format': 'worker-three-lane-delivery-source-audit',
            'case_id': CASE, 'saved_receipt_sha256': digest(receipt_path),
            'report_sha256': digest(report_path), 'result_sha256': digest(result_path),
            'original_sources': hashes, 'frames': len(observations),
            'source_binding_passed': True,
            'physical_or_legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--processing', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.attempt, args.processing)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
