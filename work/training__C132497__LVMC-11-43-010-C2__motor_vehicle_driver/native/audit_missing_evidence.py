"""Reject a saved diagnostic that calls missing source evidence a completed maneuver.

This checks pinned saved-processing output without changing acquisition sources.
It does not establish original motion or legal acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path


def audit(processing_path, result_path):
    processing = json.loads(Path(processing_path).read_text())
    result = json.loads(Path(result_path).read_text())
    if processing.get('result_sha256') != hashlib.sha256(Path(result_path).read_bytes()).hexdigest():
        raise ValueError('Saved-processing result source hash differs')
    if processing.get('missing_evidence') is not True:
        raise ValueError('Expected a missing-evidence saved-processing diagnostic')
    if 'native-raw-actors.jsonl' in processing.get('original_source_hashes', {}):
        raise ValueError('Actor source was present in the missing-source diagnostic')
    maneuver = result.get('physical_checks', {}).get('maneuver', {})
    if maneuver.get('status') != 'unverified' or result.get('maneuver_completed') is not False:
        raise ValueError('Missing actor evidence cannot complete a physical maneuver')
    if result.get('accepted') is True or processing.get('physical_acceptance_claimed') is True:
        raise ValueError('Missing actor evidence cannot be accepted')
    return {'missing_evidence_rejected_as_completion': True,
            'original_native_observed': False, 'accepted_recording': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--processing', required=True)
    parser.add_argument('--result', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.processing, args.result), sort_keys=True))
