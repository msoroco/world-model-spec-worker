"""Independent row-level audit of C102951 measured engineering trigger receipts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.parent.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recompute(folder):
    rows = [json.loads(line) for line in (folder/'native-observed.jsonl').read_text().splitlines()]
    road = json.loads((folder/'road-readback.json').read_text())
    if (len(rows) != 480 or road['lane_count'] != 2 or road['travel_directions'] != 2 or
            road['centerline_y_m'] != 0 or road['source_kind'] != 'synthetic_cpu'):
        raise ValueError('Saved trigger road or frame count differs')
    left = []
    gap = []
    for i, row in enumerate(rows):
        if (row['frame'] != i or row['native_frame'] != 1000+i or
                abs(row['time_s']-.05-i/20) > 1e-4 or
                row['source_kind'] != 'synthetic_cpu' or
                row['ego_blueprint'] != 'vehicle.tesla.model3' or
                row['overtaken_y_m'] != -1.75 or row['oncoming_y_m'] != 1.75 or
                type(row['sightline_visible']) is not bool):
            raise ValueError('Saved trigger row provenance or actor differs')
        if row['ego_y_m']+.9 > 0:
            left.append(i)
    if not left:
        raise ValueError('Left phase absent')
    first, last = left[0], left[-1]
    for i in range(first, last+1):
        row = rows[i]
        gap.append(row['oncoming_x_m']-row['ego_x_m']-4.4)
    entry = rows[first]['oncoming_x_m']-rows[first]['ego_x_m']-4.4
    return round(entry, 3), round(min(gap), 3), all(rows[i]['sightline_visible'] for i in left)


def audit():
    proof = json.loads((HERE/'trigger-proof.json').read_text())
    if (proof['format'] != 'c102951-saved-trigger-proof-v1' or
            proof['assignment_id'] != AID or proof['delivery_ready'] or
            proof['original_native_observed'] or proof['legal_verdict'] is not None or
            proof['construction_manifest_sha256'] != sha(HERE/'drafts/manifest.json') or
            proof['trigger_code_sha256'] != sha(HERE/'triggers.py') or
            proof['saved_processor_sha256'] != sha(HERE/'measure_pass.py')):
        raise ValueError('Trigger proof source binding or status differs')
    fixtures = proof['fixtures']
    if len(fixtures) != 9 or {(r['distance_m'], r['candidate_id']) for r in fixtures} != {
            (d, c) for d in (70, 120, 170) for c in ('fallback1', 'fallback2', 'fallback3')}:
        raise ValueError('Exact trigger coverage differs')
    for item in fixtures:
        d = item['distance_m']
        folder = HERE/'saved-fixtures'/str(d)
        if item['source_hashes'] != {name: sha(folder/name) for name in ('native-observed.jsonl', 'road-readback.json')}:
            raise ValueError('Saved trigger hash differs')
        entry, minimum, visible = recompute(folder)
        if abs(entry-d) > 1e-3:
            raise ValueError('Entry gap differs from frozen sweep probe')
        candidate = item['candidate_id']
        metric = entry if candidate == 'fallback1' else minimum if candidate == 'fallback2' else visible
        expected = metric < 100 if candidate == 'fallback1' else metric < 20 if candidate == 'fallback2' else not visible
        if item['metric'] != metric or item['triggered'] is not expected:
            raise ValueError('Measured trigger receipt differs')
    occluded = proof['visibility_trigger']
    folder = HERE/'trigger-fixtures'/'occluded-170'
    if (occluded['source_hashes'] != {name: sha(folder/name) for name in ('native-observed.jsonl', 'road-readback.json')} or
            occluded['changed_frame'] != 60 or occluded['triggered'] is not True or
            recompute(folder)[2] is not False):
        raise ValueError('Retained sightline trigger differs')
    negatives = proof['negative_controls']
    if {n['mutation'] for n in negatives} != {
            'incorrect_saved_source_hash', 'missing_sightline_observation', 'one_direction_road'} or not all(
            n['rejected'] is True for n in negatives):
        raise ValueError('Trigger negative coverage differs')
    receipt = {'format': 'c102951-independent-trigger-audit-v1',
               'assignment_id': AID, 'proof_sha256': sha(HERE/'trigger-proof.json'),
               'saved_rows_recomputed': 4800, 'fixture_decisions_checked': 10,
               'negative_controls_checked': 3,
               'original_native_observed': False, 'delivery_ready': False}
    (HERE/'trigger-audit.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


if __name__ == '__main__':
    print(json.dumps(audit()))
