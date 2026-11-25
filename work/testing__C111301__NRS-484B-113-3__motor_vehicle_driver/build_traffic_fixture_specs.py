"""Derive explicitly synthetic moving-vehicle CPU fixtures from diagnostic sources.

These sources only exercise saved processing. They are never original evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def build():
    for kind in ('yield', 'continue'):
        pedestrian = json.loads((HERE / ('diagnostic-pedestrian_' + kind + '-spec.json')).read_text())
        source = json.loads(json.dumps(pedestrian).replace('pedestrian', 'traffic'))
        files = source['files']
        packet = json.loads(files['map.json'])
        packet['traffic_blueprint_id'] = 'vehicle.audi.a2'
        packet.pop('traffic_radius_m')
        packet['traffic_half_width_m'] = 0.9
        files['map.json'] = json.dumps(packet, separators=(',', ':')) + '\n'
        acquisition = json.loads(files['acquisition.json'])
        acquisition['map_packet']['sha256'] = sha(files['map.json'])
        acquisition['telemetry']['sha256'] = sha(files['telemetry.json'])
        acquisition['frame_map']['sha256'] = sha(files['frame-map.json'])
        acquisition['trace']['sha256'] = sha(files['trace.jsonl'])
        acquisition['video_frame_map']['sha256'] = sha(files['video_frames.jsonl'])
        acquisition['source_id'] = 'diagnostic:traffic_' + kind
        files['acquisition.json'] = json.dumps(acquisition, indent=2) + '\n'
        suffix = 'traffic_' + kind
        spec = HERE / ('diagnostic-' + suffix + '-spec.json')
        spec.write_text(json.dumps(source, separators=(',', ':')) + '\n')
        if spec.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('traffic CPU fixture spec exceeds work file cap')
        recipe = json.loads((HERE / ('diagnostic-pedestrian_' + kind + '-recipe.json')).read_text())
        recipe['generator'] = {'source': 'work/' + AID + '/' + spec.name,
                               'sha256': hashlib.sha256(spec.read_bytes()).hexdigest()}
        (HERE / ('diagnostic-' + suffix + '-recipe.json')).write_text(json.dumps(recipe, indent=2) + '\n')
    return ['traffic_yield', 'traffic_continue']


if __name__ == '__main__':
    print(json.dumps(build()))
