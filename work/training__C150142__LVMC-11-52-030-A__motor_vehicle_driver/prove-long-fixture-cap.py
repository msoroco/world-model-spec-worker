"""Check the pinned diagnostic video cap against every selected long case."""
import hashlib
import json
import os
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT',
                      str(REPO / '.runtime-work' / 'owner150142' / 'fixture-cap'))
sys.path.insert(0, str(REPO / 'runtime'))
from scenario_pipeline.worker_exchange.fixture_generator import inspect


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = json.loads((HERE / 'execution-manifest.json').read_text())
cases = []
for entry in manifest['cases']:
    slug = entry['case_id'].rsplit('__', 1)[1]
    if not slug.startswith(('tour_bus_', 'shuttle_bus_', 'limo_', 'rtc_bus_')):
        continue
    construction_path = HERE / entry['construction']
    construction = json.loads(construction_path.read_text())
    config = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
    finalizer = next(item['content'] for item in construction['files']
                     if item['path'] == entry['measurement_procedure']['entrypoint'])
    frames = config['capture_frames']
    assert isinstance(frames, int) and frames > 2000
    assert "if len(actor_rows) != len(frame_map) or len(trace) != expected_frames:" in finalizer
    assert "expected_frames=config.get('capture_frames')" in finalizer
    spec = {'files': {}, 'graphs': [], 'videos': [{
        'path': 'overview.mkv', 'frames': frames, 'width': 16,
        'height': 16, 'fps': 20, 'color': 'black'}]}
    try:
        inspect(spec)
    except ValueError as error:
        assert str(error) == 'Invalid bounded diagnostic video parameters'
    else:
        raise AssertionError('Pinned generator accepted an unbounded video')
    cases.append({'case_id': entry['case_id'], 'capture_frames': frames,
                  'construction_sha256': sha(construction_path),
                  'finalizer_entrypoint': entry['measurement_procedure']['entrypoint'],
                  'generator_rejection': 'Invalid bounded diagnostic video parameters'})
assert len(cases) == 16
proof = {'format': 'c150142-long-fixture-cap-proof-v1', 'passed': True,
         'runtime_manifest_sha256': manifest['runtime_manifest_sha256'],
         'selected_manifest_sha256': sha(HERE / 'execution-manifest.json'),
         'cases': cases, 'official_public_compatibility_claimed': False}
path = HERE / 'current-long-fixture-cap-proof.json'
path.write_text(json.dumps(proof, indent=2) + '\n')
print(json.dumps({'cases': len(cases), 'proof_sha256': sha(path)}, sort_keys=True))
