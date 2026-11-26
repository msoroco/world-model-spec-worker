"""Independent original passenger-zone attempt and comparison audits."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from passenger_zone import CASES, audit_pair, measure_history, validate_site
from saved_audit import audit_original_history

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
                            '-of', 'json', str(path)], capture_output=True, text=True, check=True, timeout=120)
    streams = json.loads(probe.stdout).get('streams', [])
    need(len(streams) == 1, 'one original camera stream required')
    item = streams[0]
    need(item.get('nb_read_frames') == '900' and item.get('r_frame_rate') in ('20/1', '20') and
         [item.get('width'), item.get('height')] == size, 'original camera frame profile differs')
    subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path), '-f', 'null', '-'],
                   capture_output=True, check=True, timeout=180)
    return {'frames': 900, 'fps': 20, 'size': size}


def audit_attempt(attempt, case_id):
    need(case_id.startswith(ASSIGNMENT + '__'), 'wrong exact passenger-zone case')
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
    history_path = source(root, manifest, 'original-history.jsonl')
    seal_path = source(root, manifest, 'saved-seal.json')
    result_path = source(root, manifest, 'saved-result.json')
    site, seal, saved = read(site_path), read(seal_path), read(result_path)
    short = case_id.removeprefix(ASSIGNMENT + '__')
    case = next((item for item in CASES if item.name == short), None)
    need(case is not None and site.get('source_kind') == 'original_native_capture' and site.get('reviewer'),
         'reviewed original passenger-zone site missing')
    validate_site(site, case)
    need(site['zone'].get('passenger_anchor_source_sha256'), 'original passenger anchor source missing')
    audit = audit_original_history(history_path, sha(history_path), short,
                                   site['zone']['boundary_source_sha256'], site['regulations']['source_sha256'])
    rows = [json.loads(line) for line in history_path.read_text().splitlines() if line]
    measured = measure_history(rows, case, site)
    need(seal.get('case_id') == short and seal.get('site_sha256') == sha(site_path) and
         seal.get('original_history_sha256') == sha(history_path), 'saved seal changed')
    need(saved.get('case_id') == short and saved.get('site_sha256') == sha(site_path) and
         saved.get('original_history_sha256') == sha(history_path) and saved.get('measurement') == measured,
         'saved result differs from original history')
    need(saved.get('delivery_audit') == audit and saved.get('legal_judgment') is None,
         'saved independent history audit or judgment changed')
    identity_path = root / 'capture-identity.json'
    need(identity_path.is_file() and not identity_path.is_symlink(), 'original capture identity missing')
    identity = read(identity_path)
    need(identity.get('case_id') == case_id and identity.get('source_kind') == 'original_native_capture' and
         identity.get('diagnostic_fixture') is False and identity.get('source_manifest_sha256') == sha(manifest_path),
         'original capture identity or source binding missing')
    video_items = identity.get('cameras')
    need(isinstance(video_items, dict) and set(video_items) == set(CAMERAS), 'four original camera sources required')
    decodes = {}
    for name in CAMERAS:
        path = source(root, manifest, name + '.mkv')
        need(video_items[name].get('sha256') == sha(path) and video_items[name].get('frame_count') == 900,
             'original camera source changed: ' + name)
        decodes[name] = decode_camera(path, [1920, 1080] if name == 'overview' else [1280, 720])
    fixed = {'site_sha256': sha(site_path),
             'road_source_sha256': site['road']['source_sha256'],
             'regulations_source_sha256': site['regulations']['source_sha256'],
             'effective_hours_source_sha256': site['regulations']['effective_hours_source_sha256'],
             'clock_source_sha256': site['clock']['source_sha256'],
             'civil_time_iso': site['clock']['civil_time_iso'],
             'camera_plan_sha256': rows[0]['camera_plan_sha256'],
             'zone_source_sha256': site['zone']['boundary_source_sha256'],
             'vehicle_blueprint': site['vehicle_blueprint'],
             'passenger_blueprint': site['passenger_blueprint']}
    need(all(fixed.values()), 'fixed original comparison source missing')
    compare_record = {'case_id': case_id, 'frame_count': 900,
                      'original_history_sha256': sha(history_path), **fixed,
                      'conduct': case.conduct, 'passenger_action': case.passenger_action,
                      'release_delay_s': case.release_delay_s,
                      'zone_boundary_signed_distance_m': measured['zone_boundary_signed_distance_m'],
                      'civil_boundary_offset_min': measured['civil_boundary_offset_min'],
                      'passenger_event_delay_s': measured['passenger_event_delay_s'],
                      'regulations_effective': site['regulations']['effective_at_civil_time']}
    return {'format': 'c150116-independent-original-audit-v1', 'case_id': case_id,
            'source_kind': 'original_native_capture', 'source_manifest_sha256': sha(manifest_path),
            'measurement': measured, 'comparison_record': compare_record,
            'camera_decodes': decodes, 'legal_status': 'unresolved', 'physical_acceptance': False}


def audit_comparisons(reports):
    plan = read(HERE / 'case-plan.json')
    need(set(reports) == {item['case_id'] for item in plan['cases']}, 'all exact original reports required')
    differences = {'conduct_without_passenger': 'conduct',
                   'passenger_exception_activity': 'passenger_action',
                   'activity_timing': 'release_delay_s',
                   'effective_hours': 'regulations_effective',
                   'engineering_zone_marking': 'zone_boundary_signed_distance_m',
                   'engineering_regulation_hours': 'civil_boundary_offset_min',
                   'engineering_expeditious': 'passenger_event_delay_s'}
    out = []
    for comparison in plan['comparisons']:
        cid_list = comparison['case_ids']
        difference = differences[comparison['comparison_id']]
        anchor = reports[cid_list[0]]
        for cid in cid_list:
            report = reports[cid]
            need(report.get('format') == 'c150116-independent-original-audit-v1' and
                 report.get('case_id') == cid and report.get('source_kind') == 'original_native_capture' and
                 report.get('legal_status') == 'unresolved' and report.get('physical_acceptance') is False and
                 report.get('comparison_record', {}).get('original_history_sha256'),
                 'comparison includes nonoriginal or wrong-case audit')
        if comparison['comparison_id'].startswith('engineering_'):
            need(len(cid_list) == 3, 'engineering comparison requires three original attempts')
            values = [reports[cid]['comparison_record'].get(difference) for cid in cid_list]
            need(all(type(value) in (int, float) for value in values) and len(set(values)) == 3,
                 'original engineering measurements missing or collapsed')
            fixed_keys = ['road_source_sha256', 'regulations_source_sha256',
                          'effective_hours_source_sha256', 'zone_source_sha256',
                          'camera_plan_sha256', 'vehicle_blueprint', 'passenger_blueprint']
            if difference != 'civil_boundary_offset_min':
                fixed_keys.extend(['clock_source_sha256', 'civil_time_iso'])
            for cid in cid_list[1:]:
                left, right = anchor['comparison_record'], reports[cid]['comparison_record']
                for key in fixed_keys:
                    need(left.get(key) and left[key] == right.get(key),
                         'fixed engineering comparison source changed: ' + key)
            out.append({'comparison_id': comparison['comparison_id'], 'case_ids': cid_list,
                        'measured_difference': difference, 'measured_values': values,
                        'legal_status': 'unresolved', 'physical_acceptance': False})
            continue
        for cid in cid_list[1:]:
            left, right = anchor['comparison_record'], reports[cid]['comparison_record']
            if difference == 'regulations_effective':
                for key in ('road_source_sha256', 'regulations_source_sha256',
                            'effective_hours_source_sha256', 'zone_source_sha256',
                            'camera_plan_sha256', 'vehicle_blueprint', 'passenger_blueprint'):
                    need(left.get(key) and left[key] == right.get(key),
                         'fixed hours comparison condition changed: ' + key)
                need(left.get('civil_time_iso') != right.get('civil_time_iso') and
                     left.get('clock_source_sha256') and right.get('clock_source_sha256') and
                     left.get('regulations_effective') is True and
                     right.get('regulations_effective') is False,
                     'sourced effective-hours difference absent')
            else:
                audit_pair(left, right, difference)
        out.append({'comparison_id': comparison['comparison_id'], 'case_ids': cid_list,
                    'measured_difference': difference, 'legal_status': 'unresolved',
                    'physical_acceptance': False})
    return out


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    case = sub.add_parser('case')
    case.add_argument('--attempt', type=Path, required=True)
    case.add_argument('--case', required=True)
    case.add_argument('--output', type=Path, required=True)
    comparisons = sub.add_parser('comparisons')
    comparisons.add_argument('--attempts', type=Path, required=True,
                             help='JSON mapping each exact case ID to a closed original attempt directory')
    comparisons.add_argument('--comparison', required=True)
    comparisons.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior independent audit')
    if args.command == 'case':
        result = audit_attempt(args.attempt, args.case)
    else:
        attempt_index = read(args.attempts)
        need(isinstance(attempt_index, dict), 'exact original attempt index required')
        expected = {item['case_id'] for item in read(HERE / 'case-plan.json')['cases']}
        need(set(attempt_index) == expected, 'all exact original attempts required')
        report_index = {cid: audit_attempt(attempt_index[cid], cid) for cid in sorted(expected)}
        matched = [item for item in audit_comparisons(report_index)
                   if item['comparison_id'] == args.comparison]
        need(len(matched) == 1, 'unknown comparison ID')
        result = {'format': 'c150116-independent-comparison-audit-v1',
                  'comparisons': matched,
                  'legal_status': 'unresolved', 'physical_acceptance': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
