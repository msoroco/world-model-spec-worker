"""Join original trail sources into measured observations without a legal verdict."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent


def _load(name):
    spec = importlib.util.spec_from_file_location('c143687_finalizer_' + name,
                                                  ROOT / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


delivery = _load('delivery_audit')
saved = _load('saved_audit')
source_packet = _load('source_packet')
trail = _load('trail')


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _bound(root, entry, label):
    if not isinstance(entry, dict) or not entry.get('path') or not entry.get('sha256'):
        raise ValueError(label + ' source reference missing')
    path = delivery._confined(root, entry['path'])
    if _sha(path) != entry['sha256']:
        raise ValueError(label + ' source hash mismatch')
    return path


def finalize(attempt: Path, case_id: str) -> dict:
    root = Path(attempt).resolve()
    suffix = saved._case_suffix(case_id)
    acquisition_path = root / 'acquisition.json'
    acquisition = json.loads(acquisition_path.read_text(encoding='utf-8'))
    diagnostic = acquisition.get('diagnostic_fixture')
    kind = acquisition.get('provenance_kind')
    if type(diagnostic) is not bool or kind != ('diagnostic_fixture' if diagnostic else 'original_native'):
        raise ValueError('saved acquisition provenance missing or inconsistent')
    site_path = _bound(root, acquisition.get('site'), 'site')
    source_path = _bound(root, acquisition.get('source_packet'), 'source packet')
    site = json.loads(site_path.read_text(encoding='utf-8'))
    case = next(item for item in trail.CASES if item.name == suffix)
    if site.get('case_id') != case_id:
        raise ValueError('saved site differs from exact case')
    if diagnostic and site.get('provenance_kind') != 'diagnostic_fixture':
        raise ValueError('diagnostic site provenance missing')
    if not diagnostic and site.get('provenance_kind') != 'reviewed_original':
        raise ValueError('original reviewed site provenance missing')
    trail.validate_source(site, case)
    original_sources = source_packet.verify_packet(site, source_path)
    media = delivery.audit_saved(root, acquisition_path, case_id)
    packet_path = _bound(root, acquisition.get('packet_stream'), 'original tick packet')
    history = acquisition['history']
    joined = saved.audit_packet_join(
        delivery._confined(root, history['path']), history['sha256'],
        packet_path, acquisition['packet_stream']['sha256'],
        site['corridor_box_xy'], case_id)
    if joined['joined_frames'] != 900 or not joined['entered_corridor']:
        raise ValueError('saved trail corridor entry missing')
    summary = saved.audit_history(root / history['path'], history['sha256'], case_id)
    return {
        'format': 'worker-analysis-report', 'analysis_complete': True,
        'case_id': case_id, 'provenance_kind': kind, 'diagnostic_fixture': diagnostic,
        'measurements': {
            'trail_corridor_entry': {'value': joined['entered_corridor'],
                                     'source': history['path'],
                                     'source_sha256': history['sha256']},
            'sign_face_readback': {'value': summary['sign_face_readback'],
                                   'source': history['path'],
                                   'source_sha256': history['sha256']},
            **{key: {'value': summary[key], 'source_sha256': summary[
                {'official_plan_designation': 'official_plan_source_sha256',
                 'city_trail_dedication': 'dedication_source_sha256',
                 'prohibits_motor_vehicles': 'sign_face_sha256',
                 'emergency_use': 'exception_status_source_sha256',
                 'maintenance_use': 'exception_status_source_sha256'}[key]]}
               for key in saved.CONDITIONS},
        },
        'source_packet_sha256': original_sources['packet_sha256'],
        'original_packets_sha256': joined['original_packets_sha256'],
        'acquisition_sha256': media['acquisition_sha256'],
        'camera_media_sha256': {name: item['sha256'] for name, item in media['camera_media'].items()},
        'frame_count': 900, 'full_video_decode': False, 'actual_pixels': False,
        'physical_completion': False, 'legal_judgment': None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = finalize(Path(args.attempt), args.case)
    output = Path(args.output).resolve()
    root = Path(args.attempt).resolve()
    if output.parent != root or output.exists():
        raise ValueError('fresh analysis output must be inside saved attempt')
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({'case_id': args.case, 'analysis_complete': True,
                      'diagnostic_fixture': report['diagnostic_fixture']}))


if __name__ == '__main__':
    main()
