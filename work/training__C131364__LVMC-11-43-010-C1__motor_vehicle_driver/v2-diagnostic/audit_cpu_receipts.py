"""Independently audit retained current-v2 roundabout CPU receipts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = json.loads((CASE / 'v2-offline-manifest.json').read_text())
assert manifest['assignment_id'] == CASE.name and len(manifest['cases']) == 2
results = []
for entry in manifest['cases']:
    witness = entry['case_id'].rsplit('__', 1)[-1]
    proof = HERE / witness / 'proofs'
    compat = json.loads((proof / 'compatibility.json').read_text())
    process = json.loads((proof / 'processing.json').read_text())
    report = json.loads((proof / 'analysis-report.json').read_text())
    assert compat['passed'] is True and process['passed'] is True
    assert compat['case_id'] == entry['case_id']
    assert compat['construction_sha256'] == entry['construction_sha256']
    assert compat['analysis_report_sha256'] == sha(proof / 'analysis-report.json')
    assert compat['negative_log_sha256'] == sha(proof / 'negative-analysis.log')
    assert compat['fixture_recipe_sha256'] == sha(ROOT / entry['fixture_recipe'])
    assert compat['measurement_contract_sha256'] == sha(CASE / entry['measurement_contract'])
    assert compat['negative_removed'] == 'roundabout-track.jsonl'
    assert compat['negative_error_contains'] in (proof / 'negative-analysis.log').read_text()
    assert 'Ran 4 tests' in (proof / 'cpu-offline.log').read_text()
    assert process['physical_acceptance_claimed'] is False
    assert process['legal_acceptance_claimed'] is False
    assert report['physical_acceptance_claimed'] is False
    assert report['legal_acceptance_claimed'] is False
    value = compat['measurement_examples']['lane_passage']['value']
    assert value['frames'] == 600
    assert value['entry_frames'] + value['circulation_frames'] + value['exit_frames'] == 600
    assert all(value[key] is False for key in ('actual_exit_observed',
        'physical_roundabout_verified', 'lane_occupancy_observed', 'native_provenance'))
    results.append({'case_id': entry['case_id'], 'lane': value['requested_lane_id'],
        'phases': [value['entry_frames'], value['circulation_frames'], value['exit_frames']],
        'compatibility_sha256': sha(proof / 'compatibility.json'),
        'processing_sha256': sha(proof / 'processing.json')})
assert [row['lane'] for row in results] == [-1, -2]
constructions = [json.loads((CASE / entry['construction']).read_text())
                 for entry in manifest['cases']]
configs = [json.loads(next(f['content'] for f in construction['files']
    if f['path'] == 'config.json')) for construction in constructions]
fixed = ('cell_id', 'law_id', 'actor', 'duration_s', 'rate_hz', 'cameras',
         'required_atoms', 'source_packets', 'recording_description',
         'assignment_sha256', 'case_plan_sha256', 'road_sha256')
assert all(configs[0][key] == configs[1][key] for key in fixed)
assert configs[0]['track_sha256'] != configs[1]['track_sha256']
tracks = [[json.loads(line) for line in (HERE / witness / 'source-track.jsonl').read_text().splitlines()]
          for witness in ('witness_1', 'witness_2')]
assert all(len(track) == 600 for track in tracks)
assert all(left['frame'] == right['frame'] and left['time_s'] == right['time_s']
           and left['lane_id'] == -1 and right['lane_id'] == -2
           for left, right in zip(*tracks))
print(json.dumps({'passed': True, 'manifest_sha256': sha(CASE / 'v2-offline-manifest.json'),
    'witnesses': results, 'comparison_fixed_keys': list(fixed),
    'comparison_variable': 'roundabout_exit_lane'}))
