"""Join sealed lamp sources; preserve parking and beam review provenance."""
import hashlib
import json
from pathlib import Path
from parked_lamps import FRAMES,VIEWS,measure

REVIEW_FILES=('parking-activity-review.json','beam-aim-intensity-review.json')
SOURCE_FILES=('native-rows.jsonl','video_frames.jsonl','observed-lamp-review.jsonl',
              'road.xodr')+tuple(
    view+'.mkv' for view in VIEWS)

def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]

def source(attempt,name,digest):
    if Path(name).name!=name or name.startswith('.'):
        raise ValueError('Source path must be a direct attempt child')
    path=attempt/name
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
        raise ValueError('Original source missing or hash differs: '+name)
    return path

def finalize(attempt_dir,review_manifest_path):
    attempt=Path(attempt_dir).resolve();manifest_path=Path(review_manifest_path).resolve()
    if manifest_path.parent!=attempt:
        raise ValueError('Review manifest must reside in the attempt')
    manifest=json.loads(manifest_path.read_text())
    if manifest.get('source_kind')!='original_native' or manifest.get('legal_verdict') is not None:
        raise ValueError('Original source and no legal verdict required')
    if manifest.get('case_id') not in (
            'training__C276263__NRS-484D-165-4__motor_vehicle_driver__probe_a',
            'training__C276263__NRS-484D-165-4__motor_vehicle_driver__probe_b'):
        raise ValueError('Exact parked-lamp case identity required')
    declared=manifest.get('sha256')
    if not isinstance(declared,dict) or set(declared)!=set(REVIEW_FILES+SOURCE_FILES):
        raise ValueError('Exact Native camera and review source set required')
    sources={name:source(attempt,name,declared[name])
             for name in REVIEW_FILES+SOURCE_FILES}
    for name in REVIEW_FILES:
        review=json.loads(sources[name].read_text())
        if (review.get('source_kind')!='original_native' or
                review.get('review_status')!='verified' or
                not review.get('source_basis') or review.get('legal_verdict') is not None):
            raise ValueError('Original parking or beam review is pending: '+name)
    native=rows(sources['native-rows.jsonl'])
    frames=rows(sources['video_frames.jsonl'])
    observed=rows(sources['observed-lamp-review.jsonl'])
    if not all(len(items)==FRAMES for items in (native,frames,observed)):
        raise ValueError('Full 600-frame original source set required')
    assembled=[]
    for i,(n,f,o) in enumerate(zip(native,frames,observed)):
        if (n.get('frame')!=i or f.get('video_frame')!=i or o.get('frame')!=i or
                n.get('native_frame')!=f.get('native_frame') or
                o.get('native_frame')!=f.get('native_frame') or
                n.get('time_s')!=f.get('time_s') or o.get('time_s')!=f.get('time_s')):
            raise ValueError('Original Native/frame/review identities differ')
        camera_frames=f.get('camera_native_frames')
        if not isinstance(camera_frames,dict) or set(camera_frames)!=set(VIEWS):
            raise ValueError('Four original camera frame identities required')
        if n.get('source_cameras')!=camera_frames or any(
                value!=n['native_frame'] for value in camera_frames.values()):
            raise ValueError('Original camera frame join differs')
        review=o.get('beam_pixel_review')
        if not isinstance(review,dict) or review.get('source_path') not in tuple(
                view+'.mkv' for view in VIEWS):
            raise ValueError('Source-bound beam pixel review missing')
        if review.get('source_sha256')!=declared[review['source_path']]:
            raise ValueError('Beam pixel source hash differs')
        row=dict(n)
        row['observed_parking_activity']=o.get('observed_parking_activity')
        row['beam_pixel_review']=review
        assembled.append(row)
    result=measure(assembled,'original_native')
    result['case_id']=manifest['case_id']
    if (result['parked_activity_frames']!=FRAMES or
            result['beam_pixel_reviewed_frames']!=FRAMES or
            result['observed_beam_states']!=[assembled[0]['requested_beam_state']] or
            any(row['ego_speed_mps']>.1 or row['observed_curb_lane_id']!=-2
                for row in assembled)):
        raise ValueError('Original parked and lighted source window incomplete')
    result['beam_aim_elevation_deg_range']=[
        min(row['beam_pixel_review']['aim_elevation_deg'] for row in assembled),
        max(row['beam_pixel_review']['aim_elevation_deg'] for row in assembled)]
    result['relative_intensity_range']=[
        min(row['beam_pixel_review']['relative_intensity'] for row in assembled),
        max(row['beam_pixel_review']['relative_intensity'] for row in assembled)]
    result['source_sha256']=declared
    result['fixed_context']={
        'road_sha256':declared['road.xodr'],
        'ego_blueprint_id':native[0].get('ego_blueprint_id'),
        'curb_lane_id':-2,
        'duration_s':30,
        'rate_hz':20,
        'source_cameras':list(VIEWS)}
    result['review_manifest_sha256']=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if manifest.get('synthetic_cpu_fixture') is True:
        result['original_native_observed']=False
        result['source_kind']='synthetic_cpu_fixture'
    return result
