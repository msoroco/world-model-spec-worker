"""Independent raw-row audit of C104538 saved geometry diagnostic."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
PROOF = HERE/'draft-saved-geometry-proof.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


proof = json.loads(PROOF.read_text())
assert proof['scope'] == 'unselected synthetic source rows with posture labels erased'
assert proof['positive_count'] == 8 and proof['negative_count'] == 48
assert not any(proof[x] for x in ('original_native_capture_executed', 'posture_reviewed',
                                  'legal_verdict_claimed', 'accepted'))
seen = set()
for entry in proof['entries']:
    kind, candidate = entry['kind'], entry['candidate_id']
    assert kind in ('mounted_obey', 'mounted_turn')
    assert candidate in ('primary', 'fallback1', 'fallback2', 'fallback3')
    assert (kind, candidate) not in seen
    seen.add((kind, candidate))
    folder = HERE/'draft-exact-candidates'/kind/candidate/'package-proof'
    assert all(sha(folder/name) == digest for name, digest in entry['source_sha256'].items())
    rider = rows(folder/'rider_native_samples.jsonl')
    native = rows(folder/'native_samples.jsonl')
    mapping = rows(folder/'video_frames.jsonl')
    sign = json.loads((folder/'authored-sign.json').read_text())
    road = ET.fromstring((folder/'road.xodr').read_text()).find('road')
    signal = road.find('signals/signal')
    assert signal.attrib['id'] == '1140080'
    assert sign['station_m'] == float(signal.attrib['s']) == 72.0
    assert len(rider) == len(native) == len(mapping) == 480
    assert all(r['actor_id'] == rider[0]['actor_id'] and r['sign_id'] == sign['id'] and
               r['frame'] == i and r['time_s'] == n['time_s'] == m['time_s'] and
               n['native_frame'] == m['native_frame'] == m['carla_frame'] and
               m['video_frame'] == i and math.dist(n['native_center_xy_m'],
                   (r['x_m'], r['y_m'])) <= 1e-4
               for i, (r, n, m) in enumerate(zip(rider, native, mapping)))
    first = native[0]['native_forward_xy']
    last = native[-1]['native_forward_xy']
    dot = sum(a*b for a, b in zip(first, last))
    crossing = sum(abs(n['native_center_xy_m'][1]) < 1 and
                   -12 <= n['native_center_xy_m'][0] <= 12 for n in native)
    switched = native[0]['native_lane_id'] == -1 and native[-1]['native_lane_id'] == 1
    measured = entry['measurement']
    assert measured['center_crossing_frames'] == crossing
    assert measured['opposing_lane_arrival'] == switched
    assert measured['u_turn_geometry_observed'] == (kind == 'mounted_turn')
    assert (dot < -.8 and switched and crossing >= 5) == measured['u_turn_geometry_observed']
    assert measured['mounted_posture_observed'] is None
    assert measured['legal_outcome'] == 'unresolved' and not measured['accepted']
    assert entry['negative_rejections'] == {
        'filled_posture': 'Unreviewed posture or turn label was filled',
        'changed_actor': 'Rider actor/sign/frame identity differs',
        'changed_sign': 'Rider actor/sign/frame identity differs',
        'changed_frame': 'Native/camera time or frame join differs',
        'changed_center': 'Rider and Native centers differ',
        'changed_station': 'Authored sign code or station differs from road'}
assert len(seen) == 8
result = {'passed': True, 'scope': 'independent retained raw-row geometry audit',
    'positives': 8, 'negative_rejections': 48, 'controlled_pairs': 4,
    'proof_sha256': sha(PROOF), 'original_native_capture_executed': False,
    'legal_verdict_claimed': False, 'accepted': False}
target = HERE/'draft-saved-geometry-audit.json'
target.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
print(json.dumps(result))
