"""Source-bound original activity measurements for the exact business-alley law.

The output is physical observation only. Stop/stand/park, expeditiousness and
ordinance applicability remain independent judgments from retained sources.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path

CASE_PREFIX='testing__C378707__NRS-484B-477-1a__motor_vehicle_driver__'

def _need(value, message):
    if not value:
        raise ValueError(message)

def _number(value, label):
    _need(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value), 'invalid original '+label)
    return float(value)

def measure_original_activity(history: Path, seal: Path, case_id: str, *, diagnostic=False) -> dict:
    """Read sealed 20 Hz activity; nine-frame diagnostics stay explicitly synthetic."""
    _need(case_id.startswith(CASE_PREFIX), 'wrong exact business-alley case')
    history=Path(history);seal=Path(seal)
    _need(history.is_file() and seal.is_file() and not history.is_symlink() and not seal.is_symlink(), 'missing original activity source')
    inventory=json.loads(seal.read_text())
    raw=history.read_bytes()
    expected_count=9 if diagnostic else 900
    expected_format='diagnostic-alley-activity-seal' if diagnostic else 'original-alley-activity-seal'
    expected_source='synthetic_fixture' if diagnostic else 'original_native'
    _need(inventory.get('case_id')==case_id and inventory.get('format')==expected_format, 'original activity identity mismatch')
    _need(inventory.get('history_sha256')==hashlib.sha256(raw).hexdigest(), 'original activity hash changed')
    _need(inventory.get('frame_count')==expected_count and inventory.get('rate_hz')==20, 'incomplete original activity inventory')
    rows=[json.loads(line) for line in raw.splitlines()]
    _need(len(rows)==expected_count, 'incomplete original activity history')
    intervals={key:[] for key in ('halt','passenger_contact','goods_contact','driver_outside','door_open')}
    original_speeds=[];positions=[];business=[];ordinance=[]
    for index,row in enumerate(rows):
        _need(row.get('source_kind')==expected_source and row.get('frame')==index and row.get('case_id')==case_id, 'original activity frame identity mismatch')
        t=_number(row.get('time_s'),'frame time')
        _need(abs(t-index/20)<1e-5, 'original activity time discontinuity')
        speed=_number(row.get('ego_speed_mps'),'vehicle speed')
        _need(speed>=0, 'negative original vehicle speed')
        xy=row.get('ego_xy_m')
        _need(isinstance(xy,list) and len(xy)==2, 'missing original vehicle position')
        xy=[_number(value,'vehicle position') for value in xy]
        for field in ('in_business_alley','ordinance_reviewed_applicable','passenger_contact','goods_contact','driver_in_vehicle','door_open'):
            _need(type(row.get(field)) is bool, 'missing original '+field)
        _need(not (row['passenger_contact'] and row['goods_contact']), 'unreviewed simultaneous passenger and goods activity')
        original_speeds.append(speed);positions.append(xy);business.append(row['in_business_alley']);ordinance.append(row['ordinance_reviewed_applicable'])
        events={'halt':speed<0.1,'passenger_contact':row['passenger_contact'],'goods_contact':row['goods_contact'],'driver_outside':not row['driver_in_vehicle'],'door_open':row['door_open']}
        for key,active in events.items():
            if active: intervals[key].append(index)
    _need(any(business), 'no original business-alley observation')
    def spans(indices):
        if not indices:return []
        runs=[];start=last=indices[0]
        for index in indices[1:]:
            if index!=last+1:runs.append([start/20,(last+1)/20]);start=index
            last=index
        runs.append([start/20,(last+1)/20]);return runs
    return {'format':'diagnostic-alley-activity-measurements' if diagnostic else 'original-alley-activity-measurements','case_id':case_id,'history_sha256':hashlib.sha256(raw).hexdigest(),'frame_count':expected_count,'rate_hz':20,'original_speed_min_mps':min(original_speeds),'original_speed_max_mps':max(original_speeds),'original_start_xy_m':positions[0],'original_end_xy_m':positions[-1],'business_alley_frames':sum(business),'ordinance_applicable_frames':sum(ordinance),'intervals_s':{key:spans(indices) for key,indices in intervals.items()},'legal_conclusion':'unreviewed'}
