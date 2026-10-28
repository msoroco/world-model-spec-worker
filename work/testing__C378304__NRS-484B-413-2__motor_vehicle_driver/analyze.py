"""Measure actual continuous indicator travel and right-lamp image variation."""
import argparse
import json
import math
import statistics
from pathlib import Path
from source_audit import audit_sources


def course_onset(rows):
    if len(rows) < 8:
        return None
    initial = statistics.median(r['heading_deg'] for r in rows[:5])
    for i in range(5, len(rows)-2):
        values = [abs((rows[j]['heading_deg']-initial+180)%360-180) for j in (i,i+1,i+2)]
        if all(v > 3 for v in values):
            return i
    return None


def traveled(rows, start, end):
    return sum(math.dist(a['position_m'][:2], b['position_m'][:2])
               for a,b in zip(rows[start:end], rows[start+1:end+1]))


def assess(attempt):
    attempt = Path(attempt)
    cfg = json.loads((attempt/'config.json').read_text())
    rows = [json.loads(x) for x in (attempt/'physical_samples.jsonl').read_text().splitlines()]
    sources = audit_sources(attempt, cfg, rows, right_lamp_roi=cfg['right_lamp_roi_px'])
    started = next((i for i,r in enumerate(rows) if r['right_indicator_requested']),None)
    onset = course_onset(rows)
    continuous = started is not None and onset is not None and started < onset and all(
        r['right_indicator_requested'] for r in rows[started:onset+1])
    distance = traveled(rows,started,onset) if continuous else None
    uncertainty = None if distance is None else max(
        math.dist(rows[j-1]['position_m'][:2],rows[j]['position_m'][:2])
        for j in (started,onset) if j>0)
    bracket = None if distance is None else [max(0,distance-uncertainty),distance+uncertainty]
    target=30.48
    relation='unconfirmed' if bracket is None else ('below' if bracket[1]<target else 'above' if bracket[0]>target else 'straddles')
    roi=cfg['right_lamp_roi_px']
    levels=sources['right_lamp_roi_levels']
    fluctuation=[abs(b-a) for a,b in zip(levels,levels[1:])]
    # A threshold is an image-detection engineering condition, never a legal
    # signal-distance tolerance. ROI/framing must be inspected before use.
    visible_flashes=sum(v>12 for v in fluctuation)
    ready=continuous and len(rows)>30 and visible_flashes>=2
    return {'format':'right-signal-distance-capability-v1','case_id':cfg['selected_case_id'],
            'original_source_validation':{k:v for k,v in sources.items() if k!='right_lamp_roi_levels'},
            'requested_signal_distance_m':cfg['case']['variable_assignments']['commanded_signal_distance']['value'],
            'actual_signal_start_index':started,'trajectory_course_change_index':onset,
            'continuous_api_signal_before_course_change':continuous,
            'measured_traveled_distance_m':distance,'measurement_bracket_m':bracket,
            'relation_to_100ft_30_48m':relation,
            'source_roi_px':roi,'source_roi_decoded_frames':len(levels),
            'right_lamp_roi_brightness_mean':statistics.mean(levels) if levels else None,
            'right_lamp_brightness_transitions':visible_flashes,
            'pixel_visibility_verified':False,'district_status':'explicit synthetic context; frontage object requires visual review',
            'decision':'inspect_original_pixels_and_geometry' if ready else 'repair_same_frozen_case_or_reframe_from_source',
            'follow_up_configuration':{'source':'config.json','case_id':cfg['selected_case_id'],
                'preserve_signal_target':True,'review_roi_and_camera_before_new_drive':True},
            'physical_acceptance':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();Path(a.output).write_text(json.dumps(assess(a.attempt),indent=2)+'\n')
