"""Independent source audit for reverse-crosswalk attempts; CPU diagnostics only."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit(attempt, case_id, diagnostic=True):
    attempt = Path(attempt).resolve()
    manifest = read(HERE / 'execution-manifest.json')
    entry = next((row for row in manifest['cases'] if row['case_id'] == case_id), None)
    if entry is None:
        raise ValueError('Unknown exact reverse case')
    config, result = read(attempt / 'config.json'), read(attempt / 'result.json')
    receipt, analysis = read(attempt / 'compatibility.json'), read(attempt / 'analysis-report.json')
    if (config.get('selected_case_id') != case_id or result.get('case_id') != case_id
            or analysis.get('case_id') != case_id or receipt.get('case_id') != case_id):
        raise ValueError('Exact case identity differs')
    if (receipt.get('passed') is not True or receipt.get('candidate_id') != 'primary'
            or receipt.get('construction_sha256') != entry['construction_sha256']):
        raise ValueError('Current primary compatibility receipt differs')
    if result.get('physical_acceptance_claimed') is not False or result.get('provenance_kind') != 'synthetic_fixture':
        raise ValueError('Diagnostic provenance or acceptance claim differs')
    if not diagnostic:
        raise ValueError('Native delivery requires independently reviewed original capture')
    source_hashes = result.get('source_evidence_hashes', {})
    required = {'crosswalk_context.json', 'site_packet.json', 'reverse_history.jsonl',
                'video_frames.jsonl', 'district.txt', 'geometry.txt', 'marking.txt'}
    if not required <= set(source_hashes) or analysis.get('source_hashes') != source_hashes:
        raise ValueError('Original source inventory differs')
    for name, expected in source_hashes.items():
        if not (attempt / name).is_file() or sha(attempt / name) != expected:
            raise ValueError('Original source changed: ' + name)
    mapping, trace, motion = [rows(attempt / name) for name in
                              ('video_frames.jsonl', 'trace.jsonl', 'reverse_history.jsonl')]
    count = len(mapping)
    if not count or len(trace) != count or len(motion) != count:
        raise ValueError('Original frame count differs')
    for i, (frame, t, body) in enumerate(zip(mapping, trace, motion)):
        if (frame.get('video_frame') != i or frame.get('carla_frame') != t.get('frame')
                or frame.get('carla_frame') != body.get('frame')
                or frame.get('time_s') != t.get('time_s')
                or frame.get('time_s') != body.get('time_s')
                or not body.get('native_reverse') or not body.get('ego_body_vertices_xy_m')):
            raise ValueError('Original frame, time or reverse-body join differs')
        if i and (frame['carla_frame'] <= mapping[i-1]['carla_frame']
                  or abs(frame['time_s'] - mapping[i-1]['time_s'] - .05) > .001):
            raise ValueError('Original 20 Hz ordering differs')
    context, site = read(attempt / 'crosswalk_context.json'), read(attempt / 'site_packet.json')
    if (context.get('crosswalk_id') != site.get('crosswalk_id')
            or context.get('road_id') != site.get('road_id')
            or context.get('crosswalk_polygon_xy_m') != site.get('crosswalk_polygon_xy_m')):
        raise ValueError('Crosswalk source context differs')
    for name in ('district_source', 'crosswalk_geometry_source', 'crosswalk_marking_source'):
        if not site.get(name):
            raise ValueError('Missing source review pointer: ' + name)
    cameras = {row['name']: row for row in config['cameras']}
    if set(cameras) != set(CAMERAS) or set(result.get('video_references', [])) != {name+'.mkv' for name in CAMERAS}:
        raise ValueError('Four original cameras required')
    decodes = {}
    for name in CAMERAS:
        path = attempt / (name + '.mkv')
        probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                                '-show_entries', 'stream=width,height,nb_read_frames', '-of', 'json', str(path)],
                               capture_output=True, text=True, check=True)
        streams = json.loads(probe.stdout)['streams']
        if len(streams) != 1:
            raise ValueError('Camera video stream missing: ' + name)
        stream = streams[0]
        if ((stream['width'], stream['height']) != (cameras[name]['width'], cameras[name]['height'])
                or int(stream['nb_read_frames']) != count):
            raise ValueError('Camera decode dimensions or frame count differ: ' + name)
        decodes[name] = {'sha256': sha(path), 'frames': count,
                         'width': stream['width'], 'height': stream['height']}
    if result.get('capture_evidence_sha256') != sha(attempt / 'capture/evidence.jsonl'):
        raise ValueError('Capture evidence source changed')
    physical = result.get('physical_checks', {})
    if physical.get('setup', {}).get('status') != ('met' if count == 900 else 'not_met'):
        raise ValueError('Full-duration setup status differs')
    target = physical.get('target', {}).get('details', {}).get('checks', [])
    expected_overlap = case_id.endswith('reverse_over_crosswalk')
    if len(target) != 1 or target[0].get('measured') is not expected_overlap:
        raise ValueError('Case-specific crosswalk body outcome differs')
    return {'format': 'worker-reverse-source-diagnostic-audit', 'case_id': case_id,
            'diagnostic_only': True, 'software_checks_passed': True,
            'delivery_ready': False, 'physical_acceptance_claimed': False,
            'source_hashes': source_hashes, 'camera_decodes': decodes,
            'frames': count, 'planned_frames': 900,
            'full_duration_observed': count == 900,
            'real_site_reviewed': False, 'actual_pixels_reviewed': False,
            'auditor_sha256': sha(__file__)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True, type=Path)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.attempt, args.case)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'case_id': result['case_id'], 'frames': result['frames'],
                      'software_checks_passed': result['software_checks_passed']}))
