"""Bind a reviewed survey to the actual loaded Native OpenDRIVE map.

This is a lazy CARLA interface: the injected world supplies get_map(), name and
OpenDRIVE bytes. Road/highway annotations still require human source review.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('departure_live_construction', HERE / 'construction.py')
construction = importlib.util.module_from_spec(spec)
spec.loader.exec_module(construction)


def verify_live_map(world, survey_path, *, case_id):
    path = Path(survey_path)
    survey = json.loads(path.read_text(encoding='utf-8'))
    live_map = world.get_map()
    if live_map.name != survey.get('map_name'):
        raise ValueError('loaded Native map name differs from reviewed survey')
    source = live_map.to_opendrive()
    if not isinstance(source, str) or not source:
        raise ValueError('loaded Native OpenDRIVE source missing')
    actual_hash = hashlib.sha256(source.encode('utf-8')).hexdigest()
    if actual_hash != survey.get('source_sha256'):
        raise ValueError('loaded Native OpenDRIVE source hash differs')
    plan = construction.build(case_id, survey)
    return {'case_id': case_id, 'loaded_map_name': live_map.name,
            'loaded_opendrive_sha256': actual_hash,
            'survey_packet_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'construction': plan, 'public_highway_source_reviewed': False,
            'physical_turn_verified': False}
