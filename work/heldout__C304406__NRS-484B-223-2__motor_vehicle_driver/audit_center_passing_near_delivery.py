"""Independent source binding for the synthetic passing-clear saved attempt."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from three_lane_finalizer import PREFIX

CASE = PREFIX + 'center_passing_near_traffic'
SOURCES = ('passing_frames.jsonl', 'three_lane_frames.jsonl',
           'three_lane_context.json', 'three_lane_map_readback.json',
           'trace.jsonl', 'video_frames.jsonl')


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def audit(attempt, processing):
    attempt, processing = Path(attempt), Path(processing)
    receipt = json.loads(processing.read_text())
    if (receipt.get('case_id') != CASE or receipt.get('passed') is not True or
            receipt.get('recorded_only') is not True or
            receipt.get('originals_preserved') is not True or
            receipt.get('missing_evidence') is not False or
            receipt.get('physical_acceptance_claimed') is not False or
            receipt.get('legal_acceptance_claimed') is not False):
        raise ValueError('Saved passing receipt status differs')
    report = json.loads((processing.parent / 'analysis/analysis-report.json').read_text())
    result = json.loads((processing.parent / 'analysis/result.json').read_text())
    measurement = report.get('measurements', {}).get('passing_observation')
    if (report.get('case_id') != CASE or result.get('case_id') != CASE or
            not isinstance(measurement, dict) or
            result.get('measured_values', {}).get('passing_observation') != measurement.get('value')):
        raise ValueError('Saved passing measurement differs')
    hashes = measurement.get('sources')
    if not isinstance(hashes, dict) or set(hashes) != set(SOURCES):
        raise ValueError('Saved passing source inventory differs')
    for name in SOURCES:
        path = attempt / name
        if not path.is_file() or digest(path) != hashes[name]:
            raise ValueError('Saved passing original source differs: ' + name)
    observations = measurement['value']['observations']
    if (len(observations) < 2 or not all(
            row['target_right_lane_fraction'] > .75 and
            row['center_engineering_interval_clear'] is False and bool(row['center_blocked_actors'])
            for row in observations)):
        raise ValueError('Passing target or near center traffic body missing')
    if (result.get('physical_acceptance_claimed') is not False or
            result.get('legal_acceptance_claimed') is not False):
        raise ValueError('Passing source audit cannot claim physical or legal acceptance')
    return {'format':'worker-passing-source-audit','case_id':CASE,
            'processing_sha256':digest(processing),'original_sources':hashes,
            'frames':len(observations),'initial_gap_m':observations[0]['ego_target_longitudinal_gap_m'],
            'final_gap_m':observations[-1]['ego_target_longitudinal_gap_m'],
            'source_binding_passed':True,'physical_or_legal_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--processing',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    result=audit(args.attempt,args.processing)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':
    main()
