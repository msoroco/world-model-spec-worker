"""Build exact synthetic source rows and CPU receipts for the pedestrian clause."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'native'))
from pedestrian_engineering import NAMES, construction, fixture_rows, measure


def write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False)+'\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    base = ROOT/'draft-pedestrian-cases'
    receipts = []
    for response in ('clear', 'conflict'):
        for candidate in NAMES:
            folder = base/response/candidate
            folder.mkdir(parents=True, exist_ok=True)
            policy = construction(response, candidate)
            rows = fixture_rows(response, candidate)
            write(folder/'construction.json', policy)
            with (folder/'source-rows.jsonl').open('w') as stream:
                for row in rows:
                    stream.write(json.dumps(row, sort_keys=True, allow_nan=False)+'\n')
            result = measure(rows, policy)
            assert result['qualifying_synthetic_geometry']
            assert result['simultaneous_conflict_frames'] == (0 if response == 'clear' else 20)
            write(folder/'measurement.json', result)
            negatives = {}
            for label, kwargs in (('passable_sidewalk', {'blocked': False}),
                                  ('late_sidewalk_return', {'return_delay': 30})):
                negative = measure(fixture_rows(response, candidate, **kwargs), policy)
                assert not negative['qualifying_synthetic_geometry']
                negatives[label] = {'qualification_rejected': True,
                                    'measured': negative}
            write(folder/'negative-receipts.json', negatives)
            receipt = {'case_suffix': policy['case_suffix'], 'candidate_id': candidate,
                       'source_kind': 'synthetic_cpu_fixture', 'accepted': False,
                       'construction_sha256': sha(folder/'construction.json'),
                       'source_sha256': sha(folder/'source-rows.jsonl'),
                       'measurement_sha256': sha(folder/'measurement.json'),
                       'negative_sha256': sha(folder/'negative-receipts.json')}
            write(folder/'receipt.json', receipt)
            receipts.append(receipt)
    summary = {'format': 'c10052-pedestrian-cpu-construction-v1',
               'source_kind': 'synthetic_cpu_fixture', 'accepted': False,
               'cases': 2, 'candidates_per_case': 4,
               'positive_source_receipts': 8, 'qualification_negatives': 16,
               'controlled_clear_conflict_pairs': 4,
               'receipts': receipts,
               'original_native_verified': False, 'strict_v2_compatibility_verified': False}
    write(ROOT/'pedestrian-qualification-cpu-summary.json', summary)
    print(json.dumps({key: summary[key] for key in ('cases', 'positive_source_receipts',
                                                     'qualification_negatives')}, sort_keys=True))


if __name__ == '__main__':
    main()
