"""Independent original-source and four-camera audit for one exposure case.

Diagnostic mode tests the software join only. Native delivery additionally
requires a closed capture, owner exit and measured maneuver completion.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from endangerment_finalizer import analyze


CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('config.json', 'trace.jsonl', 'video_frames.jsonl',
           'exposed_actor_footprints.jsonl')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit(case_id, attempt, report_path, *, diagnostic_fixture=False):
    root = Path(attempt)
    config = json.loads((root / 'config.json').read_text())
    report = json.loads(Path(report_path).read_text())
    if config.get('selected_case_id') != case_id or report.get('case_id') != case_id:
        raise ValueError('Exact delivery case identity differs')
    measured = analyze(root)
    expected = report['measurements']['person_or_property_exposure']
    actual = measured['measurements']['person_or_property_exposure']
    if expected != actual:
        raise ValueError('Original exposure source hash differs from saved report')
    frame_map = rows(root / 'video_frames.jsonl')
    if len(frame_map) < 2:
        raise ValueError('Original frame interval is incomplete')
    decoded = {}
    for name in CAMERAS:
        source = root / (name + '.mkv')
        if not source.is_file():
            raise ValueError('Missing original camera source: ' + name)
        probe = subprocess.run([
            'ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
            '-show_entries', 'stream=nb_read_frames,width,height',
            '-of', 'json', str(source)], capture_output=True, text=True, check=True)
        streams = json.loads(probe.stdout).get('streams', [])
        if len(streams) != 1 or int(streams[0].get('nb_read_frames', -1)) != len(frame_map):
            raise ValueError('Original camera frame count differs: ' + name)
        full = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(source),
                               '-f', 'null', '-'], capture_output=True, text=True)
        if full.returncode:
            raise ValueError('Original camera full decode failed: ' + name)
        decoded[name] = {'sha256': sha(source), 'frames': len(frame_map),
                         'width': int(streams[0]['width']),
                         'height': int(streams[0]['height'])}
    result = json.loads((root / 'result.json').read_text())
    if result.get('case_id') != case_id or result.get('legal_acceptance_claimed') is not False:
        raise ValueError('Saved Native result identity or legal status differs')
    if diagnostic_fixture:
        if (root / 'capture-seal.json').exists() or not (root / 'fixture-provenance.json').is_file():
            raise ValueError('Diagnostic audit requires an explicitly marked unsealed fixture')
        scope = 'diagnostic software audit only'
    else:
        if not (root / 'capture-seal.json').is_file() or not (root / 'native-exit.json').is_file():
            raise ValueError('Native capture closure or owner exit is unverified')
        seal = json.loads((root / 'capture-seal.json').read_text())
        exit_receipt = json.loads((root / 'native-exit.json').read_text())
        if (seal.get('provenance_kind') != 'native' or
                seal.get('restoration', {}).get('restored') is not True or
                exit_receipt.get('event') != 'native_exit' or
                exit_receipt.get('capture_seal_sha256') != sha(root / 'capture-seal.json')):
            raise ValueError('Native capture closure or owner exit is unverified')
        if any(seal.get('sources', {}).get(name) != sha(root / name) for name in SOURCES):
            raise ValueError('Sealed original source hash differs')
        if result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met':
            raise ValueError('Physical maneuver completion is unverified')
        scope = 'source-verified Native delivery; legal judgment remains separate'
    return {'format': 'worker-exposure-delivery-audit', 'case_id': case_id,
            'scope': scope, 'original_sha256': {name: sha(root / name) for name in SOURCES},
            'cameras': decoded, 'frames': len(frame_map),
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--report', required=True)
    parser.add_argument('--diagnostic-fixture', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.attempt, args.report,
                           diagnostic_fixture=args.diagnostic_fixture), indent=2))


if __name__ == '__main__':
    main()
