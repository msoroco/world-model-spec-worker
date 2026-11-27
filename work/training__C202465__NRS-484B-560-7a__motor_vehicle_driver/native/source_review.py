"""Require separately reviewed original railroad geometry before Native mutation."""
import hashlib
import json
from pathlib import Path

ROLES = ('rail-geometry', 'opposite-space', 'undercarriage-grade')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(review_dir, road_sha256, *, diagnostic_fixture=False):
    root = Path(review_dir).resolve()
    records = {}
    for role in ROLES:
        path = root / (role + '.json')
        source = root / (role + '.source.txt')
        if not path.is_file() or not source.is_file():
            raise ValueError('Original reviewed rail source missing: ' + role)
        row = json.loads(path.read_text())
        if (row.get('role') != role or row.get('road_sha256') != road_sha256
                or row.get('source_sha256') != sha(source)
                or row.get('review_status') != ('schema_only' if diagnostic_fixture else 'independently_reviewed')
                or row.get('provenance_kind') != ('synthetic_fixture' if diagnostic_fixture else 'original_native')
                or not row.get('reviewer_id')):
            raise ValueError('Original reviewed rail source differs: ' + role)
        records[role] = row
    geometry = records['rail-geometry']
    if (geometry.get('crossing_kind') != 'at_grade'
            or not isinstance(geometry.get('entry_rail_x_m'), (int, float))
            or not isinstance(geometry.get('clearance_reference_rail_x_m'), (int, float))
            or geometry['clearance_reference_rail_x_m'] <= geometry['entry_rail_x_m']):
        raise ValueError('Reviewed grade crossing and ordered rails required')
    space = records['opposite-space']
    if (not isinstance(space.get('opposite_side_space_before_entry_m'), (int, float))
            or space['opposite_side_space_before_entry_m'] < 0
            or not space.get('queue_actor_identity_reviewed')):
        raise ValueError('Reviewed opposite-side space and queue identity required')
    grade = records['undercarriage-grade']
    if (not isinstance(grade.get('minimum_undercarriage_clearance_m'), (int, float))
            or not isinstance(grade.get('rail_grade_required_clearance_m'), (int, float))
            or grade['minimum_undercarriage_clearance_m'] < 0
            or grade['rail_grade_required_clearance_m'] < 0):
        raise ValueError('Reviewed vehicle undercarriage and rail grade required')
    return records
