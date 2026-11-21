"""Independently compare the newly laid pair's retained CPU diagnostic sources."""
import argparse
import hashlib
import json
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon

HERE = Path(__file__).resolve().parent
CASES = ('newly_laid_crossing', 'newly_laid_avoidance')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FIXED = ('assignment_id', 'law_id', 'cell_id', 'actor', 'frames', 'rate_hz',
         'duration_s', 'controller_knobs',
         'camera_overrides', 'cameras', 'recording_description')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def require(ok, message):
    if not ok:
        raise ValueError(message)


def inspect_case(manifest, manifest_path, short, source, saved):
    source, saved = Path(source), Path(saved)
    case_id = HERE.name + '__' + short
    entry = next(row for row in manifest['cases'] if row['case_id'] == case_id)
    selection = read(source / 'candidate-selection.json')
    processing = read(saved / 'v0001/processing.json')
    analysis = read(saved / 'v0001/analysis/source-analysis.json')
    config = read(source / 'config.json')
    readback = read(source / 'live-readback.json')
    require(selection['case_id'] == case_id and
            selection['candidate_id'] == 'primary' and
            selection['manifest_sha256'] == sha(manifest_path) and
            selection['construction_sha256'] == entry['construction_sha256'],
            'Newly laid diagnostic candidate selection differs')
    require(processing['case_id'] == case_id and processing['candidate_id'] == 'primary'
            and processing['passed'] is True and processing['recorded_only'] is True
            and processing['originals_preserved'] is True
            and processing['missing_evidence'] is False
            and processing['timestamp_joins']['frames'] == 600
            and processing['analysis_revision']['construction_sha256'] == entry['construction_sha256'],
            'Newly laid saved processing differs')
    require(analysis['case'] == short and analysis['source_kind'] == 'synthetic_diagnostic_capture'
            and analysis['format'] == 'c183370-newly-laid-diagnostic-source-analysis-v1'
            and config['case_id'] == case_id and config['frames'] == 600,
            'Newly laid analyzed case or diagnostic provenance differs')
    for name, digest in analysis['source_hashes'].items():
        require(sha(source / name) == digest,
                'Newly laid original diagnostic source changed: ' + name)
    cameras = {row['name']: row for row in analysis['camera_sources']}
    require(set(cameras) == set(CAMERAS), 'Four newly laid camera sources required')
    for name, camera in cameras.items():
        require(sha(source / (name + '.mkv')) == camera['source_sha256']
                and camera['decoded_frames'] == 600,
                'Newly laid camera hash or duration differs: ' + name)
    polygon = Polygon(readback['plan']['laid_polygon_xy_m'])
    require(polygon.is_valid and polygon.area > 0, 'Newly laid surveyed polygon invalid')
    frames = [json.loads(line) for line in (source / 'video_frames.jsonl').read_text().splitlines()]
    actors = [json.loads(line) for line in (source / 'native-actors.jsonl').read_text().splitlines()]
    require(len(frames) == len(actors) == 600, 'Newly laid source duration differs')
    contacts = []
    for index, (frame, actor) in enumerate(zip(frames, actors)):
        require(frame['video_frame'] == actor['video_frame'] == index
                and frame['carla_frame'] == actor['frame']
                and frame['time_s'] == actor['time_s'],
                'Newly laid original frame join differs')
        body = MultiPoint([(v[0], v[1]) for v in actor['ego_body_vertices_xyz_m']]).convex_hull
        require(body.area > 0, 'Newly laid original body invalid')
        if body.intersects(polygon):
            contacts.append(index)
    require(contacts == analysis['observations']['pavement_footprint_contact_frames'],
            'Newly laid analyzed contact differs from independent recomputation')
    return {'case_id': case_id, 'config': config, 'readback': readback,
            'contact_frames': contacts, 'processing_sha256': sha(saved / 'v0001/processing.json'),
            'source_analysis_sha256': sha(saved / 'v0001/analysis/source-analysis.json')}


def audit(left_source, left_saved, right_source, right_saved, manifest_path=None):
    manifest_path = Path(manifest_path or HERE / 'draft-newly-laid-finalized-manifest.json')
    manifest = read(manifest_path)
    require([row['case_id'] for row in manifest['cases']
             if row['case_id'] in {HERE.name + '__' + short for short in CASES}] ==
            [HERE.name + '__' + short for short in CASES],
            'Newly laid exact pair differs')
    plan = read(HERE / 'case-plan.json')
    comparison_id = HERE.name + '__comparison_newly_laid'
    comparison = next(row for row in plan['comparisons']
                      if row['comparison_id'] == comparison_id)
    require(comparison['case_ids'] == [HERE.name + '__' + short for short in CASES]
            and comparison['deliberate_differences'] == ['requested_pavement_crossing'],
            'Newly laid comparison plan differs')
    left = inspect_case(manifest, manifest_path, CASES[0], left_source, left_saved)
    right = inspect_case(manifest, manifest_path, CASES[1], right_source, right_saved)
    require(all(left['config'].get(key) == right['config'].get(key) for key in FIXED)
            and left['readback'] == right['readback'],
            'Newly laid fixed capture/survey context changed')
    require(bool(left['contact_frames']) and not right['contact_frames'],
            'Newly laid observed contact difference missing')
    return {'format': 'c183370-newly-laid-diagnostic-pair-audit-v1',
            'comparison_id': comparison_id,
            'manifest_sha256': sha(manifest_path),
            'case_ids': comparison['case_ids'],
            'source_analysis_sha256': [left['source_analysis_sha256'],
                                       right['source_analysis_sha256']],
            'processing_sha256': [left['processing_sha256'], right['processing_sha256']],
            'observed_contact': [True, False], 'diagnostic_fixed_context_checked': True,
            'full_original_context_verified': False,
            'limitations': ['Synthetic readback does not establish original weather, ego blueprint, surface age or warning act.'],
            'diagnostic_only': True, 'accepted': False,
            'original_native_observed': False,
            'physical_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for key in ('left-source', 'left-saved', 'right-source', 'right-saved', 'output'):
        parser.add_argument('--' + key, required=True)
    parser.add_argument('--manifest', type=Path)
    args = parser.parse_args()
    result = audit(args.left_source, args.left_saved,
                   args.right_source, args.right_saved, args.manifest)
    path = Path(args.output)
    require(not path.exists(), 'Preserve prior newly laid diagnostic pair audit')
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'comparison_id': result['comparison_id'],
                      'accepted': result['accepted'],
                      'audit_sha256': sha(path)}, sort_keys=True))
