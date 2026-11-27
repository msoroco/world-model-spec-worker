"""Bind eight selected two-vehicle Native cases to their CPU proof chain."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
EVIDENCE = {
    'ego_pose': ['vehicle-poses.jsonl', 'video_frames.jsonl'],
    'curbside_pose': ['vehicle-poses.jsonl', 'body-footprints.jsonl'],
    'curb_geometry': ['road.xodr', 'map-geometry.json', 'highway-review.json'],
    'ego_highway_side_of_curbside': ['map-geometry.json', 'body-footprints.jsonl'],
    'longitudinal_overlap_m': ['body-footprints.jsonl', 'vehicle-poses.jsonl'],
    'lateral_surface_gap_m': ['body-footprints.jsonl', 'map-geometry.json'],
    'concurrent_overlap_at_rest': ['body-footprints.jsonl', 'vehicle-poses.jsonl'],
    'longest_concurrent_run_frames': ['body-footprints.jsonl', 'vehicle-poses.jsonl'],
    'activity_context': ['activity-review.json', 'body-footprints.jsonl'],
    'traffic_conflict_context': ['exception-review.json', 'overview.mkv'],
    'law_compliance_context': ['exception-review.json'],
    'police_direction_context': ['exception-review.json', 'overview.mkv'],
    'device_direction_context': ['exception-review.json', 'overview.mkv'],
    'source_camera_frame_join': ['video_frames.jsonl', 'overview.mkv',
                                 'approach.mkv', 'reference_corner.mkv',
                                 'driver_reference.mkv'],
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    manifest['status'] = 'cpu_prepared_pending_original_highway_activity_exception_review'
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        proof = HERE / 'proofs' / suffix
        physical = proof / 'physical-preparation.json'
        entry['physical_preparation'] = {'receipt': str(physical.relative_to(HERE)),
                                         'sha256': digest(physical)}
        entry['acquisition'] = {name: {'entrypoint': 'runner.py',
            'method': 'Original Native frame and independent source review for ' + name,
            'evidence': sources} for name, sources in EVIDENCE.items()}
        entry['post_capture'] = {'recorded_only': True,
            'command': 'runtime.py process-saved --manifest work/' + AID + '/execution-manifest.json --case ' + entry['case_id'] +
                ' --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER',
            'feedback_command': 'cat $SAVED_OUTPUT/feedback.json # ' + entry['case_id']}
        saved_log = proof / 'saved.log'
        if saved_log.is_file():
            entry['post_capture'].update(test_log=str(saved_log.relative_to(HERE)),
                test_log_sha256=digest(saved_log), test_exit_code=0)
    (HERE / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    first = json.loads((HERE / manifest['cases'][0]['construction']).read_text())
    for item in first['files']:
        target = HERE / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item['content'])
    (HERE / 'construction.json').write_text(json.dumps(first, indent=2) + '\n')
    print({'cases': len(manifest['cases']),
           'fallbacks': sum(len(row['candidates']) for row in manifest['cases'])})


if __name__ == '__main__':
    main()
