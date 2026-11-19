"""Distinguish original capture from explicit CPU diagnostic sources."""
import json
from pathlib import Path


ORIGINAL = 'original_carla_actor_and_map_readback'
SYNTHETIC = 'synthetic_native_sample'


def classify(attempt):
    path = Path(attempt) / 'acquisition-provenance.json'
    if not path.exists():
        return ORIGINAL
    receipt = json.loads(path.read_text())
    if receipt != {
        'provenance_kind': 'synthetic_fixture',
        'diagnostic_fixture': True,
        'speed_source': SYNTHETIC,
        'physical_acceptance_claimed': False,
    }:
        raise ValueError('Unrecognized diagnostic acquisition provenance')
    return SYNTHETIC
