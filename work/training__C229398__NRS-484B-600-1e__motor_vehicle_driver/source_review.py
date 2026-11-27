"""Bind original route, curb, subject, phase and visibility sources by hash."""
import hashlib
import json
from pathlib import Path

AID = 'training__C229398__NRS-484B-600-1e__motor_vehicle_driver'
SOURCES = ('road_curb_route', 'approach_scope', 'vehicle_identity',
           'camera_visibility')


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def join(attempt, case_id, diagnostic=False):
    attempt = Path(attempt)
    path = attempt/'approach-review.json'
    require(path.is_file(), 'Missing required source: approach-review.json')
    review = json.loads(path.read_text())
    require(review.get('assignment_id') == AID and review.get('case_id') == case_id,
            'Exact source review identity differs')
    kind = review.get('review_kind')
    require(kind in ('original_native', 'synthetic_diagnostic'),
            'Unknown source review provenance')
    require(diagnostic == (kind == 'synthetic_diagnostic'),
            'Synthetic source cannot claim original review')
    refs = review.get('sources', {})
    require(set(refs) == set(SOURCES), 'Route, phase, actor or camera source missing')
    hashes = {}
    for name in SOURCES:
        ref = refs[name]
        expected = 'source_context/'+name+'.txt'
        require(ref.get('path') == expected and (attempt/expected).is_file(),
                'Missing required source: '+expected)
        digest = sha(attempt/expected)
        require(digest == ref.get('sha256'), 'Source hash mismatch: '+name)
        hashes[name] = digest
    require(sha(attempt/'road.xodr') == review.get('road_xodr_sha256'),
            'Reviewed road and curb geometry hash changed')
    if kind == 'original_native':
        for key in ('road_and_curb_native_readback_reviewed',
                    'approach_driving_and_parking_same_recording_reviewed',
                    'subject_actor_identity_reviewed',
                    'all_four_camera_visibility_reviewed'):
            require(review.get(key) is True, 'Original source review incomplete: '+key)
    else:
        require(review.get('physical_acceptance_claimed') is False,
                'Synthetic source claimed physical acceptance')
    return {'review_kind':kind,'source_sha256':hashes,
            'original_scope_reviewed':kind == 'original_native'}
