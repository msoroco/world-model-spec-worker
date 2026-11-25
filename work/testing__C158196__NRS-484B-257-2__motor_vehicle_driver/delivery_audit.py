"""Independent saved-source audit for the exact signed-entrance delivery case."""

import hashlib
import json
import math
from pathlib import Path

from worker_exchange.media import audit as audit_video
from worker_exchange.measurement_contract import validate, verify_report


CAMERAS = {
    'overview': (1920, 1080),
    'approach': (1280, 720),
    'reference_corner': (1280, 720),
    'driver_reference': (1280, 720),
}
REQUIRED = ('config.json', 'entrance_inventory.json', 'crossing_history.jsonl',
            'video_frames.jsonl', 'analysis-report.json', 'result.json')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit_delivery(attempt, package, case_id, *, diagnostic_fixture=False, receipt_dir=None):
    """Require original 600-frame identity joins and independently decoded cameras."""
    attempt, package = Path(attempt), Path(package)
    manifest = json.loads((package / 'execution-manifest.json').read_text())
    entries = [item for item in manifest['cases'] if item['case_id'] == case_id]
    if len(entries) != 1:
        raise ValueError('Unselected exact delivery case')
    entry = entries[0]
    for name in REQUIRED:
        if not (attempt / name).is_file():
            raise ValueError('Missing original delivery source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    if (config.get('selected_case_id') != case_id or config.get('cell_id') != 'C158196'
            or config.get('law_id') != 'NRS-484B-257-2'
            or config.get('rate_hz') != 20 or config.get('duration_s') != 30):
        raise ValueError('Exact signed-entrance capture identity or schedule differs')
    provenance = attempt / 'acquisition-provenance.json'
    if not provenance.is_file():
        raise ValueError('Missing original acquisition provenance')
    source_kind = json.loads(provenance.read_text()).get('provenance_kind')
    if diagnostic_fixture:
        if source_kind != 'synthetic_fixture':
            raise ValueError('CPU diagnostic must identify a synthetic fixture')
    elif source_kind != 'native':
        raise ValueError('Native delivery requires native acquisition provenance')
    mapping, history = rows(attempt / 'video_frames.jsonl'), rows(attempt / 'crossing_history.jsonl')
    if len(mapping) != 600 or len(history) != 600:
        raise ValueError('Full original 600-frame duration required')
    prior_frame, prior_time = -1, -math.inf
    for index, (frame, row) in enumerate(zip(mapping, history)):
        ident, time = frame.get('carla_frame'), frame.get('time_s')
        if (frame.get('video_frame') != index or type(ident) is not int
                or ident <= prior_frame or type(time) not in (int, float)
                or not math.isfinite(time) or time <= prior_time):
            raise ValueError('Nonmonotone original frame/time map')
        if index and abs(time - prior_time - 0.05) > 1e-4:
            raise ValueError('Original frame map is not 20 Hz')
        if row.get('frame') != ident or abs(row.get('time_s', -math.inf) - time) > 1e-4:
            raise ValueError('Crossing body history has no original frame join')
        camera_frames = frame.get('camera_frames')
        if not isinstance(camera_frames, dict) or set(camera_frames) != set(CAMERAS):
            raise ValueError('Four original camera identities missing')
        if any(camera_frames[name] != ident for name in CAMERAS):
            raise ValueError('Camera sample differs from original Native frame')
        for role in ('ego', 'other'):
            body = row.get(role + '_body_vertices_xy_m')
            if (not isinstance(body, list) or len(body) < 4
                    or any(not isinstance(point, list) or len(point) != 2
                           or any(type(value) not in (int, float) or not math.isfinite(value)
                                  for value in point) for point in body)):
                raise ValueError('Missing complete original ' + role + ' body')
        prior_frame, prior_time = ident, time
    if abs(mapping[-1]['time_s'] - mapping[0]['time_s'] - 599 / 20) > 1e-4:
        raise ValueError('Original capture observation span differs')
    analysis_path = attempt / 'analysis-report.json'
    analysis = json.loads(analysis_path.read_text())
    plan = json.loads((package / 'case-plan.json').read_text())
    contract = json.loads((package / entry['measurement_contract']).read_text())
    validate(contract, plan['requirement_dispositions'],
             (package / 'saved_finalizer.py').read_text(), case_id)
    measurements = verify_report(contract, analysis, attempt)
    if len(measurements) != 4:
        raise ValueError('Four selected original-source measurements required')
    result = json.loads((attempt / 'result.json').read_text())
    if result.get('case_id') != case_id:
        raise ValueError('Physical result selects another case')
    check = result.get('physical_checks', {}).get('maneuver', {})
    if not diagnostic_fixture and (check.get('status') != 'met'
                                   or result.get('maneuver_completed') is not True):
        raise ValueError('Native delivery lacks completed physical crossing')
    if receipt_dir is not None:
        receipt_dir = Path(receipt_dir)
        receipt_dir.mkdir(parents=True, exist_ok=True)
    decodes = {}
    for index, (name, size) in enumerate(CAMERAS.items()):
        path = attempt / (name + '.mkv')
        if not path.is_file():
            raise ValueError('Missing original source camera: ' + name)
        receipt = audit_video(path, 600, mapping_sha256=sha(attempt / 'video_frames.jsonl'),
                              receipt=(receipt_dir / f'camera-{index}.json') if receipt_dir else None)
        if receipt['dimensions'] != list(size):
            raise ValueError('Source camera dimensions differ: ' + name)
        decodes[name] = {'sha256': receipt['video_sha256'], 'decoded_frames': receipt['frames']}
    return {'format': 'c158196-257-2-independent-delivery-audit', 'case_id': case_id,
            'source_kind': source_kind, 'expected_frames': 600,
            'frame_map_sha256': sha(attempt / 'video_frames.jsonl'),
            'crossing_history_sha256': sha(attempt / 'crossing_history.jsonl'),
            'analysis_sha256': sha(analysis_path),
            'verified_measurements': sorted(measurements), 'source_decodes': decodes,
            'software_audit_passed': True, 'physical_acceptance_claimed': False,
            'legal_conclusion': 'unresolved'}
