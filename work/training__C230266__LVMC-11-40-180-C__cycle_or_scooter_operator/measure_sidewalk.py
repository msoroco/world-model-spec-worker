"""Saved-only C230266 source meter. No controller or legal value is an outcome."""
import json
import math
from pathlib import Path
import struct
from bisect import bisect_left

from audio_source import RATE, load_pcm, validate_source

FRAMES = 600
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def read_rows(root, name):
    path = Path(root)/name
    if not path.is_file():
        raise ValueError('Missing original sidewalk source: '+name)
    return [json.loads(line) for line in path.read_text().splitlines()]


def measure(root, expected_frames=FRAMES):
    root=Path(root)
    audio=validate_source(root,expected_frames)
    actors=read_rows(root,'sidewalk-actors.jsonl')
    mapping=read_rows(root,'video_frames.jsonl')
    images=read_rows(root,'camera-frames.jsonl')
    mic_frames=read_rows(root,'pedestrian-microphone-frames.jsonl')
    if len(actors)!=expected_frames or len(mapping)!=expected_frames or len(images)!=4*expected_frames:
        raise ValueError('Incomplete original rider/pedestrian/video source')
    expected_images={(i,name,mapping[i]['native_frame']) for i in range(expected_frames)
                     for name in CAMERAS}
    if {(r['video_frame'],r['camera'],r['native_frame']) for r in images}!=expected_images:
        raise ValueError('Original camera frame join differs')
    rider_id,ped_id=actors[0]['rider_id'],actors[0]['pedestrian_id']
    if rider_id==ped_id or any(r['pedestrian_id']!=ped_id or r['rider_id']!=rider_id
                              for r in actors):
        raise ValueError('Distinct original participant identities required')
    overlap=ahead=pause=None
    minimum_lateral_gap=math.inf
    for i,(row,frame,mic) in enumerate(zip(actors,mapping,mic_frames)):
        if (row['video_frame']!=i or frame['video_frame']!=i or
                row['native_frame']!=frame['native_frame'] or
                mic['native_frame']!=frame['native_frame'] or
                mic['pedestrian_id']!=ped_id or
                abs(row['time_s']-frame['time_s'])>1e-4 or
                set(frame['camera_native_frames'])!=set(CAMERAS)):
            raise ValueError('Original rider/pedestrian/audio time join differs')
        rider=row['rider_xyz_m'];ped=row['pedestrian_xyz_m']
        re=row['rider_bbox_extent_xyz_m'];pe=row['pedestrian_bbox_extent_xyz_m']
        if not all(math.isfinite(v) for v in (*rider,*ped,*re,*pe)):
            raise ValueError('Nonfinite original sidewalk participant source')
        if not (-6.5<=rider[1]-re[1] and rider[1]+re[1]<=-3.5 and
                -6.5<=ped[1]-pe[1] and ped[1]+pe[1]<=-3.5):
            raise ValueError('Original participant footprint left authored sidewalk')
        rlo,rhi=rider[0]-re[0],rider[0]+re[0]
        plo,phi=ped[0]-pe[0],ped[0]+pe[0]
        if overlap is None and rhi>=plo:overlap=i
        if overlap is not None and ahead is None and rlo>phi:ahead=i
        if rhi>=plo and rlo<=phi:
            gap=max(0,abs(rider[1]-ped[1])-re[1]-pe[1])
            minimum_lateral_gap=min(minimum_lateral_gap,gap)
        velocity=row['rider_velocity_xyz_mps']
        speed=math.sqrt(sum(v*v for v in velocity))
        if speed<=.05 and pause is None:pause=i
    metadata=json.loads((root/'pedestrian-microphone.json').read_text())
    raw=load_pcm(root,metadata)
    samples=struct.unpack('<'+'h'*(len(raw)//2),raw)
    first_pulse=None
    window=RATE//20
    # RMS is an engineering detector only. The microphone/source placement and
    # acoustic identity still require independent original-source review.
    for offset in range(0,len(samples)-window+1,window):
        piece=samples[offset:offset+window]
        rms=math.sqrt(sum(v*v for v in piece)/len(piece))/32768
        if rms>=.15:
            first_pulse=offset//window
            break
    # The first copied chunk has an upper-bound arrival timestamp. ALSA/ffmpeg
    # buffering can shift the actual onset; report a conservative diagnostic
    # order only when separated by more than one second of Native frames.
    if first_pulse is None:
        pulse_frame=None
    else:
        copied_chunk_duration_ns=8192*1_000_000_000//(RATE*2)
        pulse_time_ns=(metadata['first_chunk_monotonic_ns']-
                       copied_chunk_duration_ns+
                       first_pulse*window*1_000_000_000//RATE)
        pulse_frame=bisect_left([r['monotonic_ns'] for r in mic_frames],pulse_time_ns)
    pulse_before_pass=(pulse_frame is not None and overlap is not None and
                       pulse_frame+20<overlap)
    return {'source_kind':metadata['source_kind'], 'frames':expected_frames,
            'rider_id':rider_id,'pedestrian_id':ped_id,
            'first_footprint_overlap_frame':overlap,
            'first_full_ahead_frame':ahead,
            'first_rider_pause_frame':pause,
            'first_microphone_pulse_window':first_pulse,
            'first_microphone_pulse_video_frame_approx':pulse_frame,
            'pulse_precedes_overlap_with_engineering_margin':pulse_before_pass,
            'audio_timing_conservative_margin_s':1.0,
            'minimum_lateral_footprint_gap_m':None if math.isinf(minimum_lateral_gap)
                                                  else round(minimum_lateral_gap,4),
            'microphone_pcm_sha256':audio['pcm_sha256'],
            'engineering_audio_rms_threshold':.15,
            'microphone_placement_verified':False,
            'audible_signal_identity_verified':False,
            'legal_right_of_way_verdict':None,
            'original_physical_completion_verified':False}
