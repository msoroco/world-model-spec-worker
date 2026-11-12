"""Independent original Walk display, governance and pixel-source boundary."""
import hashlib
import json
import tempfile
from pathlib import Path

from measure_walk import analyze, read_rows

CAMERAS=('overview','approach','reference_corner','driver_reference')
SOURCES=('road_geometry.json','native_samples.jsonl','video_frames.jsonl',
         *(camera+'.mkv' for camera in CAMERAS))


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def require(ok,message):
    if not ok:raise ValueError(message)

def validate_review(review,mapping,hashes,signal_id,*,diagnostic=False):
    kind='source_shaped_unit_test' if diagnostic else 'original_native_camera_pixels'
    require(review.get('format')=='c111256-official-walk-review-v1' and
            review.get('source_kind')==kind and review.get('reviewer') and review.get('method') and
            review.get('legal_verdict_claimed') is False and
            review.get('signal_actor_id')==signal_id and
            review.get('source_sha256')==hashes,
            'Walk review identity or source hashes differ')
    require(len(mapping)==480 and len(review.get('observations',[]))==480,
            'Walk review omits an original frame')
    require(set(review.get('camera_rgb_sequence_sha256',{}))==set(CAMERAS) and
            all(isinstance(review['camera_rgb_sequence_sha256'][name],str) and
                len(review['camera_rgb_sequence_sha256'][name])==64 for name in CAMERAS),
            'Walk review omits independent camera decode receipts')
    if not diagnostic:
        require(review.get('official_signal_verified') is True and
                review.get('governance_verified') is True and
                review.get('pedestrian_heading_verified') is True,
                'Official Walk governance or pedestrian heading unverified')
    observed_walk=0
    for index,(frame,item) in enumerate(zip(mapping,review['observations'])):
        require(frame.get('video_frame')==index and
                item.get('video_frame')==index and
                item.get('native_frame')==frame.get('native_frame') and
                item.get('signal_actor_id')==signal_id and
                item.get('camera') in CAMERAS and
                item.get('source_rgb_sha256')==frame.get('source_rgb_sha256',{}).get(item.get('camera')) and
                isinstance(item.get('source_rgb_sha256'),str) and
                len(item['source_rgb_sha256'])==64 and
                item.get('display') in ('Walk','DontWalk','Wait','Unknown') and
                type(item.get('pedestrian_facing_signal')) is bool and
                item.get('method') and item.get('limitations') is not None,
                'Walk pixel/frame or facing observation differs')
        if item['display']=='Walk' and item['pedestrian_facing_signal']:
            observed_walk+=1
            if not diagnostic:
                require(item.get('official_display') is True and
                        item.get('governs_crosswalk') is True and
                        item.get('pedestrian_heading_source')=='native_heading_measured',
                        'Walk frame lacks official governance or measured heading')
        elif not diagnostic:
            require(item.get('official_display') in (True,False) and
                    item.get('governs_crosswalk') in (True,False),
                    'Walk review left official display or governance unknown')
    if not diagnostic:require(observed_walk>0,'No original directed Walk frame observed')
    return {'reviewed_frames':480,'directed_walk_frames':observed_walk,
            'original_walk_verified':not diagnostic}


def audit_original(attempt,review_path):
    attempt=Path(attempt);review_path=Path(review_path)
    geometry=json.loads((attempt/'road_geometry.json').read_text())
    require(geometry.get('synthetic_diagnostic') is False and
            geometry.get('signal_governance_verified') is True and
            geometry.get('walk_pixels_verified') is True,
            'Synthetic or unverified Walk construction cannot prove official display')
    hashes={name:sha(attempt/name) for name in SOURCES}
    mapping=read_rows(attempt/'video_frames.jsonl')
    rows=read_rows(attempt/'native_samples.jsonl')
    require(len(rows)==len(mapping)==480 and all(
        sample.get('display_source')=='original_pixel_audit' and
        sample.get('pedestrian_facing_source')=='native_heading_measured' and
        sample.get('speed_provenance')=='native_measured'
        for sample in rows), 'Original Walk/heading/speed sources absent')
    review=json.loads(review_path.read_text())
    summary=validate_review(review,mapping,hashes,geometry['walk_signal_id'])
    require(all(sample.get('walk_signal_display_observed')==item.get('display') and
                sample.get('pedestrian_facing_signal')==item.get('pedestrian_facing_signal') and
                sample.get('walk_signal_actor_id')==item.get('signal_actor_id')
                for sample,item in zip(rows,review['observations'])),
            'Walk review disagrees with original frame samples')
    from scenario_pipeline.worker_exchange.media import audit as decode
    for camera in CAMERAS:
        with tempfile.TemporaryDirectory() as temporary:
            def check_rgb(frame,camera=camera):
                require(sha_bytes(frame.pixels)==mapping[frame.index]['source_rgb_sha256'][camera],
                        'Decoded original RGB bytes differ from Walk frame map')
            receipt=Path(temporary)/'decode.json'
            decoded=decode(attempt/(camera+'.mkv'),480,receipt=receipt,
                           mapping_sha256=hashes['video_frames.jsonl'],
                           checkers={'original_rgb_sha256':(sha(Path(__file__)),check_rgb)})
            require(decoded.get('rgb_sequence_sha256')==review['camera_rgb_sequence_sha256'][camera] and
                    decoded.get('frames')==480,
                    'Independent Walk camera RGB sequence differs')
    measurement=analyze(attempt)
    require(measurement['synthetic_diagnostic'] is False and
            measurement['walk_display_frames']>=summary['directed_walk_frames'],
            'Original Walk measurement differs from review')
    return {'format':'c111256-original-walk-source-audit-v1',
            'source_sha256':hashes,'review_sha256':sha(review_path),
            'reviewed_frames':480,'directed_walk_frames':summary['directed_walk_frames'],
            'physical_acceptance_claimed':False,'legal_verdict_claimed':False}


def sha_bytes(data):return hashlib.sha256(data).hexdigest()
