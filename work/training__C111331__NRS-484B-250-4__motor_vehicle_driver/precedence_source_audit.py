"""Audit three authored precedence requests; no physical/legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path

NAMES=('prior_stop_yield','prior_stop_no_yield','inside_vehicle_no_yield')
FIXED=('other_center_xy_m','other_phase_requested','signal_id',
       'signal_installed_requested','signal_uncovered_requested',
       'signal_display_requested','marked_stop_line_x_m',
       'near_side_crosswalk_x_m','intersection_entry_x_m')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]


def audit(root):
    root=Path(root)
    streams={name:rows(root/name/'sources/vehicle-history.jsonl') for name in NAMES}
    if any(len(s)!=600 for s in streams.values()):
        raise ValueError('Incomplete 600-frame precedence request')
    reference=streams[NAMES[0]]
    entries={};stops={};other_entry=None;other_clear=None;other_stop=None
    for i in range(600):
        row=reference[i]
        if row['frame']!=i or row['time_s']!=i/20:
            raise ValueError('Precedence frame/time source differs')
        if i and row['other_center_xy_m']==reference[i-1]['other_center_xy_m'] and row['other_center_xy_m'][1]+2 < -26 and other_stop is None:
            other_stop=i
        if row['other_center_xy_m'][1]+2>=-20 and other_entry is None:other_entry=i
        if row['other_center_xy_m'][1]-2>20 and other_clear is None:other_clear=i
        for name,stream in streams.items():
            current=stream[i]
            if any(current[key]!=row[key] for key in FIXED):
                raise ValueError('Fixed precedence construction condition differs')
            if current['frame']!=i or current['time_s']!=i/20:
                raise ValueError('Precedence case time join differs')
            if i and current['ego_center_xy_m']==stream[i-1]['ego_center_xy_m'] and current['ego_front_x_m'] < -26:
                stops[name]=stops.get(name,0)+1
            if current['ego_front_x_m']>=-20 and name not in entries:entries[name]=i
    if set(entries)!=set(NAMES) or set(stops)!=set(NAMES) or other_stop is None or other_entry is None or other_clear is None:
        raise ValueError('Precedence stop/entry source incomplete')
    if not (other_stop<entries['prior_stop_no_yield']<other_entry<entries['inside_vehicle_no_yield']<other_clear<entries['prior_stop_yield']):
        raise ValueError('Requested prior-stop/inside-yield ordering differs')
    return {'format':'c111331-requested-precedence-audit-v1',
            'cases':list(NAMES),'ego_entry_frames':entries,'ego_pre_line_stationary_frames':stops,
            'other_stop_frame':other_stop,'other_entry_frame':other_entry,
            'other_clear_frame':other_clear,
            'source_sha256':{name:sha(root/name/'sources/vehicle-history.jsonl') for name in NAMES},
            'fixed_conditions_checked':True,'requested_difference_checked':True,
            'original_native_observed':False,'actual_pixels_reviewed':False,'legal_verdict':None}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();Path(a.output).write_text(json.dumps(audit(a.root),indent=2)+'\n')
