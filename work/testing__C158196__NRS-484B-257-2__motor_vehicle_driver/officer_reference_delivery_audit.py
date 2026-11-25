"""Independent original-source audit for the six officer/reference alternatives."""

import hashlib
import json
import math
import os
from pathlib import Path


CAMERAS = {'overview': (1920, 1080), 'approach': (1280, 720),
           'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}
REQUIRED = ('config.json', 'officer-reference-capture.json',
            'officer_reference_history.jsonl', 'trace.jsonl',
            'capture/evidence.jsonl', 'video_frames.jsonl',
            'analysis-report.json', 'result.json')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()
            if line.strip()]


def audit_delivery(attempt, package, case_id, *, diagnostic_fixture=False,
                   receipt_dir=None):
    attempt, package = Path(attempt).resolve(), Path(package).resolve()
    manifest = json.loads((package / 'officer-reference-diagnostic-manifest.json').read_text())
    entries = [item for item in manifest['cases'] if item['case_id'] == case_id]
    if len(entries) != 1:
        raise ValueError('Unselected exact officer/reference case')
    entry = entries[0]
    construction = package / entry['construction']
    if sha(construction) != entry['construction_sha256']:
        raise ValueError('Exact officer/reference construction changed')
    for name in REQUIRED:
        if not (attempt / name).is_file():
            raise ValueError('Missing original delivery source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    if (config.get('selected_case_id') != case_id or
            (config.get('law_id'), config.get('cell_id'), config.get('actor')) !=
            ('NRS-484B-257-2', 'C158196', 'motor_vehicle_driver') or
            config.get('rate_hz') != 20 or config.get('duration_s') != 30):
        raise ValueError('Exact officer/reference capture identity differs')
    capture = json.loads((attempt / 'officer-reference-capture.json').read_text())
    mapping = rows(attempt / 'video_frames.jsonl')
    history = rows(attempt / 'officer_reference_history.jsonl')
    trace = rows(attempt / 'trace.jsonl')
    evidence = rows(attempt / 'capture/evidence.jsonl')
    if (capture.get('case_id') != case_id or capture.get('frame_count') != 600 or
            not all(len(v) == 600 for v in
                    (capture.get('rows', []), mapping, history, trace, evidence))):
        raise ValueError('Full original 600-frame delivery duration required')
    source_rows = capture['rows']
    prior_frame, prior_time = -1, -math.inf
    for index, (source, frame, motion, trace_row, event) in enumerate(
            zip(source_rows, mapping, history, trace, evidence)):
        ident, time = source.get('carla_frame'), source.get('time_s')
        if (source.get('frame_index') != index or type(ident) is not int or
                ident <= prior_frame or type(time) not in (int, float) or
                not math.isfinite(time) or time <= prior_time or
                (index and abs(time - prior_time - 0.05) > 1e-4) or
                frame.get('video_frame') != index or frame.get('carla_frame') != ident or
                abs(frame.get('time_s', -math.inf) - time) > 1e-4 or
                frame.get('camera_frames') != {name: ident for name in CAMERAS} or
                motion.get('frame') != ident or trace_row.get('frame') != ident or
                event.get('original_frame') != ident or
                motion.get('ego_body_vertices_xy_m') !=
                source.get('ego_body_vertices_xy_m') or
                motion.get('ego_speed_mps') != source.get('ego_speed_mps')):
            raise ValueError('Original officer/reference source frame join differs')
        prior_frame, prior_time = ident, time
    if abs(prior_time - source_rows[0]['time_s'] - 599 / 20) > 1e-4:
        raise ValueError('Original officer/reference time span differs')
    provenance = json.loads((attempt / 'capture/manifest.json').read_text())
    source_kind = provenance.get('acquisition')
    if diagnostic_fixture:
        if source_kind != 'synthetic_diagnostic':
            raise ValueError('CPU audit requires synthetic provenance')
    elif source_kind != 'native':
        raise ValueError('Native delivery requires Native acquisition provenance')
    analysis = json.loads((attempt / 'analysis-report.json').read_text())
    if analysis.get('case_id') != case_id or not analysis.get('analysis_complete'):
        raise ValueError('Exact saved analysis missing')
    for source, digest in analysis.get('source_sha256', {}).items():
        if sha(attempt / source) != digest:
            raise ValueError('Saved analysis original source changed: ' + source)
    if not os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT'):
        raise ValueError('SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work required')
    from worker_exchange.media import audit as audit_video
    from worker_exchange.measurement_contract import validate, verify_report
    contract = json.loads((package / entry['measurement_contract']).read_text())
    plan = json.loads((package / 'case-plan.json').read_text())
    validate(contract, plan['requirement_dispositions'],
             (package / 'officer_reference_saved_finalizer.py').read_text(), case_id)
    measured = verify_report(contract, analysis, attempt)
    result = json.loads((attempt / 'result.json').read_text())
    if result.get('case_id') != case_id:
        raise ValueError('Physical result selects another case')
    if not diagnostic_fixture and (
            result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met'
            or result.get('maneuver_completed') is not True):
        raise ValueError('Native delivery lacks completed physical motion')
    if receipt_dir is not None:
        receipt_dir = Path(receipt_dir)
        receipt_dir.mkdir(parents=True, exist_ok=True)
    decodes = {}
    for index, (name, size) in enumerate(CAMERAS.items()):
        path = attempt / (name + '.mkv')
        if not path.is_file():
            raise ValueError('Missing original source camera: ' + name)
        decoded = audit_video(path, 600,
                              mapping_sha256=sha(attempt / 'video_frames.jsonl'),
                              receipt=(receipt_dir / f'camera-{index}.json')
                              if receipt_dir else None)
        if decoded['dimensions'] != list(size):
            raise ValueError('Original source camera dimensions differ: ' + name)
        decodes[name] = {'sha256': decoded['video_sha256'],
                         'decoded_frames': decoded['frames']}
    return {'format': 'c158196-officer-reference-independent-delivery-audit',
            'case_id': case_id, 'source_kind': source_kind,
            'construction_sha256': entry['construction_sha256'],
            'frame_map_sha256': sha(attempt / 'video_frames.jsonl'),
            'capture_sha256': sha(attempt / 'officer-reference-capture.json'),
            'analysis_sha256': sha(attempt / 'analysis-report.json'),
            'verified_measurements': sorted(measured), 'source_decodes': decodes,
            'software_audit_passed': True, 'physical_acceptance_claimed': False,
            'legal_conclusion': 'unresolved'}
