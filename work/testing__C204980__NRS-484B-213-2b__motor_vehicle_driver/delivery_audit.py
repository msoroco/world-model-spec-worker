"""Independent source-bound audit for an original railroad crossing delivery."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from analysis import ASSIGNMENT, CAMERAS, load_json, load_rows, source_inventory


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def within(root, relative):
    root = Path(root).resolve(strict=True)
    path = (root/relative).resolve(strict=True)
    require(path.is_relative_to(root) and path.is_file(), 'source path escapes original attempt')
    return path


def inspect_original(attempt, case_id, *, diagnostic_protocol=False):
    attempt = Path(attempt).resolve(strict=True)
    require(case_id.startswith(ASSIGNMENT+'__'), 'case identity mismatch')
    hashes, rows, scene, source_manifest = source_inventory(attempt, case_id, 900)
    context = load_json(attempt/'rail-context.json')
    if not diagnostic_protocol:
        require(context.get('diagnostic_fixture') is False,
                'diagnostic fixture cannot satisfy independent delivery audit')
    trace = load_rows(attempt/'trace.jsonl')
    frame_map = load_rows(attempt/'video_frames.jsonl')
    require(len(trace) == len(frame_map) == 900 and all(
        trace[i]['frame'] == frame_map[i]['carla_frame'] == rows[i]['original_frame'] and
        abs(trace[i]['time_s']-frame_map[i]['time_s']) <= 1e-6
        for i in range(900)), 'original trace/camera time join invalid')
    for camera in CAMERAS:
        path = within(attempt,camera+'.mkv')
        probe = subprocess.run(['ffprobe','-v','error','-select_streams','v:0',
                                '-count_frames','-show_entries','stream=nb_read_frames',
                                '-of','default=nw=1:nk=1',str(path)],
                               capture_output=True,text=True,check=True)
        require(probe.stdout.strip() == '900', 'full video frame count differs: '+camera)
    return {'case_id':case_id,'source_manifest_sha256':sha(source_manifest),
            'source_hashes':hashes,'frame_count':900,'camera_frame_map_sha256':sha(attempt/'video_frames.jsonl'),
            'trace_sha256':sha(attempt/'trace.jsonl'),
            'diagnostic_protocol':diagnostic_protocol}


def audit(attempt, case_id, processing_path, pixel_review_path):
    attempt = Path(attempt).resolve(strict=True)
    checked = inspect_original(attempt,case_id)
    processing = load_json(processing_path)
    require(processing.get('format') == 'worker-saved-processing' and
            processing.get('case_id') == case_id and processing.get('passed') is True and
            processing.get('recorded_only') is True and processing.get('originals_preserved') is True,
            'saved-only processing receipt missing or incomplete')
    original_hashes = processing.get('original_source_hashes',{})
    require(set(checked['source_hashes']) <= set(original_hashes),
            'saved processing omitted original source inventory')
    for relative,digest in original_hashes.items():
        require(sha(within(attempt,relative)) == digest,
                'saved original changed: '+relative)
    saved_result = Path(processing.get('result',''))
    require(saved_result.is_file() and sha(saved_result) == processing.get('result_sha256'),
            'saved result hash differs')
    result = load_json(saved_result)
    require(result.get('case_id') == case_id and result.get('maneuver_completed') is True and
            result.get('physical_checks',{}).get('maneuver',{}).get('status') == 'met' and
            result.get('provenance_kind') == 'native' and result.get('diagnostic_fixture') is False,
            'original physical completion unverified')
    review = load_json(pixel_review_path)
    require(review.get('case_id') == case_id and review.get('actual_pixels_reviewed') is True and
            review.get('frame_map_sha256') == checked['camera_frame_map_sha256'] and
            set(review.get('views',[])) == set(CAMERAS) and
            all(review.get('video_sha256',{}).get(camera) == checked['source_hashes'][camera+'.mkv']
                for camera in CAMERAS), 'actual original pixel review missing or stale')
    require(all(review.get(key) for key in ('reviewer','method','observations')),
            'pixel reviewer or observations missing')
    require(processing.get('final_video_checks',{}).get('frames') == 900,
            'full promoted video decode missing')
    return {'format':'worker-c204980-independent-delivery-audit-v1',
            'case_id':case_id,'passed':True,'checks':['native_source','all_participants',
            'time_join','full_video_decode','actual_pixels','physical_completion'],
            'original_source_manifest_sha256':checked['source_manifest_sha256'],
            'processing_sha256':sha(processing_path),'pixel_review_sha256':sha(pixel_review_path),
            'legal_judgment':'unresolved'}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--case',required=True)
    p.add_argument('--attempt',required=True)
    p.add_argument('--processing',required=True)
    p.add_argument('--pixel-review',required=True)
    a=p.parse_args()
    print(json.dumps(audit(a.attempt,a.case,a.processing,a.pixel_review),sort_keys=True))


if __name__=='__main__':
    main()
