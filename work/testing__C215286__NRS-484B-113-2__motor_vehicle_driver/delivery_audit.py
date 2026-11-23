"""Exact reverse-case software delivery audit boundary; no Native acceptance."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT', str(REPO / '.runtime-work' / 'c215286-delivery-audit'))
sys.path.insert(0, str(REPO / 'runtime' / 'scenario_pipeline'))
from worker_exchange.measurement_contract import validate, verify_report
from worker_exchange.saved_processing import _closure
from worker_exchange.native_output import provenance_record
from worker_exchange.common import digest, within
from worker_exchange.candidate_constructions import select
from delivery_source_audit import audit as audit_sources
from crosswalk_reverse import analyze as measure_reverse


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_delivery(attempt, case_id):
    attempt = Path(attempt)
    source = audit_sources(attempt, case_id, diagnostic=True)
    if source['frames'] != 900 or not source['full_duration_observed']:
        raise ValueError('Full original 900-frame duration required')
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next((item for item in manifest['cases'] if item['case_id'] == case_id), None)
    if entry is None:
        raise ValueError('Unselected exact reverse case')
    construction = HERE / entry['construction']
    if sha(construction) != entry['construction_sha256']:
        raise ValueError('Exact construction source changed')
    contract = json.loads((HERE / entry['measurement_contract']).read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    code = next(item['content'] for item in json.loads(construction.read_text())['files']
                if item['path'] == entry['measurement_procedure']['entrypoint'])
    validate(contract, plan['requirement_dispositions'], code, case_id)
    report = json.loads((attempt / 'analysis-report.json').read_text())
    measured = verify_report(contract, report, attempt)
    result = json.loads((attempt / 'result.json').read_text())
    if any(result.get('physical_checks', {}).get(key, {}).get('status') != 'met'
           for key in ('setup', 'target', 'maneuver', 'attempt')):
        raise ValueError('Full-duration physical checker fixture did not complete')
    return {'format': 'worker-c215286-delivery-cpu-boundary', 'case_id': case_id,
            'source_audit_sha256': sha(HERE / 'delivery_source_audit.py'),
            'analysis_sha256': sha(attempt / 'analysis-report.json'),
            'result_sha256': sha(attempt / 'result.json'),
            'measurement_keys': sorted(measured), 'frames': 900,
            'camera_decodes': source['camera_decodes'],
            'software_audit_passed': True, 'native_source_accepted': False,
            'actual_pixels_reviewed': False, 'physical_acceptance_claimed': False,
            'legal_conclusion': 'unresolved'}


def audit_native_preflight(attempt, case_id, owner_receipt):
    """Check original Native closure and case sources before operator pixel review."""
    attempt = Path(attempt).resolve()
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next((item for item in manifest['cases'] if item['case_id'] == case_id), None)
    if entry is None:
        raise ValueError('Unselected exact reverse case')
    provenance = provenance_record(attempt)
    if provenance['provenance_kind'] != 'native' or provenance['diagnostic_fixture'] is not False:
        raise ValueError('Native non-diagnostic provenance required')
    seal = json.loads((attempt / 'capture-seal.json').read_text())
    if (seal.get('format') != 'worker-sealed-capture' or seal.get('provenance_kind') != 'native'
            or seal.get('diagnostic_fixture') is not False or seal.get('frames') != 900
            or seal.get('events') != ['capture_finished', 'encoders_closed', 'restoration_verified']
            or seal.get('source_digest') != digest(seal.get('sources', {}))):
        raise ValueError('Native capture seal or duration differs')
    required_sources = {'construction.json', 'runner.py', 'config.json', 'reverse_history.jsonl',
                        'video_frames.jsonl', 'crosswalk_context.json', 'site_packet.json',
                        'district.txt', 'geometry.txt', 'marking.txt',
                        'overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv'}
    if not required_sources <= set(seal['sources']):
        raise ValueError('Native capture seal omits required original source')
    selection_path = attempt / 'candidate-selection.json'
    selection = json.loads(selection_path.read_text()) if selection_path.is_file() else {'candidate_id': 'primary'}
    candidate_id = selection.get('candidate_id')
    _, selected, _ = select(HERE / 'execution-manifest.json', case_id, candidate_id)
    construction = HERE / selected['construction']
    if sha(construction) != selected['construction_sha256']:
        raise ValueError('Exact construction source changed')
    if selection_path.is_file() and (selection.get('case_id') != case_id
            or selection.get('construction_sha256') != selected['construction_sha256']
            or selection.get('manifest_sha256') != sha(HERE / 'execution-manifest.json')):
        raise ValueError('Native candidate selection differs from exact manifest')
    revision = seal.get('native_revision', {})
    if revision != {'construction_sha256': sha(attempt / 'construction.json'),
                    'runner_sha256': sha(attempt / 'runner.py')}:
        raise ValueError('Native capture revision differs')
    if sha(attempt / 'construction.json') != selected['construction_sha256']:
        raise ValueError('Native construction differs from exact case')
    _closure(attempt, owner_receipt, 'native', False)
    config = json.loads((attempt / 'config.json').read_text())
    if config.get('selected_case_id') != case_id:
        raise ValueError('Native config selects another case')
    measured = measure_reverse(attempt)
    if len(measured['samples']) != 900:
        raise ValueError('Native reverse history must contain 900 joined frames')
    expected_overlap = case_id.endswith('__reverse_over_crosswalk')
    if (not measured['backward_motion_observed']
            or measured['reverse_body_on_or_over_crosswalk'] is not expected_overlap):
        raise ValueError('Native original reverse-body outcome differs from selected case')
    cameras = {row['name']: row for row in config['cameras']}
    if set(cameras) != {'overview', 'approach', 'reference_corner', 'driver_reference'}:
        raise ValueError('Four Native cameras required')
    decodes = {}
    for name, camera in cameras.items():
        path = within(attempt, name + '.mkv')
        probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                                '-show_entries', 'stream=width,height,nb_read_frames', '-of', 'json', str(path)],
                               capture_output=True, text=True, check=True)
        streams = json.loads(probe.stdout)['streams']
        if (len(streams) != 1 or streams[0]['width'] != camera['width']
                or streams[0]['height'] != camera['height']
                or int(streams[0]['nb_read_frames']) != 900):
            raise ValueError('Native camera dimensions or frame count differ: ' + name)
        decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:v:0',
                                  '-f', 'framemd5', '-'], capture_output=True, check=True)
        frame_lines = [line for line in decoded.stdout.splitlines() if line and not line.startswith(b'#')]
        if len(frame_lines) != 900:
            raise ValueError('Native decoded frame count differs: ' + name)
        decodes[name] = {'source_sha256': sha(path),
                         'decoded_frames_sha256': hashlib.sha256(b'\n'.join(frame_lines)).hexdigest()}
    return {'format': 'worker-c215286-native-source-preflight', 'case_id': case_id,
            'candidate_id': candidate_id,
            'capture_seal_sha256': sha(attempt / 'capture-seal.json'),
            'owner_release_sha256': sha(owner_receipt),
            'reverse_source_hashes': measured['sources'], 'camera_decodes': decodes,
            'native_source_preflight_passed': True, 'actual_pixels_reviewed': False,
            'physical_acceptance_claimed': False, 'legal_conclusion': 'unresolved'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--mode', choices=('positive', 'negative', 'native-preflight'), required=True)
    parser.add_argument('--attempt', type=Path)
    parser.add_argument('--owner-receipt', type=Path)
    args = parser.parse_args()
    kind = 'over' if args.case.endswith('__reverse_over_crosswalk') else 'short'
    if kind == 'short' and not args.case.endswith('__reverse_stops_before_crosswalk'):
        raise ValueError('Unselected reverse case')
    attempt = REPO / '.runtime-work' / 'c215286-full-stage' / '.runtime-work' / (kind + '-primary')
    if args.mode == 'native-preflight':
        if args.attempt is None or args.owner_receipt is None:
            raise ValueError('Native preflight requires attempt and owner-release receipt')
        print(json.dumps(audit_native_preflight(args.attempt, args.case, args.owner_receipt), sort_keys=True))
    elif args.mode == 'positive':
        print(json.dumps(audit_delivery(attempt, args.case), sort_keys=True))
    else:
        with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work', prefix='c215286-audit-negative-') as tmp:
            altered = Path(tmp) / 'attempt'
            shutil.copytree(attempt, altered, copy_function=os.link)
            path = altered / 'video_frames.jsonl'
            original = path.read_bytes()
            path.unlink()
            path.write_bytes(original.replace(b'"video_frame":0', b'"video_frame":1', 1))
            audit_delivery(altered, args.case)
        raise AssertionError('Changed original video frame map was accepted')


if __name__ == '__main__':
    main()
