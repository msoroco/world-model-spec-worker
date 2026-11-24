"""CPU proof for controlled authored placement-source availability."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile

HERE = Path(__file__).resolve().parent
BASE = HERE / 'cases/branch-requests'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(bundle):
    spec = importlib.util.spec_from_file_location('placement_check', bundle / 'placement_check.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.check(bundle)


def main():
    entries = []
    tracks = set()
    for suffix in ('placement_record_absent', 'placement_record_supplied'):
        for candidate in ('primary', 'fallback1'):
            bundle = BASE / (suffix if candidate == 'primary' else suffix + '-fallback1')
            result = check(bundle)
            assert result['official_placement_verified'] is False
            tracks.add(sha(bundle / 'requested-tracks.jsonl'))
            assert "placement-source-readback.json" in (bundle / 'runner.py').read_text()
            entries.append({'case_id': result['case_id'], 'candidate_id': candidate,
                            'construction_sha256': sha(bundle / 'construction.json'),
                            'record_sha256': result['placement_source_sha256'],
                            'document_present': result['placement_source']['document_present']})
    assert len(tracks) == 1
    with tempfile.TemporaryDirectory(prefix='c10389-placement-proof-', dir=HERE.parents[1] / '.runtime-work') as name:
        target = Path(name)
        source = BASE / 'placement_record_supplied'
        for part in ('config.json', 'assignment-source.json', 'alley-stop.xodr',
                     'requested-tracks.jsonl', 'placement-record.json', 'placement_check.py'):
            shutil.copyfile(source / part, target / part)
        record = json.loads((target / 'placement-record.json').read_text())
        record['official_placement_verified'] = True
        (target / 'placement-record.json').write_text(json.dumps(record) + '\n')
        try:
            check(target)
        except ValueError as exc:
            assert 'Placement source hash changed' in str(exc)
        else:
            raise AssertionError('Unverified placement source was promoted')
    result = {'format': 'c10389-placement-source-pair-proof-v1', 'entries': entries,
              'shared_tracks_sha256': tracks.pop(), 'tampered_authority_rejected': True,
              'administrative_authenticity_verified': False,
              'official_placement_verified': False, 'selected_delivery': False}
    path = BASE / 'placement-pair-proof.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    print(json.dumps({'positive': len(main()['entries']), 'negative': 1}))
