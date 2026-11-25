"""Independent original-source comparison across three towed spacing samples."""
import hashlib
import json
from pathlib import Path

from towing_comparison import COMMON, SOURCES, context, rows, sha


def audit(roots):
    roots = [Path(root) for root in roots]
    if len(roots) != 3:
        raise ValueError('Three exact sweep sources required')
    contexts = [context(root) for root in roots]
    for other in contexts[1:]:
        if any(other.get(name) != contexts[0].get(name) for name in COMMON + SOURCES):
            raise ValueError('Fixed original highway context changed')
    histories = [rows(root / 'caravan_history.jsonl') for root in roots]
    if any(len(history) != 900 for history in histories):
        raise ValueError('Full 900-frame sweep histories required')
    design = [sha(root / 'towing_design_source.txt') for root in roots]
    if len(set(design)) != 1:
        raise ValueError('Towing design source changed')
    links = [sha(root / 'towing-relationship.json') for root in roots]
    if len(set(links)) != 1:
        raise ValueError('Towing relationship source changed')
    opening = [[], [], []]
    for frame_index, group in enumerate(zip(*histories)):
        first = group[0]
        for case_index, row in enumerate(group):
            if (row['frame'] != first['frame'] or row['frame'] != frame_index + 100
                    or row['time_s'] != first['time_s'] or row['road_id'] != first['road_id']):
                raise ValueError('Original frame or road join changed')
            if row.get('towing_relationship') != {'drawing_actor_id': 1, 'drawn_actor_id': 8}:
                raise ValueError('Original towing link changed')
            units = row.get('drawn_units', [])
            if len(units) != 1 or units[0].get('actor_id') != 8:
                raise ValueError('Original drawn body changed')
            if (row['caravan_members'][0] != first['caravan_members'][0]
                    or row['drawn_units'] != first['drawn_units']):
                raise ValueError('Fixed drawing combination changed')
            if len(row['caravan_members']) != 3:
                raise ValueError('Caravan member inventory changed')
            rear = row['caravan_members'][1]['body_vertices_xy_m']
            front = row['caravan_members'][0]['body_vertices_xy_m']
            opening[case_index].append(min(v[0] for v in rear) - max(v[0] for v in front))
    measured = [min(values) for values in opening]
    if not (measured[0] < measured[2] < measured[1]):
        raise ValueError('Declared spacing order differs from original bodies')
    return {'format': 'worker-c160013-towing-sweep-comparison',
            'case_ids': [f'caravan_spacing_towed_physical-{i:04d}' for i in range(3)],
            'original_frames_per_case': 900,
            'fixed_context_source_hashes': {name: contexts[0][name]['sha256'] for name in SOURCES},
            'towing_design_sha256': design[0], 'towing_relationship_sha256': links[0],
            'history_sha256': [sha(root / 'caravan_history.jsonl') for root in roots],
            'measured_minimum_openings_m': measured,
            'declared_differences': ['caravan member spacing', 'entrant approach position'],
            'without_danger_judgment': 'unresolved',
            'physical_acceptance_claimed': False}
