"""Independent two-case source comparison for signed school crossing timing."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path: Path) -> dict:
    if not path.is_file():
        raise ValueError('Missing comparison source: ' + path.name)
    return json.loads(path.read_text())

def rows(path: Path) -> list[dict]:
    if not path.is_file():
        raise ValueError('Missing comparison source: ' + path.name)
    return [json.loads(x) for x in path.read_text().splitlines()]

def one(case: str, path: Path) -> dict:
    saved = read(path)
    manifest = read(HERE / 'execution-manifest.json')
    entry = next((c for c in manifest['cases'] if c['case_id'] == case), None)
    if (entry is None or saved.get('case_id') != case or saved.get('passed') is not True or
            saved.get('recorded_only') is not True or
            saved.get('native_revision', {}).get('construction_sha256') != entry['construction_sha256'] or
            saved.get('timestamp_joins', {}).get('frames') != 600 or
            saved.get('final_video_checks', {}).get('frames') != 600):
        raise ValueError('Selected saved comparison member differs')
    stage = Path(saved['analysis_directory']).resolve()
    if stage != path.resolve().parent / 'analysis':
        raise ValueError('Saved comparison analysis path differs')
    geometry = read(stage / 'road_geometry.json')
    config = read(stage / 'config.json')
    samples = rows(stage / 'native_samples.jsonl')
    frames = rows(stage / 'video_frames.jsonl')
    report = read(stage / 'analysis-report.json')
    if len(samples) != len(frames) or len(samples) != 600:
        raise ValueError('Incomplete comparison source frames')
    observed = report['measurements']['signed_school_crossing_entry']['value']['entry']
    if observed['native_frame'] not in {r['native_frame'] for r in samples}:
        raise ValueError('Entry frame not source-joined')
    if report.get('physical_acceptance_claimed') is not False:
        raise ValueError('Synthetic comparison claims physical acceptance')
    return {'case_id': case, 'construction_sha256': entry['construction_sha256'],
            'processing_sha256': sha(path), 'geometry_sha256': sha(stage / 'road_geometry.json'),
            'camera_plan': config['cameras'], 'duration_s': config['duration_s'],
            'person_trajectory': [r['person'] for r in samples],
            'frame_map_sha256': sha(stage / 'video_frames.jsonl'),
            'entry': observed, 'source_kind': samples[0]['source_kind']}

def audit(comparison: str, case_a: str, case_b: str, path_a: Path, path_b: Path,
          omit_case: str | None) -> dict:
    plan = read(HERE / 'case-plan.json')
    paired = next((c for c in plan['comparisons'] if c['comparison_id'] == comparison), None)
    if paired is None or paired['case_ids'] != [case_a, case_b]:
        raise ValueError('Comparison identity or order differs')
    if omit_case:
        raise ValueError('Missing selected comparison member: ' + omit_case)
    a = one(case_a, path_a)
    b = one(case_b, path_b)
    if (a['geometry_sha256'] != b['geometry_sha256'] or
            a['camera_plan'] != b['camera_plan'] or a['duration_s'] != b['duration_s'] or
            a['person_trajectory'] != b['person_trajectory'] or
            a['frame_map_sha256'] != b['frame_map_sha256'] or
            a['source_kind'] != b['source_kind']):
        raise ValueError('Fixed school-crossing source conditions differ')
    if (a['entry']['person_in_crosswalk'] is not True or
            a['entry']['person_on_approach_side'] is not True or
            b['entry']['person_in_crosswalk'] is not False or
            a['entry']['native_frame'] >= b['entry']['native_frame']):
        raise ValueError('Measured occupied/cleared entry contrast absent')
    return {'format': 'c394563-independent-comparison-audit-v1',
            'comparison_id': comparison, 'case_ids': [case_a, case_b],
            'fixed_geometry_sha256': a['geometry_sha256'],
            'fixed_frame_map_sha256': a['frame_map_sha256'],
            'person_trajectory_sha256': hashlib.sha256(json.dumps(a['person_trajectory'], sort_keys=True).encode()).hexdigest(),
            'source_kind': a['source_kind'], 'observed_entry_a': a['entry'],
            'observed_entry_b': b['entry'], 'controlled_difference': 'ego_entry_frame',
            'observed_difference': 'person occupancy on approach side at vehicle front entry',
            'diagnostic_only': True, 'physical_or_legal_acceptance_claimed': False,
            'limits': ['City Traffic Engineer authority, original School-Xing sign pixels and person intention need independent Native review.']}

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for key in ('comparison', 'case-a', 'case-b', 'processing-a', 'processing-b', 'output'):
        p.add_argument('--' + key, required=True)
    p.add_argument('--omit-case')
    a = p.parse_args()
    result = audit(a.comparison, a.case_a, a.case_b, Path(a.processing_a),
                   Path(a.processing_b), a.omit_case)
    target = Path(a.output)
    if target.exists():
        raise ValueError('Comparison output already exists')
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'comparison_id': a.comparison,
                      'diagnostic_only': True}))
