"""Independent original-source and authority audit for selected hose deliveries."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE_NAMES = ('road.xodr', 'actor-sources.jsonl', 'camera-frames.jsonl',
                'hose-source.json', 'department-presence.json', 'communication-setup.json',
                'way-review.json', 'hose-review.json', 'command-review.json',
                'video_frames.jsonl', 'reference_corner.mkv')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing source: ' + path.name)
    return json.loads(path.read_text())


def count(path):
    return len(Path(path).read_text().splitlines())


def audit(case, candidate, attempt, processing, diagnostic, omit_source=None):
    manifest = read(HERE / 'execution-manifest.json')
    entry = next((e for e in manifest['cases'] if e['case_id'] == case), None)
    if entry is None:
        raise ValueError('Unknown selected case')
    selected = entry if candidate == 'primary' else next((e for e in entry['candidates'] if e['id'] == candidate), None)
    if selected is None:
        raise ValueError('Unknown selected candidate')
    saved = read(processing)
    if (saved.get('passed') is not True or saved.get('recorded_only') is not True or
            saved.get('case_id') != case or saved.get('candidate_id') != candidate or
            saved.get('native_revision', {}).get('construction_sha256') != selected['construction_sha256'] or
            saved.get('originals_preserved') is not True or
            saved.get('timestamp_joins', {}).get('frames') != 600 or
            saved.get('final_video_checks', {}).get('frames') != 600):
        raise ValueError('Selected saved processing or full-frame decode differs')
    stage = Path(saved['analysis_directory']).resolve()
    hashes = {}
    for name in SOURCE_NAMES:
        if name == omit_source:
            raise ValueError('Missing source: ' + name)
        path = stage / name
        if not path.is_file():
            raise ValueError('Missing source: ' + name)
        hashes[name] = sha(path)
    if count(stage / 'actor-sources.jsonl') != 600 or count(stage / 'camera-frames.jsonl') != 2400:
        raise ValueError('Original actor or camera source frames incomplete')
    if count(stage / 'trace.jsonl') != 600 or count(stage / 'video_frames.jsonl') != 600:
        raise ValueError('Original trace or frame map incomplete')
    result = read(stage / 'result.json')
    report = read(stage / 'analysis-report.json')
    if result.get('case_id') != case or result.get('trace_reference') != 'trace.jsonl':
        raise ValueError('Original result or trace reference differs')
    if set(result.get('video_references', [])) != {n + '.mkv' for n in CAMERAS}:
        raise ValueError('Original four-camera references differ')
    for name in CAMERAS:
        if not (stage / (name + '.mkv')).is_file():
            raise ValueError('Missing source: ' + name + '.mkv')
    measurement = report.get('measurements', {}).get('source_bound_hose_passage', {})
    if (measurement.get('method') != 'measured' or
            any(measurement.get('sources', {}).get(name) != hashes[name] for name in SOURCE_NAMES)):
        raise ValueError('Source-bound hose measurement differs')
    value = measurement.get('value', {})
    if value.get('frames') != 600 or type(value.get('driven_hose_overlap_frames')) is not int:
        raise ValueError('Original hose passage measurement differs')
    way = read(stage / 'way-review.json')
    hose = read(stage / 'hose-review.json')
    command = read(stage / 'command-review.json')
    presence = read(stage / 'department-presence.json')
    communication = read(stage / 'communication-setup.json')
    if (way.get('road_sha256') != hashes['road.xodr'] or not way.get('road_access_basis') or
            way.get('hose_on_actual_route') is not True or
            hose.get('hose_source_sha256') != hashes['hose-source.json'] or
            hose.get('department_presence_sha256') != hashes['department-presence.json'] or
            'firetruck' not in presence.get('fire_apparatus_blueprint', '') or
            presence.get('command_role_actor_id') != communication.get('official_actor_id') or
            hose.get('department_affiliation') is not True or
            hose.get('fire_use_purpose') not in ('fire', 'alarm', 'practice_run') or
            not hose.get('protection_arrangements') or
            command.get('actor_sha256') != hashes['actor-sources.jsonl'] or
            command.get('communication_setup_sha256') != hashes['communication-setup.json'] or
            command.get('case_id') != case or not command.get('official_identity') or
            command.get('command_status') != 'official_in_command' or
            command.get('vehicle_class') != 'ordinary_motor_vehicle' or
            command.get('human_driver') is not True or
            len({way.get('source'), hose.get('source'), command.get('source')}) != 3):
        raise ValueError('Independent way, hose, driver or command source join differs')
    if command.get('communication_status') == 'documented_consent':
        if command.get('permission') != 'drive_over_hose' or command.get('scope_case_id') != case or not command.get('timing_source') or communication.get('communication_setup') != 'authored_radio_permission':
            raise ValueError('Consent content, timing or scope source differs')
    elif command.get('communication_status') != 'explicit_none' or command.get('monitoring_window') != 'full_original_capture' or communication.get('communication_setup') != 'explicit_no_communication':
        raise ValueError('Explicit no-communication source differs')
    if diagnostic:
        receipt = read(Path(attempt) / 'compatibility.json')
        if (receipt.get('passed') is not True or receipt.get('case_id') != case or
                receipt.get('candidate_id') != candidate or
                receipt.get('construction_sha256') != selected['construction_sha256']):
            raise ValueError('Diagnostic compatibility identity differs')
    else:
        provenance = read(Path(attempt) / 'acquisition-provenance.json')
        if provenance.get('provenance_kind') != 'native' or provenance.get('diagnostic_fixture') is True:
            raise ValueError('Original Native acquisition required')
        for review in (way, hose, command):
            if review.get('review_status') != 'independently_reviewed' or not review.get('reviewer'):
                raise ValueError('Independent original review incomplete')
        if hose.get('pixel_sha256') != hashes['reference_corner.mkv']:
            raise ValueError('Original hose pixel review differs')
        pixel = read(stage / 'hose-pixel-review.json')
        if pixel.get('review_status') != 'independently_reviewed' or pixel.get('frame_map_sha256') != hashes['video_frames.jsonl'] or pixel.get('source_video_sha256') != hashes['reference_corner.mkv']:
            raise ValueError('Independent original hose pixel review incomplete')
        physical = result.get('physical_checks', {}).get('maneuver', {})
        if physical.get('status') != 'met' or result.get('maneuver_completed') is not True:
            raise ValueError('Original physical travel completion unverified')
    return {'format': 'c230231-independent-delivery-audit-v1', 'case_id': case,
            'candidate_id': candidate, 'construction_sha256': selected['construction_sha256'],
            'saved_processing_sha256': sha(processing), 'original_source_sha256': hashes,
            'diagnostic_only': diagnostic, 'physical_or_legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', default='primary')
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--processing', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--omit-source', choices=SOURCE_NAMES)
    args = parser.parse_args()
    if args.omit_source and not args.diagnostic:
        raise ValueError('Source omission is diagnostic only')
    receipt = audit(args.case, args.candidate, args.attempt, args.processing,
                    args.diagnostic, args.omit_source)
    if args.output.exists():
        raise ValueError('Retain previous delivery audit result')
    args.output.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'case_id': args.case, 'diagnostic_only': args.diagnostic}))


if __name__ == '__main__':
    main()
