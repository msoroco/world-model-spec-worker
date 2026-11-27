"""Independent original freight-zone attempt and comparison audits."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from freight_zone import CASES, measure_history, validate_site
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


def audit_original_pair(left, right, difference):
    need(left.get('case_id') != right.get('case_id'), 'duplicate comparison case')
    for item in (left, right):
        need(item.get('frame_count') == 900 and item.get('original_history_sha256') and
             item.get('site_sha256'), 'comparison history or site source missing')
    for key in ('road_source_sha256', 'zone_source_sha256', 'regulations_source_sha256',
                'effective_hours_source_sha256', 'camera_plan_sha256',
                'vehicle_blueprint', 'passenger_blueprint', 'freight_vehicle_blueprint',
                'materials_inventory_source_sha256', 'freight_entry_source_sha256',
                'traffic_and_official_directions_source_sha256', 'clock_source_sha256',
                'civil_time_iso'):
        need(left.get(key) and left[key] == right.get(key),
             'fixed comparison condition changed: ' + key)
    need(difference in ('conduct', 'material_action', 'activity_delay_s',
                        'passenger_action', 'freight_arrival'),
         'unsupported original comparison difference')
    need(left.get(difference) != right.get(difference), 'deliberate difference absent')
    need(left.get('regulations_effective') is True and
         right.get('regulations_effective') is True, 'comparison hours changed')
    return {'left': left['case_id'], 'right': right['case_id'],
            'difference': difference, 'legal_judgment': None}


def audit_attempt(attempt, case_id):
    need(case_id.startswith(ASSIGNMENT + '__'), 'wrong exact freight-zone case')
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
    capture_seal_path = source(root, manifest, 'capture-seal.json')
    map_path = source(root, manifest, 'camera-frame-map.jsonl')
    video_map_path = source(root, manifest, 'video_frames.jsonl')
    seal_path = source(root, manifest, 'saved-seal.json')
    result_path = source(root, manifest, 'saved-result.json')
    site, seal, saved = read(site_path), read(seal_path), read(result_path)
    capture_seal = read(capture_seal_path)
    need(manifest.get('capture_seal_sha256') == sha(capture_seal_path) and
         capture_seal.get('case_id') == case_id and
         capture_seal.get('provenance_kind') == 'native' and
         capture_seal.get('diagnostic_fixture') is False and
         capture_seal.get('frames') == 900,
         'original Native capture seal changed')
    for name, digest in capture_seal.get('sources', {}).items():
        relative = Path(name)
        candidate = root / relative
        need(not relative.is_absolute() and '..' not in relative.parts and
             candidate.is_file() and not candidate.is_symlink() and sha(candidate) == digest,
             'original Native capture source changed: ' + name)
    reviewed_manifest_path = root / 'reviewed-site/source-manifest.json'
    reviewed_site_path = root / 'reviewed-site/site-context.json'
    need(reviewed_manifest_path.is_file() and reviewed_site_path.is_file() and
         not reviewed_manifest_path.is_symlink() and not reviewed_site_path.is_symlink() and
         capture_seal.get('reviewed_manifest_sha256') == sha(reviewed_manifest_path) and
         capture_seal.get('reviewed_site_sha256') == sha(reviewed_site_path),
         'reviewed original site packet changed')
    reviewed_manifest = read(reviewed_manifest_path)
    reviewed_site = read(reviewed_site_path)
    provenance = reviewed_manifest.get('source_provenance', {})
    need(reviewed_manifest.get('source_kind') == 'reviewed_original_site' and
         reviewed_manifest.get('diagnostic_fixture') is False and
         provenance.get('kind') == 'original_reviewed_site' and
         provenance.get('diagnostic_fixture') is False and
         provenance.get('reviewer') and provenance.get('citation'),
         'original reviewed site provenance changed')
    reviewed_site['source_kind'] = 'original_native_capture'
    need(site == reviewed_site, 'finalized original site differs from reviewed source')
    short = case_id.removeprefix(ASSIGNMENT + '__')
    case = next((item for item in CASES if item.name == short), None)
    need(case is not None and site.get('source_kind') == 'original_native_capture' and
         site.get('case_id') == case_id and site.get('reviewer'),
         'reviewed original freight-zone site missing')
    validate_site(site, case)
    need(site['zone'].get('passenger_anchor_source_sha256') and
         site['zone'].get('materials_anchor_source_sha256'),
         'original material or passenger anchor source missing')
    audit = audit_original_history(history_path, sha(history_path), short,
                                   site['zone']['boundary_source_sha256'], site['regulations']['source_sha256'])
    rows = [json.loads(line) for line in history_path.read_text().splitlines() if line]
    measured = measure_history(rows, case, site)
    camera_rows = [json.loads(line) for line in map_path.read_text().splitlines() if line]
    video_rows = [json.loads(line) for line in video_map_path.read_text().splitlines() if line]
    need(len(camera_rows) == len(video_rows) == len(rows) == 900,
         'original camera/Native frame count differs')
    for index, (history_row, camera_row, video_row) in enumerate(zip(rows, camera_rows, video_rows)):
        frame = history_row['original_frame']
        need(camera_row.get('original_frame') == frame and
             camera_row.get('time_s') == history_row['elapsed_s'] and
             camera_row.get('camera_frames') == {name: frame for name in CAMERAS} and
             video_row.get('video_frame') == index and
             video_row.get('carla_frame') == frame and video_row.get('native_frame') == frame and
             video_row.get('time_s') == history_row['elapsed_s'],
             'original camera/Native same-tick join differs')
    need(seal.get('case_id') == short and seal.get('site_sha256') == sha(site_path) and
         seal.get('original_history_sha256') == sha(history_path), 'saved seal changed')
    need(saved.get('case_id') == short and saved.get('site_sha256') == sha(site_path) and
         saved.get('original_history_sha256') == sha(history_path) and
         saved.get('measurement') == json.loads(json.dumps(measured)),
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
             'passenger_blueprint': site['passenger_blueprint'],
             'freight_vehicle_blueprint': site['freight_vehicle_blueprint'],
             'materials_inventory_source_sha256': site['materials_inventory_source_sha256'],
             'freight_entry_source_sha256': site['road']['freight_entry_source_sha256'],
             'traffic_and_official_directions_source_sha256': site['traffic_and_official_directions_source_sha256']}
    need(all(fixed.values()), 'fixed original comparison source missing')
    compare_record = {'case_id': case_id, 'frame_count': 900,
                      'original_history_sha256': sha(history_path), **fixed,
                      'conduct': case.conduct, 'material_action': case.material_action,
                      'activity_delay_s': case.activity_delay_s,
                      'passenger_action': case.passenger_action,
                      'freight_arrival': case.freight_arrival,
                      'material_events': measured['material_events'],
                      'passenger_events': measured['passenger_events'],
                      'freight_events': measured['freight_events'],
                      'freight_entry_blocked_frames': measured['freight_entry_blocked_frames'],
                      'halt_to_material_event_s': measured['halt_to_material_event_s'],
                      'regulations_effective': site['regulations']['effective_at_civil_time']}
    return {'format': 'c386226-independent-original-audit-v1', 'case_id': case_id,
            'source_kind': 'original_native_capture', 'source_manifest_sha256': sha(manifest_path),
            'measurement': measured, 'comparison_record': compare_record,
            'camera_decodes': decodes, 'legal_status': 'unresolved', 'physical_acceptance': False}


def audit_comparisons(reports):
    """Verify fixed original sources and the declared observed differences."""
    plan = read(HERE / 'case-plan.json')
    need(set(reports) == {item['case_id'] for item in plan['cases']},
         'all exact original reports required')
    rules = {
        'prohibited_conduct_without_materials': ('conduct', None),
        'actual_materials_alternatives': ('material_action', 'material_events'),
        'material_activity_timing': ('activity_delay_s', 'halt_to_material_event_s'),
        'effective_hours_condition': ('regulations_effective', None),
        'passenger_exception_activity': ('passenger_action', 'passenger_events'),
        'passenger_exception_interference': ('freight_arrival', 'freight_events'),
    }
    out = []
    for comparison in plan['comparisons']:
        cid_list = comparison['case_ids']
        need(comparison['comparison_id'] in rules, 'unknown comparison branch')
        difference, observed = rules[comparison['comparison_id']]
        for cid in cid_list:
            report = reports[cid]
            need(report.get('format') == 'c386226-independent-original-audit-v1' and
                 report.get('case_id') == cid and report.get('source_kind') == 'original_native_capture' and
                 report.get('legal_status') == 'unresolved' and report.get('physical_acceptance') is False and
                 report.get('comparison_record', {}).get('original_history_sha256'),
                 'comparison includes nonoriginal or wrong-case audit')
        values = [reports[cid]['comparison_record'].get(difference) for cid in cid_list]
        need(len({json.dumps(v, sort_keys=True) for v in values}) == len(values),
             'deliberate comparison setup difference absent')
        if observed:
            measured = [reports[cid]['comparison_record'].get(observed) for cid in cid_list]
            need(all(value is not None for value in measured) and
                 len({json.dumps(v, sort_keys=True) for v in measured}) == len(measured),
                 'original observed comparison difference absent: ' + observed)
        anchor = reports[cid_list[0]]['comparison_record']
        for cid in cid_list[1:]:
            current = reports[cid]['comparison_record']
            if difference == 'regulations_effective':
                for key in ('road_source_sha256', 'regulations_source_sha256',
                            'effective_hours_source_sha256', 'zone_source_sha256',
                            'camera_plan_sha256', 'vehicle_blueprint', 'passenger_blueprint',
                            'freight_vehicle_blueprint', 'materials_inventory_source_sha256',
                            'freight_entry_source_sha256',
                            'traffic_and_official_directions_source_sha256'):
                    need(anchor.get(key) and anchor[key] == current.get(key),
                         'fixed hours comparison source changed: ' + key)
                need(anchor.get('civil_time_iso') != current.get('civil_time_iso') and
                     anchor.get('clock_source_sha256') and current.get('clock_source_sha256'),
                     'sourced civil effective-hours difference absent')
            else:
                audit_original_pair(anchor, current, difference)
        out.append({'comparison_id': comparison['comparison_id'],
                    'case_ids': cid_list, 'measured_difference': difference,
                    'original_values': values, 'legal_status': 'unresolved',
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
        result = {'format': 'c386226-independent-comparison-audit-v1',
                  'comparisons': matched,
                  'legal_status': 'unresolved', 'physical_acceptance': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
