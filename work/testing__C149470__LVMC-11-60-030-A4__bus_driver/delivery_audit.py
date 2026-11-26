"""Independent original-attempt and exact-comparison audit for C149470."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from reviewed_source import FIELDS, measure_reviewed, verify

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
FIXED_COMPARISON_SOURCES = ('jurisdiction', 'bus_class', 'tour_exclusion',
                            'operator', 'curb_geometry', 'bus_route', 'traffic_route')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def decode_camera(path: Path) -> dict:
    probe = subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_frames',
         '-show_entries', 'stream=nb_read_frames,width,height,r_frame_rate',
         '-of', 'json', str(path)], capture_output=True, text=True, check=True,
        timeout=120)
    streams = json.loads(probe.stdout).get('streams', [])
    if len(streams) != 1 or streams[0].get('nb_read_frames') != '900':
        raise ValueError('original camera must decode exactly 900 frames')
    if streams[0].get('r_frame_rate') not in ('20/1', '20'):
        raise ValueError('original camera must be 20 fps')
    if int(streams[0].get('width', 0)) < 640 or int(streams[0].get('height', 0)) < 360:
        raise ValueError('original camera resolution too small')
    subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path),
                    '-f', 'null', '-'], capture_output=True, check=True, timeout=180)
    return {'frames': 900, 'width': streams[0]['width'],
            'height': streams[0]['height'], 'fps': 20}


def audit_attempt(packet_path: Path, attempt: Path, case_name: str) -> dict:
    """Require a reviewed site and retained original 900-frame stream."""
    reviewed = verify(packet_path, case_name)
    attempt = Path(attempt).resolve()
    identity = load_json(attempt / 'capture-identity.json')
    expected_case = ASSIGNMENT + '__' + case_name
    if (identity.get('case_id') != expected_case or
            identity.get('source_kind') != 'original_native_capture' or
            identity.get('diagnostic_fixture') is True or
            identity.get('reviewed_site_sha256') != reviewed['site_sha256']):
        raise ValueError('original capture identity or reviewed site binding missing')
    rows_path = attempt / 'original-bus-frames.jsonl'
    if rows_path.is_symlink() or not rows_path.is_file():
        raise ValueError('retained original bus frames missing')
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
    if len(rows) != 900 or identity.get('frames_sha256') != sha(rows_path):
        raise ValueError('original frame count/hash invalid')
    camera = identity.get('cameras')
    if not isinstance(camera, dict) or set(camera) != {'overview', 'approach', 'curb_wheel', 'traffic'}:
        raise ValueError('four original camera streams missing')
    camera_hashes = {}
    camera_decodes = {}
    for name, item in camera.items():
        if not isinstance(item, dict) or item.get('frame_count') != 900:
            raise ValueError('original camera frame inventory missing: ' + name)
        path = item.get('path')
        if not isinstance(path, str) or Path(path).is_absolute() or '..' in Path(path).parts:
            raise ValueError('original camera path invalid: ' + name)
        target = attempt / path
        if target.is_symlink() or not target.is_file() or target.resolve().parent != attempt:
            raise ValueError('original camera bytes missing: ' + name)
        if sha(target) != item.get('sha256'):
            raise ValueError('original camera hash changed: ' + name)
        camera_hashes[name] = item['sha256']
        camera_decodes[name] = decode_camera(target)
    measurement = measure_reviewed(rows, packet_path, case_name)
    return {'format': 'c149470-independent-original-attempt-audit-v1',
            'case_id': expected_case, 'source_kind': 'original_native_capture',
            'reviewed_site_sha256': reviewed['site_sha256'],
            'source_hashes': reviewed['source_hashes'],
            'frames_sha256': sha(rows_path), 'camera_hashes': camera_hashes,
            'camera_decodes': camera_decodes,
            'measurement': measurement,
            'legal_status': 'unresolved', 'physical_acceptance': False}


def audit_comparisons(reports: dict[str, dict], comparison_id: str | None = None) -> list[dict]:
    """Bind every declared pair to independent original reports."""
    plan = load_json(HERE / 'case-plan.json')
    selected_comparisons = [item for item in plan['comparisons']
                            if comparison_id is None or item['comparison_id'] == comparison_id]
    if comparison_id is not None and len(selected_comparisons) != 1:
        raise ValueError('unknown exact comparison')
    expected = ({item['case_id'] for item in plan['cases']} if comparison_id is None
                else set(selected_comparisons[0]['case_ids']))
    if set(reports) != expected:
        raise ValueError('all exact original reports required')
    output = []
    for comparison in selected_comparisons:
        pair = comparison['case_ids']
        if len(pair) != 2:
            raise ValueError('comparison must bind two exact cases')
        selected = [reports[case_id] for case_id in pair]
        if any(item.get('case_id') != case_id or
               item.get('source_kind') != 'original_native_capture' or
               item.get('format') != 'c149470-independent-original-attempt-audit-v1'
               for item, case_id in zip(selected, pair)):
            raise ValueError('comparison includes nonoriginal or wrong-case audit')
        source_hashes = [item.get('source_hashes') for item in selected]
        if any(not isinstance(hashes, dict) or set(hashes) != set(FIELDS) or
               any(not isinstance(value, str) or len(value) != 64
                   for value in hashes.values()) for hashes in source_hashes):
            raise ValueError('comparison source inventory missing')
        allowed_changes = ({'bus_route'} if comparison['comparison_id'] ==
                           'parallel_engineering_grid' else
                           {'traffic_route'} if comparison['comparison_id'] ==
                           'traffic_engineering_grid' else set())
        if any(source_hashes[0][name] != source_hashes[1][name]
               for name in FIXED_COMPARISON_SOURCES if name not in allowed_changes):
            raise ValueError('comparison fixed original source changed')
        if allowed_changes and all(source_hashes[0][name] == source_hashes[1][name]
                                   for name in allowed_changes):
            raise ValueError('comparison declared route change has no original source change')
        if any(item.get('legal_status') != 'unresolved' or
               item.get('physical_acceptance') is not False or
               item.get('measurement', {}).get('source_hashes') != item['source_hashes']
               for item in selected):
            raise ValueError('comparison audit provenance or judgment changed')
        output.append({'comparison_id': comparison['comparison_id'],
                       'case_ids': pair,
                       'fixed_source_hashes': {name: source_hashes[0][name]
                                               for name in FIXED_COMPARISON_SOURCES
                                               if name not in allowed_changes},
                       'changed_source_hashes': {name: [source_hashes[0][name],
                                                       source_hashes[1][name]]
                                                 for name in allowed_changes},
                       'measured_wheel_curb_upper_bounds_m': [
                           item['measurement']['right_front_wheel_curb_upper_bound_m']
                           for item in selected],
                       'measured_bus_curb_angles_deg': [
                           item['measurement']['maximum_bus_curb_angle_deg']
                           for item in selected],
                       'measured_other_traffic_speeds_mps': [
                           item['measurement']['minimum_other_traffic_speed_mps']
                           for item in selected],
                       'legal_status': 'unresolved', 'physical_acceptance': False})
    return output
