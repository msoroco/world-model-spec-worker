"""Independently recompute requested motion and verify three diagnostic outcomes."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--selected', action='store_true')
args = parser.parse_args()
BASE = HERE / ('selected-30s' if args.selected else 'extended-primary') / 'physical-proof'
KINDS = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
         'missing_evidence': 'unverified'}
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


manifest = read(HERE / ('selected-30s-draft-execution-manifest.json' if args.selected
                        else 'current-30s-compatibility-manifest.json'))
index = read(BASE / 'index.json')
assert len(index['cases']) == len(manifest['cases']) == 2
rows = []
for entry, ref in zip(manifest['cases'], index['cases']):
    assert ref['case_id'] == entry['case_id']
    proof_path = HERE / ref['receipt']
    assert sha(proof_path) == ref['sha256']
    proof = read(proof_path)
    assert proof['construction_sha256'] == entry['construction_sha256'] == sha(HERE / entry['construction'])
    construction = read(HERE / entry['construction'])
    tracks = next(item['content'] for item in construction['files'] if item['path'] == 'requested-tracks.jsonl')
    authored = [json.loads(line) for line in tracks.splitlines()]
    assert len(authored) == 600
    witness = entry['case_id'].rsplit('__', 1)[-1]
    overlap = sum(row['requested_center_xy_m'][1] - row['requested_body_width_m'] / 2 < -3.5
                  and row['requested_center_xy_m'][1] + row['requested_body_width_m'] / 2 > -5.5
                  for row in authored)
    assert overlap == (0 if witness == 'witness_1' else 520)
    assert round(authored[-1]['requested_center_xy_m'][0] - authored[0]['requested_center_xy_m'][0], 4) == 119.8
    assert {fixture['kind'] for fixture in proof['fixtures']} == set(KINDS)
    for fixture in proof['fixtures']:
        assert fixture['exit_code'] == 0
        assert sha(HERE / fixture['log']) == fixture['log_sha256']
        assert sha(HERE / fixture['result']) == fixture['result_sha256']
        result = read(HERE / fixture['result'])
        status = KINDS[fixture['kind']]
        assert result['case_id'] == entry['case_id'] and result['construction_sha256'] == entry['construction_sha256']
        assert result['physical_checks']['maneuver']['status'] == status
        assert result['maneuver_completed'] == (status == 'met')
        assert result['provenance_kind'] == 'synthetic_fixture' and result['diagnostic_fixture'] is True
        assert result['original_native_observed'] is False and result['legal_verdict'] is None
        assert result['requested_track_sha256'] == hashlib.sha256(tracks.encode()).hexdigest()
        if status == 'met':
            assert result['realized_observables']['requested_sidewalk_overlap_frames'] == overlap
            assert result['realized_observables']['requested_travel_m'] == 119.8
    life = proof['lifecycle']
    assert life['events'] == EVENTS and life['exit_code'] == 0
    assert life['negative_premature_saved_processing_rejected'] is True
    assert sha(HERE / life['log']) == life['log_sha256']
    rows.append({'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
                 'requested_overlap_frames': overlap, 'proof_sha256': sha(proof_path)})
out = {'format': 'c422978-30s-physical-audit-v1', 'rows': rows, 'passed': True,
       'diagnostic_only': True, 'original_native_observed': False}
path = BASE / 'audit.json'
path.write_text(json.dumps(out, sort_keys=True, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'passed': True, 'cases': len(rows), 'audit_sha256': sha(path)}))
