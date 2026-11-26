"""Source-bound right-turn completion criterion for original Native histories."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


REQUIRED = ('road_geometry.json', 'body_history.jsonl', 'video_frames.jsonl',
            'native_samples.jsonl')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def assess(attempt: Path) -> dict:
    attempt = Path(attempt)
    available = {name: sha(attempt / name) for name in REQUIRED if (attempt / name).is_file()}
    missing = [name for name in REQUIRED if name not in available]
    base = {'format': 'c42387-physical-right-turn-assessment-v1',
            'source_hashes': available, 'missing_evidence': missing,
            'engineering_criterion_not_legal': True,
            'physical_acceptance_claimed': False, 'legal_verdict': None}
    if missing:
        return {**base, 'status': 'unverified', 'observed': {}}
    try:
        geometry = json.loads((attempt / 'road_geometry.json').read_text())
        body, mapping, samples = (rows(attempt / name) for name in REQUIRED[1:])
        if any(len(source) != 600 for source in (body, mapping, samples)):
            raise ValueError('Incomplete original right-turn interval')
        approach = geometry['approach_road_id']
        destination = geometry['destination_road_id']
        if type(approach) is not int or type(destination) is not int or approach == destination:
            raise ValueError('Native approach/destination road identity missing')
        road_ids = []
        headings = []
        centers = []
        for index, (b, m, s) in enumerate(zip(body, mapping, samples)):
            frame = m.get('native_frame')
            if m.get('video_frame') != index or b.get('frame') != frame or s.get('native_frame') != frame:
                raise ValueError('Native body/frame identity join differs')
            if abs(float(b['time_s']) - float(m['time_s'])) > 1e-4 or \
                    abs(float(s['time_s']) - float(m['time_s'])) > 1e-4:
                raise ValueError('Native body/frame timestamp join differs')
            vertices = b.get('body_vertices_m')
            if not isinstance(vertices, list) or len(vertices) < 4 or \
                    any(not isinstance(v, list) or len(v) != 3 or
                        not all(type(a) in (int, float) and math.isfinite(a) for a in v)
                        for v in vertices):
                raise ValueError('Full original Native body geometry missing')
            road_id = b.get('road_id')
            if road_id != s.get('road_id') or type(road_id) is not int:
                raise ValueError('Original Native road identity missing')
            road_ids.append(road_id)
            heading = s.get('ego_heading_deg')
            if type(heading) not in (int, float) or not math.isfinite(heading):
                raise ValueError('Original Native heading missing')
            headings.append(float(heading))
            centers.append([sum(v[axis] for v in vertices) / len(vertices)
                            for axis in (0, 1)])
        path_m = sum(math.dist(a, b) for a, b in zip(centers, centers[1:]))
        heading_change = (headings[-1] - headings[0] + 180) % 360 - 180
        first_destination = next((i for i, road in enumerate(road_ids)
                                  if i > 0 and road == destination), None)
        met = (road_ids[0] == approach and first_destination is not None and
               road_ids[-1] == destination and path_m >= 10 and
               -120 <= heading_change <= -60)
        return {**base, 'status': 'met' if met else 'not_met',
                'observed': {'start_road_id': road_ids[0],
                    'destination_road_id': destination,
                    'first_destination_sample': first_destination,
                    'last_road_id': road_ids[-1],
                    'sampled_body_center_path_m': round(path_m, 5),
                    'heading_change_deg': round(heading_change, 5),
                    'sample_count': 600},
                'engineering_completion': 'ordered road transition, at least 10 m sampled body movement and 60–120 degree clockwise heading change; not a statutory rule'}
    except (KeyError, TypeError, ValueError, IndexError, OSError) as exc:
        return {**base, 'status': 'unverified', 'observed': {},
                'source_error': str(exc)}
