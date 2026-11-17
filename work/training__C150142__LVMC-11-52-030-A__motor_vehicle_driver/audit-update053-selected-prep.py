"""Check exact selected acquisition bindings for the nine pending long primaries."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ITEMS = {
    'tour_bus_above': 36122, 'shuttle_bus_above': 36122,
    'limo_above': 36122, 'rtc_bus_above': 36122,
    'tour_bus_no_loading': 36121, 'shuttle_bus_no_loading': 36121,
    'limo_no_loading': 36121, 'rtc_bus_at': 36121,
    'rtc_bus_no_loading': 36121,
}
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest_path = ROOT / 'execution-manifest.json'
    manifest_sha = sha(manifest_path)
    cases = {case['case_id']: case for case in read(manifest_path)['cases']}
    rows = []
    for name, frames in ITEMS.items():
        case_id = ROOT.name + '__' + name
        attempt = REPO / '.runtime-work' / ('c150142-selected-' +
                    name.replace('_', '-') + '-primary-native-v1')
        selection = read(attempt / 'candidate-selection.json')
        config = read(attempt / 'config.json')
        assert selection['case_id'] == case_id
        assert selection['candidate_id'] == 'primary'
        assert selection['manifest_sha256'] == manifest_sha
        assert selection['construction_sha256'] == cases[case_id]['construction_sha256']
        assert config['capture_frames'] == frames
        assert all((attempt / (view + '.mkv')).is_file() for view in VIEWS)
        rows.append({'case_id': case_id, 'frames': frames,
                     'construction_sha256': selection['construction_sha256'],
                     'four_named_sources_present': True})
    return {'format': 'c150142-update053-selected-prep-audit-v1',
            'manifest_sha256': manifest_sha, 'passed': True,
            'scope': 'synthetic prepared acquisitions; no saved pass implied',
            'rows': rows, 'original_native_observed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
