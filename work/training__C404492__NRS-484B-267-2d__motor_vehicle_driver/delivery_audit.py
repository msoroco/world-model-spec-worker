"""Independent saved-source audit; diagnostics cannot establish physical acceptance."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('capture/manifest.json', 'trace.jsonl', 'vehicle_poses.jsonl',
           'video_frames.jsonl', 'emergency_context.json',
           *(name + '.mkv' for name in CAMERAS))


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected_statutory_context(context, case):
    """Require reviewed facts for the selected moving, undirected branch."""
    if (context.get('case_id') != case or
            context.get('review_kind') != 'original_source_review' or
            not context.get('reviewer')):
        raise ValueError('Original statutory context review required')
    official = case.endswith(('__official_1', '__official_2'))
    if official:
        if context.get('official_regulatory_vehicle') is not True:
            raise ValueError('Regulatory vehicle status unproved')
        value = context.get('regulatory_agency_vehicle_source')
        if not isinstance(value, str) or not value or value.startswith('synthetic-fixture:'):
            raise ValueError('Original regulatory agency source missing')
    elif context.get('emergency_vehicle_authorized') is not True:
        raise ValueError('Emergency authority unproved')
    if context.get('qualifying_flash_equipment_reviewed') is not True:
        raise ValueError('Flashing equipment unproved')
    if context.get('officer_directed_otherwise') is not False:
        raise ValueError('Selected undirected branch requires reviewed officer exception absence')
    for key in ('ego_driver_source', 'ego_vehicle_source',
                *(('regulatory_agency_vehicle_source',) if official else ('emergency_authorization_source',)),
                'qualifying_flash_equipment_source',
                'flashing_light_visual_source', 'lane_boundary_source',
                'officer_direction_review_source'):
        value = context.get(key)
        if not isinstance(value, str) or not value or value.startswith('synthetic-fixture:'):
            raise ValueError('Original statutory source missing: ' + key)


def audit(case, candidate, attempt, processing, diagnostic=False):
    manifest = read(HERE / 'execution-manifest.json')
    entry = next((item for item in manifest['cases'] if item['case_id'] == case), None)
    if entry is None:
        raise ValueError('Unselected delivery case')
    selected = entry if candidate == 'primary' else next(
        (item for item in entry['candidates'] if item['id'] == candidate), None)
    if selected is None or sha(HERE / selected['construction']) != selected['construction_sha256']:
        raise ValueError('Selected construction changed')
    selection = read(attempt / 'candidate-selection.json')
    if (selection.get('candidate_id') != candidate or
            selection.get('construction_sha256') != selected['construction_sha256']):
        raise ValueError('Candidate selection changed')
    saved = read(processing)
    if (saved.get('passed') is not True or saved.get('recorded_only') is not True or
            saved.get('originals_preserved') is not True or
            saved.get('timestamp_joins', {}).get('frames') != 600 or
            saved.get('final_video_checks', {}).get('passed') is not True or
            saved.get('case_id') != case or saved.get('candidate_id') != candidate or
            saved.get('missing_evidence') or saved.get('physical_acceptance_claimed') or
            saved.get('legal_acceptance_claimed')):
        raise ValueError('Saved processing proof incomplete')
    hashes = {}
    for name in SOURCES:
        path = attempt / name
        if not path.is_file():
            raise ValueError('Missing original source: ' + name)
        hashes[name] = sha(path)
        if saved['original_source_hashes'].get(name) != hashes[name]:
            raise ValueError('Saved original source changed: ' + name)
    result = Path(saved['result'])
    if not result.is_file() or sha(result) != saved['result_sha256']:
        raise ValueError('Saved result changed')
    value = read(result)
    if value.get('case_id') != case or value.get('accepted') or value.get('legal_verdict_claimed'):
        raise ValueError('Saved result identity or acceptance changed')
    frame_map, poses, trace = (rows(attempt / name) for name in
                               ('video_frames.jsonl', 'vehicle_poses.jsonl', 'trace.jsonl'))
    context = read(attempt / 'emergency_context.json')
    if len(frame_map) != 600 or len(poses) != 600 or len(trace) != 600:
        raise ValueError('Original frame count differs')
    if (context.get('case_id') != case or
            any(p.get('ego', {}).get('actor_id') != context.get('ego_actor_id') or
                p.get('emergency', {}).get('actor_id') != context.get('emergency_actor_id')
                for p in poses)):
        raise ValueError('Original participants differ')
    for i, (f, p, t) in enumerate(zip(frame_map, poses, trace)):
        native = f.get('native_frame')
        if (f.get('video_frame') != i or p.get('video_frame') != i or
                p.get('native_frame') != native or t.get('frame') != native or
                abs(float(t['time_s']) - float(f['time_s'])) > 1e-8 or
                set(f.get('camera_native_frames', {})) != set(CAMERAS) or
                any(f['camera_native_frames'][name] != native for name in CAMERAS)):
            raise ValueError('Original Native camera/pose/trace join differs')
    common = {'format': 'c404492-emergency-delivery-audit-v1', 'case_id': case,
              'candidate_id': candidate, 'original_source_sha256': hashes,
              'source_kind': read(attempt / 'capture/manifest.json').get('acquisition')}
    if diagnostic:
        return {**common, 'diagnostic_only': True, 'accepted': False,
                'checks': {'time_join': True, 'all_participants': True,
                           'full_video_decode': True, 'native_source': False,
                           'actual_pixels': False, 'physical_completion': False}}
    if (common['source_kind'] != 'original_native' or
            selection.get('manifest_sha256') != sha(HERE / 'execution-manifest.json')):
        raise ValueError('Original Native source required')
    selected_statutory_context(context, case)
    review_path = attempt / 'independent-physical-review.json'
    if not review_path.is_file():
        raise ValueError('Independent physical and pixel review required')
    review = read(review_path)
    authority_review = ('regulatory_authority_reviewed' if case.endswith(('__official_1', '__official_2'))
                        else 'emergency_authorization_reviewed')
    required = ('all_participants_reviewed', 'four_original_camera_pixels_reviewed',
                'actual_motion_and_overlap_reviewed', 'flashing_equipment_reviewed',
                authority_review, 'officer_direction_reviewed', 'native_completion_reviewed')
    if review.get('case_id') != case or any(review.get(key) is not True for key in required):
        raise ValueError('Independent statutory source review incomplete')
    return {**common, 'accepted': True, 'checks': {key: True for key in
            ('native_source', 'all_participants', 'time_join', 'full_video_decode',
             'actual_pixels', 'physical_completion')}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('case', 'candidate', 'attempt', 'processing', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain previous audit output')
    value = audit(args.case, args.candidate, Path(args.attempt), Path(args.processing), args.diagnostic)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps({'case_id': args.case, 'diagnostic_only': args.diagnostic,
                      'accepted': value['accepted']}))
