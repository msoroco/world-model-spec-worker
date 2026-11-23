"""Convert retained actor poses and extents to source footprint vertices."""
import argparse
import json
import math
from pathlib import Path

from projection_measure import sha, point, PARTS


def vertices(actor):
    if not isinstance(actor, dict) or not isinstance(actor.get('actor_id'), str) or not actor['actor_id']:
        raise ValueError('Retained actor identity missing')
    center = point(actor.get('center_xy_m'))
    extent = point(actor.get('half_extent_xy_m'))
    if min(extent) <= 0:
        raise ValueError('Actor half extent must be positive')
    yaw = actor.get('yaw_deg')
    if not isinstance(yaw, (int, float)) or not math.isfinite(yaw):
        raise ValueError('Actor yaw missing')
    angle = math.radians(yaw)
    cosine, sine = math.cos(angle), math.sin(angle)
    return [[center[0] + dx*cosine - dy*sine,
             center[1] + dx*sine + dy*cosine]
            for dx, dy in ((-extent[0], -extent[1]),
                           (extent[0], -extent[1]),
                           (extent[0], extent[1]),
                           (-extent[0], extent[1]))]


def build(raw_path, curb_path, output_path, expected_frames=600,
          allow_synthetic=False):
    raw_path, curb_path, output_path = map(Path, (raw_path, curb_path, output_path))
    source_kind = 'synthetic_native_sample' if allow_synthetic else 'native'
    raw_rows = [json.loads(line) for line in raw_path.read_text().splitlines()
                if line.strip()]
    if len(raw_rows) != expected_frames or expected_frames < 600:
        raise ValueError('At least 600 complete actor frames required')
    curb_hash = sha(curb_path)
    rows = []
    for frame, raw in enumerate(raw_rows):
        if raw.get('frame') != frame or raw.get('source_kind') != source_kind:
            raise ValueError('Actor frame/source identity mismatch')
        actors = raw.get('actors')
        if not isinstance(actors, dict) or set(actors) != set(PARTS):
            raise ValueError('Vehicle, load and trailer actor inventories required')
        vehicle = actors['vehicle']
        if vehicle is None:
            raise ValueError('Vehicle actor missing')
        vehicle_id = vehicle.get('actor_id')
        participants = {}
        identities = set()
        for part in PARTS:
            actor = actors[part]
            if actor is None:
                participants[part] = None
                continue
            actor_id = actor.get('actor_id')
            if actor_id in identities:
                raise ValueError('Actor identity reused across parts')
            identities.add(actor_id)
            if part != 'vehicle' and actor.get('attached_to') != vehicle_id:
                raise ValueError('Load/trailer association missing')
            participants[part] = {'actor_id': actor_id,
                                  'vertices_xy_m': vertices(actor)}
        rows.append({'frame': frame, 'source_kind': source_kind,
                     'curb_sha256': curb_hash, 'participants': participants})
    output_path.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n'
                                   for row in rows))
    return {'format': 'c229398-source-footprints-v1', 'frames': expected_frames,
            'source_kind': source_kind, 'raw_actors_sha256': sha(raw_path),
            'curb_sha256': curb_hash, 'footprints_sha256': sha(output_path),
            'original_native_observed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw', required=True)
    parser.add_argument('--curb', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--frames', type=int, default=600)
    parser.add_argument('--allow-synthetic', action='store_true')
    args = parser.parse_args()
    print(json.dumps(build(args.raw, args.curb, args.output, args.frames,
                           args.allow_synthetic), indent=2))
