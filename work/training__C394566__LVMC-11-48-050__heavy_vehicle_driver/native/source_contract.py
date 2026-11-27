"""Join original route telemetry to cited non-visual facts without legal inference."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

COUNT = 600
REQUIRED_FACT_SOURCES = ('weight', 'district', 'truck_route', 'civil_clock', 'permit')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path: Path) -> list[dict]:
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    values = [json.loads(line) for line in path.read_text().splitlines()]
    if len(values) != COUNT:
        raise ValueError('Original route trace requires 600 frame rows')
    return values


def load(attempt: Path, case_id: str) -> dict:
    attempt = Path(attempt)
    for name in ('authority-context.json', 'capture-seal.json'):
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    context = json.loads((attempt / 'authority-context.json').read_text())
    seal = json.loads((attempt / 'capture-seal.json').read_text())
    if context.get('case_id') != case_id or context.get('source_kind') not in ('synthetic_native_sample', 'original_review_packet'):
        raise ValueError('Source context case or kind differs')
    terms = ('ru.truck', 'ru.commercial_motor_vehicle', 'kin.extent', 'st.roadway', 'dev.regulatory_sign', 'env.civil_time', 'drv.condition_in_effect', 'kin.velocity')
    if any(not isinstance(context.get(term), dict) or not context[term] for term in terms):
        raise ValueError('Missing authored instance context')
    refs = context.get('authority_refs')
    if not isinstance(refs, dict) or set(refs) != set(REQUIRED_FACT_SOURCES):
        raise ValueError('Every factual authority needs an exact source reference')
    for key, ref in refs.items():
        if not isinstance(ref, dict) or not isinstance(ref.get('path'), str) or not isinstance(ref.get('sha256'), str):
            raise ValueError('Malformed authority source reference: ' + key)
        path = attempt / ref['path']
        if path.resolve().parent != attempt.resolve() or not path.is_file():
            raise ValueError('Missing required source: ' + ref['path'])
        if sha(path) != ref['sha256']:
            raise ValueError('Changed authority source: ' + key)
    rows = _rows(attempt / 'original-route-rows.jsonl')
    frames = _rows(attempt / 'video_frames.jsonl')
    if seal.get('case_id') != case_id:
        raise ValueError('Capture seal case differs')
    protected = ('authority-context.json', 'original-route-rows.jsonl', 'video_frames.jsonl')
    hashes = seal.get('sha256')
    if not isinstance(hashes, dict) or any(hashes.get(name) != sha(attempt / name) for name in protected):
        raise ValueError('Original source seal differs')
    last_time = -math.inf
    for index, (row, frame) in enumerate(zip(rows, frames)):
        if row.get('case_id') != case_id or row.get('source_kind') != 'original_native_pose':
            raise ValueError('Original route row identity differs')
        if row.get('video_frame') != index or frame.get('video_frame') != index or row.get('native_frame') != frame.get('native_frame'):
            raise ValueError('Native route/frame join differs')
        time_s = row.get('time_s')
        if type(time_s) not in (int, float) or not math.isfinite(time_s) or time_s <= last_time or abs(time_s - frame.get('time_s', -1)) > .001:
            raise ValueError('Native time join differs')
        last_time = time_s
        if type(row.get('road_id')) is not int or type(row.get('ego_speed_mps')) not in (int, float) or not math.isfinite(row['ego_speed_mps']) or row['ego_speed_mps'] < 0:
            raise ValueError('Original road or movement source differs')
        if any(type(row.get(key)) not in (int, float) or not math.isfinite(row[key]) for key in ('ego_x_m', 'ego_y_m')):
            raise ValueError('Original position source differs')
        extent = row.get('vehicle_half_extent_m')
        if not isinstance(extent, list) or len(extent) != 2 or any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0 for value in extent):
            raise ValueError('Original body extent source differs')
    return {'format': 'c394566-source-join-v1', 'case_id': case_id,
            'source_kind': context['source_kind'], 'context': context,
            'rows': rows, 'frame_count': COUNT,
            'source_hashes': {name: sha(attempt / name) for name in protected},
            'authority_hashes': {key: ref['sha256'] for key, ref in refs.items()},
            'original_authority_reviewed': False, 'physical_or_legal_accepted': False}
