"""Independent original-source acceptance boundary for C110919 judgment sweeps."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
CAMERAS=('overview','approach','reference_corner','driver_reference')
MANIFESTS={'C110919-right-of-way':'update041-traffic-timing-sweep-manifest.json',
           'C110919-extreme-right':'update052-extreme-right-sweep-manifest.json'}
sys.path.insert(0,str(HERE/'native'))
from extreme_right_sweep import measure_approach

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())
def rows(path):return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
def require(ok,message):
    if not ok:raise ValueError(message)
def frames(path):
    done=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-count_frames',
        '-show_entries','stream=nb_read_frames','-of','default=nw=1:nk=1',str(path)],
        capture_output=True,text=True,check=True)
    return int(done.stdout.strip())

def audit(sweep_id,case_id,construction_sha256,attempt,processing,*,diagnostic,source_review=None):
    require(sweep_id in MANIFESTS,'Unknown judgment sweep')
    manifest=read(HERE/MANIFESTS[sweep_id])
    entry=next((e for e in manifest['cases'] if e['case_id']==case_id),None)
    require(entry is not None and entry['construction_sha256']==construction_sha256 and
            sha(HERE/entry['construction'])==construction_sha256,
            'Exact sweep case or construction source differs')
    attempt=Path(attempt).resolve();processing=Path(processing).resolve()
    require(attempt.is_dir() and processing.is_file() and ROOT in attempt.parents,
            'Original attempt or saved processing path missing')
    saved=read(processing)
    require(saved.get('case_id')==case_id and saved.get('candidate_id')=='primary' and
            saved.get('passed') is True and saved.get('originals_preserved') is True and
            saved.get('timestamp_joins',{}).get('passed') is True and
            saved.get('physical_acceptance_claimed') is False and
            saved.get('legal_acceptance_claimed') is False,
            'Saved source-chain processing incomplete')
    names=('native_samples.jsonl','road_geometry.json','video_frames.jsonl',
           'capture/evidence.jsonl','body_history.jsonl','trace.jsonl',
           *(camera+'.mkv' for camera in CAMERAS))
    hashes={}
    for name in names:
        source=attempt/name
        require(source.is_file(),'Missing original source: '+name)
        hashes[name]=sha(source)
        require(saved.get('original_source_hashes',{}).get(name)==hashes[name],
                'Saved original source hash differs: '+name)
    mapping=rows(attempt/'video_frames.jsonl')
    native=rows(attempt/'native_samples.jsonl')
    evidence=rows(attempt/'capture/evidence.jsonl')
    history=rows(attempt/'body_history.jsonl')
    require(len(mapping)==len(native)==len(evidence)==len(history)==480,
            'Original frame or participant stream incomplete')
    for index,(frame,sample,capture,body) in enumerate(zip(mapping,native,evidence,history)):
        require(frame['video_frame']==index and
                frame['native_frame']==sample['native_frame']==capture['original_frame']==body['frame'] and
                abs(frame['time_s']-sample['time_s'])<=1e-4 and
                {tuple(p) for p in sample['native_body_xy_m']}==
                {tuple(p[:2]) for p in body['body_vertices_m']}==
                {tuple(p[:2]) for p in capture['ego']['body_vertices_m']},
                'Original Native full-body/frame/time join differs')
    counts={camera:frames(attempt/(camera+'.mkv')) for camera in CAMERAS}
    require(set(counts.values())=={480},'Four source cameras lack all frames')
    result=read(attempt/'result.json')
    report=read(attempt/'analysis-report.json')
    require(saved.get('result_sha256')==sha(attempt/'result.json') and
            result.get('case_id')==case_id and result.get('accepted') is False and
            result.get('legal_verdict_claimed') is False,
            'Saved result changed or asserts legal acceptance')
    geometry=read(attempt/'road_geometry.json')
    require(geometry.get('signal_actor_id') and geometry.get('cross_traffic_signal_actor_id') and
            geometry.get('lanes',{}).get('west_traffic_right',{}).get('lane_id')==-1 and
            all(row.get('signal_state_observed') in ('Red','TrafficLightState.Red') and
                row.get('other_traffic_signal_state_observed') in ('Green','TrafficLightState.Green')
                for row in native),
            'Original governing or directed traffic signal and lane source differs')
    if sweep_id=='C110919-extreme-right':
        lateral=measure_approach(native,geometry)
        require(report['measurements']['extreme_right_lateral_sweep']['value']==lateral and
                result['realized_observables']['full_body_lateral_position_in_highway']['value']==
                    lateral['minimum_right_edge_clearance_m'] and
                all(row.get('lateral_right_offset_m')==entry['authored_lateral_right_offset_m']
                    for row in native),
                'Original lateral body, lane or selected offset differs')
    else:
        timing=report['measurements']['traffic_timing_sweep']['value']
        require(timing['authored_launch_frame']==entry['authored_traffic_launch_frame'] and
                result['realized_observables']['ego_entry_relative_to_signal_directed_traffic']['value']==
                    timing['ego_minus_traffic_entry_s'] and
                all(row.get('traffic_launch_frame')==entry['authored_traffic_launch_frame']
                    for row in native),
                'Original traffic timing or selected launch differs')
    synthetic=any(row.get('synthetic_diagnostic') is True or
                  row.get('speed_provenance')=='synthetic_native_sample' for row in native)
    if diagnostic:
        require(synthetic and result.get('provenance_kind')=='synthetic_local_diagnostic' and
                result.get('maneuver_completed') is False,
                'Diagnostic source attempted physical promotion')
        return {'case_id':case_id,'sweep_id':sweep_id,'source_shape_passed':True,
                'passed':False,'source_sha256':hashes,'source_frame_counts':counts,
                'physical_or_legal_acceptance_claimed':False}
    require(not synthetic and result.get('provenance_kind')=='native' and
            result.get('maneuver_completed') is True and source_review is not None,
            'Original Native motion or independent source review missing')
    source_review=Path(source_review).resolve()
    require((ROOT/'state/operations').resolve() in source_review.parents,
            'Original review must be retained under local operations')
    review=read(source_review)
    sys.path.insert(0,str(ROOT/'runtime/pipeline'))
    from scenario_pipeline.worker_exchange.media import audit as decode
    decoded={name:decode(attempt/(name+'.mkv'),480,
                         mapping_sha256=hashes['video_frames.jsonl']) for name in CAMERAS}
    views=review.get('views',{})
    require(set(views)==set(CAMERAS) and all(
        views[name].get('video_sha256')==hashes[name+'.mkv'] and
        views[name].get('rgb_sequence_sha256')==decoded[name]['rgb_sequence_sha256'] and
        views[name].get('reviewed_frame_ids')==list(range(480)) and
        views[name].get('limitations') is not None for name in CAMERAS),
        'Original four-camera full pixel review missing')
    require(review.get('source_kind')=='original_native_map_signal_actor_pixels' and
            review.get('case_id')==case_id and review.get('source_sha256')==hashes and
            review.get('reviewer') and review.get('method') and
            review.get('signal_governs_ego') is True and
            review.get('stop_reference_confirmed') is True and
            review.get('pedestrians_and_cross_traffic_reviewed') is True and
            review.get('native_owner_released') is True and
            review.get('legal_verdict_claimed') is False and
            (review.get('native_full_body_lane_and_highway_reviewed') is True
             if sweep_id=='C110919-extreme-right' else
             review.get('directed_traffic_conflict_timing_reviewed') is True),
            'Original actor, signal, lane or conflict review incomplete')
    return {'case_id':case_id,'sweep_id':sweep_id,'source_shape_passed':True,
            'passed':True,'source_sha256':hashes,'source_frame_counts':counts,
            'source_review_sha256':sha(source_review),'legal_verdict_claimed':False}
