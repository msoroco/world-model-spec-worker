"""Exercise pinned Core atom coverage against source-shaped diagnostic facts.

This projection tests the semantic shape required of a later native conversion.
It does not claim the synthetic packet is an original reviewed intersection.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from signal_crossing import validate_source_packet


REQUIRED = ('dev.traffic_signal', 'st.intersection', 'st.lane_enters')
INDICATIONS = {'Red': 'circular_red', 'Yellow': 'circular_yellow',
               'Green': 'circular_green', 'Off': 'dark'}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project_diagnostic(attempt: Path) -> list[dict]:
    """Project only fields backed by the explicit synthetic packet/history."""
    attempt = Path(attempt)
    map_bytes = (attempt / 'map.xodr').read_bytes()
    review_bytes = (attempt / 'review.json').read_bytes()
    packet = validate_source_packet(
        json.loads((attempt / 'source-packet.json').read_text()), map_bytes, review_bytes)
    signal_packet = json.loads((attempt / 'signal-packet.json').read_text())
    history_path = attempt / 'signal-history.json'
    if signal_packet.get('payload_sha256') != _sha(history_path):
        raise ValueError('diagnostic signal history hash mismatch')
    history = json.loads(history_path.read_text())
    if history.get('crossing_id') != packet['crossing_id'] or len(history.get('frames', [])) != 6:
        raise ValueError('diagnostic crossing history mismatch')
    if history.get('crossing_bounds_xy_m') != packet['crossing_bounds_xy_m']:
        raise ValueError('diagnostic crossing boundary mismatch')
    box = packet['crossing_bounds_xy_m']
    boundary = [[box[0], box[1]], [box[2], box[1]],
                [box[2], box[3]], [box[0], box[3]]]
    scenes = []
    for row in history['frames']:
        indication = INDICATIONS.get(row.get('ego_light_readback'))
        if indication is None:
            raise ValueError('diagnostic live signal state missing')
        scenes.append({
            't': row['time_s'], 'subject': 11, 'users': [],
            'structures': [
                {'id': 1, 'kind': 'lane', 'lane': {'enters_intersection': 3}},
                {'id': 3, 'kind': 'intersection', 'boundary': boundary}],
            'devices': [{'id': packet['official_device_inventory'][0]['id'],
                         'kind': 'traffic_signal', 'indications': [indication],
                         'governs': [1]}],
        })
    return scenes


def prove(attempt: Path) -> dict:
    from traffic_spec_adapter.atom_contract import required_coverage
    scenes = project_diagnostic(attempt)
    capability = {'atoms': {atom: 'exact' for atom in REQUIRED}}
    positive = required_coverage(REQUIRED, capability, scenes)
    if not positive['passed']:
        raise ValueError('Source-shaped Core diagnostic does not cover required atoms')
    negative = {}
    for atom in REQUIRED:
        changed = copy.deepcopy(scenes)
        for scene in changed:
            if atom == 'dev.traffic_signal':
                scene['devices'][0]['indications'] = []
            elif atom == 'st.intersection':
                scene['structures'] = [r for r in scene['structures'] if r['kind'] != 'intersection']
            else:
                scene['structures'][0]['lane'].pop('enters_intersection')
        result = required_coverage(REQUIRED, capability, changed)
        if atom not in result['missing']:
            raise ValueError('Core accepted missing ' + atom)
        negative[atom] = result['atoms'][atom]['reason']
    return {'diagnostic_fixture': True, 'source_packet_sha256': _sha(Path(attempt) / 'source-packet.json'),
            'signal_history_sha256': _sha(Path(attempt) / 'signal-history.json'),
            'frames': len(scenes), 'positive': positive, 'negative': negative,
            'original_site_reviewed': False, 'native_conversion_proven': False,
            'physical_delivery_proven': False}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prove(args.attempt), sort_keys=True))
