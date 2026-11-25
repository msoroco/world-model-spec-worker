"""Prove the pinned converter's required long evidence cannot fit one returned file."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LIMIT = 2 * 1024 * 1024


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evidence_floor(count):
    # Zero and [] minimize values, and constant time deliberately relaxes the
    # required strictly increasing timestamps. A valid evidence stream is larger.
    return sum(len(json.dumps({
        'original_frame': frame, 'replay_frame': frame, 'actor_id': 0,
        'recording_time_s': 0, 'replay_simulation_time_s': 0,
        'ego': {'speed_provenance': 'synthetic_native_sample',
                'speed_mps': 0, 'position_m': []},
    }, separators=(',', ':')).encode()) + 1 for frame in range(count))


def main():
    adapter = REPO / 'runtime/scenario_pipeline/traffic_spec_adapter/adapter.py'
    adapter_text = adapter.read_text()
    required = (
        "e['original_frame']",
        "e['replay_frame']",
        "e['actor_id']",
        "e['recording_time_s']",
        "e['replay_simulation_time_s']",
        "e['ego'].get('speed_provenance')",
        "e['ego']['speed_mps']",
        "e['ego']['position_m']",
        "if source_manifest.get('frames')!=len(evidence) or len(evidence)!=len(telemetry)",
    )
    if any(snippet not in adapter_text for snippet in required):
        raise ValueError('Pinned converter trace contract changed')
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    rows = []
    for entry in manifest['cases']:
        if entry.get('fixture_recipe'):
            continue
        construction = json.loads((HERE / entry['construction']).read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        count = config['capture_frames']
        lower_bound = evidence_floor(count)
        if lower_bound <= LIMIT:
            raise ValueError('Long evidence lower bound no longer exceeds returned-file cap')
        rows.append({'case_id': entry['case_id'], 'frames': count,
                     'evidence_lower_bound_bytes': lower_bound})
    if len(rows) != 16:
        raise ValueError('Selected long case set changed')
    result = {
        'format': 'c150142-current-long-required-evidence-floor-v1',
        'runtime_adapter_sha256': sha(adapter),
        'selected_manifest_sha256': sha(HERE / 'execution-manifest.json'),
        'returned_file_limit_bytes': LIMIT,
        'required_evidence_fields': ['original_frame', 'replay_frame', 'actor_id',
                                     'recording_time_s', 'replay_simulation_time_s',
                                     'ego.speed_provenance', 'ego.speed_mps', 'ego.position_m'],
        'lower_bound_relaxes_timestamp_and_position_validation': True,
        'long_cases': rows,
        'finding': 'Every required single-file long capture/evidence.jsonl exceeds the returned-file cap even with shortest numeric values and no optional fields.',
        'official_public_compatibility_passed': False,
    }
    print(json.dumps(result, sort_keys=True, separators=(',', ':')))


if __name__ == '__main__':
    main()
