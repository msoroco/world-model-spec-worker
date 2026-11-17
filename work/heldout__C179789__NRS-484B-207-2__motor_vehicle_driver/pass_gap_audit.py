"""Independent signed body-gap audit over retained original pass sources."""
from __future__ import annotations
import json
from pathlib import Path
from overtaken_response import verify_saved_sources


def audit(source_path, frame_map_path, trace_path):
    verified = verify_saved_sources(source_path, frame_map_path, trace_path)
    rows = [json.loads(line) for line in Path(source_path).read_text().splitlines() if line.strip()]
    gaps = []
    for raw, observed in zip(rows, verified['frames']):
        tx, ty = raw['road_tangent_xy']
        rear = min(x * tx + y * ty for x, y in raw['overtaker_corners'])
        front = max(x * tx + y * ty for x, y in raw['subject_corners'])
        gap = rear - front
        if (gap > 0) != observed['body_pass_complete']:
            raise ValueError('Original signed body gap and completion differ')
        gaps.append({'frame': observed['frame'], 'time_s': observed['time_s'],
                     'signed_gap_m': gap, 'body_pass_complete': observed['body_pass_complete']})
    return {'format': 'worker-signed-body-pass-gap-audit',
            'source_sha256': verified['source_sha256'], 'frames': gaps,
            'first_positive_gap_frame': next((row['frame'] for row in gaps if row['signed_gap_m'] > 0), None),
            'physical_acceptance_claimed': False, 'legal_conclusion': None}
