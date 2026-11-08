"""Independently audit the synthetic retag path and its tampered row."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def read(path):
    return json.loads(path.read_text())


def encoded(rows):
    return ''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows).encode()


def main():
    proof = read(HERE / 'original-tag-cpu-proof.json')
    assert proof['format'] == 'c422978-original-tag-cpu-path-v1'
    assert proof['original_native_observed'] is False and proof['accepted'] is False
    source = HERE / 'saved-fixtures/witness_2/primary/native-observed.jsonl'
    context = HERE / 'context-fixtures/witness_2/primary/city-context.json'
    assert proof['source_fixture_sha256'] == sha_bytes(source.read_bytes())
    assert proof['context_sha256'] == sha_bytes(context.read_bytes())
    assert proof['occupancy_processor_sha256'] == sha_bytes((HERE / 'measure_saved.py').read_bytes())
    assert proof['spatial_processor_sha256'] == sha_bytes((HERE / 'measure_context.py').read_bytes())
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    assert len(rows) == 480 and all(row['source_kind'] == 'synthetic_cpu' for row in rows)
    for row in rows:
        row['source_kind'] = 'original_native'
    assert proof['retagged_observed_sha256'] == sha_bytes(encoded(rows))
    moving = [row for row in rows if row['speed_mps'] > .1]
    occupancy = sum(min(p[1] for p in row['body_native_xy_m']) < 5.5 and
                    max(p[1] for p in row['body_native_xy_m']) > 3.5 for row in moving)
    spatial = sum(min(p[1] for p in row['body_native_xy_m']) <= 5.5 and
                  max(p[1] for p in row['body_native_xy_m']) >= 3.5 for row in moving)
    assert proof['positive'] == {
        'frames': 480, 'moving_sidewalk_overlap_frames': occupancy,
        'moving_sidewalk_intersection_frames': spatial,
        'city_authority_reviewed': False,
        'driveway_rule_composition_reviewed': False, 'legal_verdict': None}
    rows[17]['source_kind'] = 'native_original'
    assert proof['mixed_provenance_observed_sha256'] == sha_bytes(encoded(rows))
    assert set(proof['negative_rejections']) == {'occupancy', 'spatial'}
    assert all('provenance differs' in message for message in proof['negative_rejections'].values())
    result = {'format': 'c422978-original-tag-independent-audit-v1',
              'proof_sha256': sha_bytes((HERE / 'original-tag-cpu-proof.json').read_bytes()),
              'rows_audited': 480, 'negative_rejections_audited': 2,
              'original_native_observed': False, 'accepted': False}
    (HERE / 'original-tag-cpu-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
