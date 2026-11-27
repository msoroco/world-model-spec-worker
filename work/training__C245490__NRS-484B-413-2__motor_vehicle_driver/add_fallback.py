"""Declare exact same-cell fallback before running its CPU proofs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'draft-native-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        rel = 'native/selected-drafts/' + suffix + '/fallback1/construction.json'
        source = HERE / rel
        entry['candidates'] = [{'id': 'fallback1', 'construction': rel,
            'construction_sha256': sha(source),
            'trigger': {'source': 'result.json physical_checks.maneuver',
                        'metric': 'lane_transition_status',
                        'failure_condition': 'status is not_met or unverified after source-bound original review'},
            'changed_knobs': ['controller_gain 1.5 to 2.0; signal onset, area, weather, actor and camera contract fixed']}]
    path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'cases': len(manifest['cases']), 'manifest_sha256': sha(path)}, sort_keys=True))


if __name__ == '__main__':
    main()
