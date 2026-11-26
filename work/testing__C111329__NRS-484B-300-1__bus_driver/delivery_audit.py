"""Independent original-only bus/device delivery and comparison audit."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile
from PIL import Image

from comparison_audit import audit_pair
from device_scene import signed_distance_to_stop
from package_spec import CAMERA_NAMES, CASES, HERE, case_id
from reviewed_source import FIELDS, verify


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def decode_camera(path):
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


def audit_attempt(packet_path, attempt, case_name, allow_mock=False):
    if not allow_mock and load(packet_path).get('mock_only_contract_wiring'):
        raise ValueError('mock-only source cannot satisfy original delivery')
    reviewed = verify(packet_path, case_name, load(packet_path).get('candidate_id', 'primary'))
    attempt = Path(attempt).resolve()
    identity = load(attempt / 'capture-identity.json')
    if not allow_mock and identity.get('mock_only_contract_wiring'):
        raise ValueError('mock-only capture cannot satisfy original delivery')
    if (identity.get('case_id') != case_id(case_name) or
            identity.get('source_kind') != 'original_native_capture' or
            identity.get('diagnostic_fixture') is not False or
            identity.get('reviewed_site_sha256') != sha(packet_path) or
            identity.get('candidate_id') != reviewed['candidate_id']):
        raise ValueError('original capture or reviewed site identity missing')
    rows_path = attempt / 'original-device-frames.jsonl'
    if rows_path.is_symlink() or not rows_path.is_file() or identity.get('frames_sha256') != sha(rows_path):
        raise ValueError('original bus/device frames missing or changed')
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
    if len(rows) != 900:
        raise ValueError('900 original bus/device frames required')
    site = reviewed['site']
    expected = next(row for row in CASES if row[0] == case_name)
    measured = []
    prior = None
    for index, row in enumerate(rows):
        frame, time_s = row.get('original_frame'), row.get('time_s')
        if (type(frame) is not int or type(time_s) not in (int, float) or
                prior is not None and (frame != prior[0] + 1 or not .049 <= time_s-prior[1] <= .051)):
            raise ValueError('original 20 Hz frame identity broken')
        prior = frame, time_s
        if row.get('case_id') != case_id(case_name) or row.get('device_id') != site['device_id'] or \
                row.get('facing_approach_id') != site['ego_approach_id'] or \
                row.get('bus_blueprint_id') != site['bus_blueprint_id'] or row.get('aspect') != expected[1]:
            raise ValueError('original bus/device identity or aspect differs')
        if any(row.get(name + '_source_sha256') != reviewed['source_hashes'][name] for name in FIELDS):
            raise ValueError('original frame source differs from reviewed packet')
        if not row.get('placement_source') or not row.get('nrs_307_context_source') or \
                'police_direction_source' not in row:
            raise ValueError('original placement, officer or 307 source context missing')
        if expected[3] == 'proceed' and (row.get('police_direction') != 'proceed' or
                                         not row['police_direction_source']):
            raise ValueError('contemporaneous original police direction missing')
        measured.append(signed_distance_to_stop(site, row['bus_front_xy']))
    if measured[0] <= 0 or any(value < 0 for value in measured) != expected[4]:
        raise ValueError('original bus line conduct differs from selected case')
    map_path = attempt / 'camera-frame-map.jsonl'
    if map_path.is_symlink() or not map_path.is_file() or identity.get('camera_frame_map_sha256') != sha(map_path):
        raise ValueError('original camera frame map missing or changed')
    frame_map = [json.loads(line) for line in map_path.read_text().splitlines()]
    archives = identity.get('camera_archives')
    if len(frame_map) != 900 or not isinstance(archives, dict) or set(archives) != set(CAMERA_NAMES):
        raise ValueError('four original camera frame maps or archives missing')
    for row, item in zip(rows, frame_map):
        if (item.get('original_frame') != row['original_frame'] or
                item.get('time_s') != row['time_s'] or
                set(item.get('camera_png_sha256', {})) != set(CAMERA_NAMES)):
            raise ValueError('original camera and bus/device frame join invalid')
    archive_hashes = {}
    for name, item in archives.items():
        relative = item.get('path')
        if not isinstance(relative, str) or Path(relative).name != relative:
            raise ValueError('original pixel archive path invalid')
        path = attempt / relative
        if path.is_symlink() or not path.is_file() or sha(path) != item.get('sha256'):
            raise ValueError('original pixel archive missing or changed')
        with zipfile.ZipFile(path) as archive:
            expected_entries = [f'{index:04d}-{row["original_frame"]}.png'
                                for index, row in enumerate(rows)]
            if archive.namelist() != expected_entries:
                raise ValueError('original camera pixel frame inventory differs')
            for index, entry in enumerate(expected_entries):
                raw = archive.read(entry)
                if not raw.startswith(b'\x89PNG\r\n\x1a\n') or \
                        hashlib.sha256(raw).hexdigest() != frame_map[index]['camera_png_sha256'][name]:
                    raise ValueError('original camera pixel/frame hash differs')
                try:
                    Image.open(io.BytesIO(raw)).verify()
                except Exception as error:
                    raise ValueError('original camera pixel PNG invalid') from error
        archive_hashes[name] = item['sha256']
    streams = identity.get('cameras')
    if not isinstance(streams, dict) or set(streams) != set(CAMERA_NAMES):
        raise ValueError('four original camera streams missing')
    camera_hashes, decodes = {}, {}
    for name, item in streams.items():
        relative = item.get('path')
        if item.get('frame_count') != 900 or not isinstance(relative, str) or Path(relative).name != relative:
            raise ValueError('original camera stream inventory invalid')
        path = attempt / relative
        if path.is_symlink() or not path.is_file() or sha(path) != item.get('sha256'):
            raise ValueError('original camera stream missing or changed')
        camera_hashes[name] = item['sha256']
        decodes[name] = decode_camera(path)
    return {'format': 'c111329-independent-original-attempt-audit-v1',
            'case_id': case_id(case_name), 'source_kind': 'original_native_capture',
            'mock_only_contract_wiring': allow_mock,
            'candidate_id': reviewed['candidate_id'],
            'reviewed_site_sha256': sha(packet_path),
            'site_identity': {'bus_blueprint_id': site['bus_blueprint_id'],
                              'device_id': site['device_id'],
                              'facing_approach_id': site['ego_approach_id']},
            'source_hashes': reviewed['source_hashes'],
            'frames_sha256': sha(rows_path),
            'camera_frame_map_sha256': sha(map_path),
            'camera_archive_hashes': archive_hashes,
            'camera_hashes': camera_hashes, 'camera_decodes': decodes,
            'measurement': {'line_entry': any(value < 0 for value in measured),
                            'aspect': expected[1],
                            'first_line_entry_frame': next((row['original_frame'] for row, value in zip(rows, measured) if value < 0), None),
                            'police_direction': expected[3],
                            'police_direction_source': rows[0]['police_direction_source'],
                            'placement_source': rows[0]['placement_source'],
                            'nrs_307_context_source': rows[0]['nrs_307_context_source'],
                            'first_signed_distance_m': measured[0],
                            'last_signed_distance_m': measured[-1]},
            'legal_status': 'unresolved', 'physical_acceptance': False}


def audit_comparisons(reports, comparison_id=None, allow_mock=False):
    plan = load(HERE / 'case-plan.json')
    selected = [row for row in plan['comparisons']
                if comparison_id is None or row['comparison_id'] == comparison_id]
    if comparison_id is not None and len(selected) != 1:
        raise ValueError('unknown exact comparison')
    required = ({row['case_id'] for row in plan['cases']} if comparison_id is None
                else set(selected[0]['case_ids']))
    if set(reports) != required:
        raise ValueError('all exact original reports required')
    output = []
    for item in selected:
        left, right = (reports[case] for case in item['case_ids'])
        if any(report.get('source_kind') != 'original_native_capture' or
               (report.get('mock_only_contract_wiring') and not allow_mock) or
               report.get('format') != 'c111329-independent-original-attempt-audit-v1' or
               report.get('legal_status') != 'unresolved' or
               report.get('physical_acceptance') is not False
               for report in (left, right)):
            raise ValueError('comparison includes nonoriginal or accepted legal report')
        if left['case_id'] != item['case_ids'][0] or right['case_id'] != item['case_ids'][1]:
            raise ValueError('comparison exact case identity differs')
        summaries = []
        for report in (left, right):
            measurement = report['measurement']
            hashes = report['source_hashes']
            if set(hashes) != set(FIELDS) or any(len(value) != 64 for value in hashes.values()):
                raise ValueError('comparison reviewed source inventory missing')
            summaries.append({**{key + '_sha256': hashes[key] for key in FIELDS},
                              'bus_blueprint_id': report['site_identity']['bus_blueprint_id'],
                              'camera_profile': 'overview1080-capability', 'duration_s': 45,
                              'device_id': report['site_identity']['device_id'],
                              'facing_approach_id': report['site_identity']['facing_approach_id'],
                              'aspect': measurement['aspect'],
                              'line_entry': measurement['line_entry'],
                              'police_direction': measurement['police_direction'],
                              'police_direction_source': measurement['police_direction_source'],
                              'placement_source': measurement['placement_source'],
                              'nrs_307_context_source': measurement['nrs_307_context_source'],
                              'original_trace_sha256': report['frames_sha256']})
        difference = {'red_instruction_conduct': 'bus_line_behavior',
                      'contemporaneous_police_direction': 'police_direction',
                      'device_instruction': 'device_instruction'}[item['comparison_id']]
        proof = audit_pair(*summaries, difference)
        output.append({'comparison_id': item['comparison_id'],
                       'case_ids': item['case_ids'], 'source_kind': 'original_native_capture',
                       'fixed_source_hashes': left['source_hashes'],
                       'comparison_variable': difference,
                       'source_complete': proof['accepted_as_source_complete'],
                       'legal_status': 'unresolved', 'physical_acceptance': False})
    return output
