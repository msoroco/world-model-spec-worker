"""Independent original controlled-access exit and comparison audits."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from controlled_access_exit import CASES, audit_comparison, measure_history, validate_site
from saved_audit import audit_saved

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def need(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def source(root, manifest, name):
    record = manifest.get('files', {}).get(name)
    need(isinstance(record, dict) and record.get('sha256'), 'original source missing: ' + name)
    relative = record.get('path')
    need(isinstance(relative, str) and relative and not Path(relative).is_absolute() and '..' not in Path(relative).parts,
         'unsafe original source path: ' + name)
    path = root / relative
    need(path.is_file() and not path.is_symlink() and path.resolve().parent == root and sha(path) == record['sha256'],
         'original source bytes changed: ' + name)
    return path


def decode_camera(path, size):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_frames',
                            '-show_entries', 'stream=nb_read_frames,width,height,r_frame_rate',
                            '-of', 'json', str(path)], capture_output=True, text=True,
                           check=True, timeout=120)
    streams = json.loads(probe.stdout).get('streams', [])
    need(len(streams) == 1, 'one original camera stream required')
    item = streams[0]
    need(item.get('nb_read_frames') == '900' and item.get('r_frame_rate') in ('20/1', '20') and
         [item.get('width'), item.get('height')] == size, 'original camera frame profile differs')
    subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path), '-f', 'null', '-'],
                   capture_output=True, check=True, timeout=180)
    return {'frames': 900, 'fps': 20, 'size': size}


def audit_attempt(attempt, case_id):
    need(case_id.startswith(ASSIGNMENT + '__'), 'wrong exact exit case')
    supplied = Path(attempt)
    need(supplied.is_dir() and not supplied.is_symlink(), 'original attempt missing')
    root = supplied.resolve()
    manifest_path = root / 'source-manifest.json'
    need(manifest_path.is_file() and not manifest_path.is_symlink(), 'original source manifest missing')
    manifest = read(manifest_path)
    need(manifest.get('case_id') == case_id and manifest.get('source_kind') == 'original_native_capture' and
         manifest.get('reviewer') and manifest.get('diagnostic_fixture') is False,
         'reviewed original source identity missing')
    site_path = source(root, manifest, 'site-context.json')
    rows_path = source(root, manifest, 'original-history.json')
    packet_path = source(root, manifest, 'saved-packet.json')
    site, rows, packet = read(site_path), read(rows_path), read(packet_path)
    short = case_id.removeprefix(ASSIGNMENT + '__')
    case = next((item for item in CASES if item.name == short), None)
    need(case is not None and site.get('source_kind') == 'original_native_capture' and site.get('reviewer'),
         'reviewed original controlled-access exit site missing')
    validate_site(site, case)
    measured = measure_history(rows, site, case)
    need(packet.get('case_id') == short and packet.get('site_sha256') == sha(site_path) and
         packet.get('original_history_sha256') == sha(rows_path), 'saved source binding changed')
    expected = dict(measured, source_history_sha256=sha(rows_path))
    need(json.dumps(packet.get('measurement'), sort_keys=True) == json.dumps(expected, sort_keys=True),
         'saved measurement differs from original history')
    audit_saved(packet)
    identity_path = root / 'capture-identity.json'
    need(identity_path.is_file() and not identity_path.is_symlink(),
         'original capture identity missing')
    identity = read(identity_path)
    need(identity.get('case_id') == case_id and identity.get('source_kind') == 'original_native_capture' and
         identity.get('diagnostic_fixture') is False and
         identity.get('source_manifest_sha256') == sha(manifest_path),
         'original capture identity or source binding missing')
    video_items = identity.get('cameras')
    need(isinstance(video_items, dict) and set(video_items) == set(CAMERAS),
         'four original camera sources required')
    decodes = {}
    for name in CAMERAS:
        path = source(root, manifest, name + '.mkv')
        need(video_items[name].get('sha256') == sha(path) and video_items[name].get('frame_count') == 900,
             'original camera source changed: ' + name)
        need(packet['videos'][name].get('sha256') == sha(path) and
             packet['videos'][name].get('decode_receipt_sha256'),
             'saved camera packet differs from decoded original: ' + name)
        decodes[name] = decode_camera(path, [1920, 1080] if name == 'overview' else [1280, 720])
    road = site['road']
    fixed = {'map_sha256': road['map_sha256'], 'site_sha256': sha(site_path),
             'camera_plan_sha256': packet.get('camera_plan_sha256'),
             'exit_route_sha256': road['route_source_sha256'],
             'approach_route_sha256': road['route_source_sha256'],
             'blueprints_sha256': site['ego_blueprint_source_sha256'] + ':' + site['approach_blueprint_source_sha256']}
    need(all(fixed.values()), 'fixed original comparison source missing')
    compare_record = {'case_id': case_id, 'frame_count': 900,
                      'original_history_sha256': sha(rows_path), **fixed,
                      'policy': case.policy, 'approaching_count': case.approaching_count,
                      'approach_headway_s': case.approach_headway_s}
    return {'format': 'c228302-independent-original-audit-v1',
            'case_id': case_id, 'source_kind': 'original_native_capture',
            'source_manifest_sha256': sha(manifest_path),
            'measurement': measured, 'comparison_record': compare_record,
            'camera_decodes': decodes, 'legal_status': 'unresolved',
            'physical_acceptance': False}


def audit_comparisons(reports):
    plan = read(HERE / 'case-plan.json')
    need(set(reports) == {item['case_id'] for item in plan['cases']},
         'five exact original reports required')
    out = []
    for comparison in plan['comparisons']:
        left_id, right_id = comparison['case_ids']
        left, right = reports[left_id], reports[right_id]
        for report, cid in ((left, left_id), (right, right_id)):
            need(report.get('format') == 'c228302-independent-original-audit-v1' and
                 report.get('case_id') == cid and report.get('source_kind') == 'original_native_capture' and
                 report.get('legal_status') == 'unresolved' and report.get('physical_acceptance') is False and
                 report.get('comparison_record', {}).get('original_history_sha256'),
                 'comparison includes nonoriginal or wrong-case audit')
        changed = comparison['deliberate_differences']
        need(len(changed) == 1, 'one declared comparison variable required')
        difference = 'policy' if changed[0] == 'policy' else changed[0]
        result = audit_comparison(left['comparison_record'], right['comparison_record'], difference)
        out.append({'comparison_id': comparison['comparison_id'],
                    'case_ids': [left_id, right_id],
                    'measured_difference': result['difference'],
                    'legal_status': 'unresolved', 'physical_acceptance': False})
    return out
