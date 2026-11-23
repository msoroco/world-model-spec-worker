"""Independent saved-only source binding for original signed-zone speed evidence."""
import hashlib
import json
from pathlib import Path


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(capture_path, seal_path, case_id):
    capture = Path(capture_path)
    seal = json.loads(Path(seal_path).read_text())
    if seal.get('capture_sha256') != _sha(capture):
        raise ValueError('capture seal mismatch')
    data = json.loads(capture.read_text())
    if data.get('case_id') != case_id or seal.get('case_id') != case_id:
        raise ValueError('exact case mismatch')
    if data.get('cell_id') != 'C136559' or data.get('law_id') != 'NRS-484B-620-2':
        raise ValueError('identity mismatch')
    if not all(data.get(k) for k in ('map_source_sha256', 'zone_establishment_source_sha256',
                                     'zone_extent_source_sha256', 'sign_instruction_source_sha256',
                                     'camera_plan_sha256', 'ego_blueprint')):
        raise ValueError('site source missing')
    if data.get('authorized_speed_mph') != 25.0:
        raise ValueError('authorized speed source changed')
    rows = data.get('original_rows', [])
    if len(rows) != 900:
        raise ValueError('full original frame history missing')
    previous_time = None
    for i, row in enumerate(rows):
        if row.get('original_frame') != i:
            raise ValueError('original frame gap')
        t = row.get('original_time_s')
        if not isinstance(t, (int, float)) or (previous_time is not None and t <= previous_time):
            raise ValueError('original time gap')
        previous_time = t
        if not row.get('ego_id') or not row.get('sign_readback_source_sha256'):
            raise ValueError('actor or sign readback source missing')
        if not isinstance(row.get('inside_zone'), bool) or not isinstance(row.get('sign_installed'), bool):
            raise ValueError('zone or sign observation missing')
        speed = row.get('actual_speed_mps')
        if not isinstance(speed, (float, int)) or speed < 0 or speed > 100:
            raise ValueError('original speed missing or invalid')
    return {'case_id': case_id, 'frame_count': len(rows), 'capture_sha256': seal['capture_sha256'],
            'first_original_frame': rows[0]['original_frame'],
            'last_original_frame': rows[-1]['original_frame'],
            'legal_judgment': None}
