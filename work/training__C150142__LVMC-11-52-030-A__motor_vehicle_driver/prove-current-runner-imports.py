"""Check every C150142 Native entrypoint resolves the active pinned runtime."""
import ast
import hashlib
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
RUNNERS = (
    'selected_runner.py', 'signed_runner.py', 'long_exception_runner.py',
    'no_loading_runner.py', 'business_runner.py',
    'emergency_no_business_runner.py',
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    output_root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    if REPO / '.runtime-work' not in output_root.parents:
        raise ValueError('Runtime output root must be under .runtime-work')
    if not (REPO / 'runtime/scenario_pipeline/worker_exchange/capture.py').is_file():
        raise ValueError('Active runtime capture source missing')
    if not (REPO / 'runtime/python/pipeline_capture.py').is_file():
        raise ValueError('Active Native capture source missing')
    paths = {}
    for name in RUNNERS:
        path = ROOT / 'native' / name
        source = path.read_text()
        ast.parse(source, filename=str(path))
        if 'runtime/pipeline/' in source:
            raise ValueError('Retired runtime import in ' + name)
        if "repo / 'runtime/scenario_pipeline'" not in source or \
                "repo / 'runtime/python'" not in source:
            raise ValueError('Missing active runtime import in ' + name)
        paths[name] = sha(path)
    audit = ROOT / 'native/delivery_audit.py'
    source = audit.read_text()
    ast.parse(source, filename=str(audit))
    if 'runtime/pipeline/' in source or "parent / 'runtime/scenario_pipeline'" not in source:
        raise ValueError('Delivery audit does not resolve active runtime')
    sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
    sys.path.insert(0, str(REPO / 'runtime/python'))
    from worker_exchange import native_output, world_restore
    capture = REPO / 'runtime/python/pipeline_capture.py'
    compile(capture.read_text(), str(capture), 'exec')
    if not all((native_output.seal_capture, world_restore.snapshot,
                world_restore.restore)):
        raise ValueError('Active Native runtime imports incomplete')
    return {'format': 'c150142-current-native-import-proof-v1',
            'passed': True, 'runner_sha256': paths,
            'delivery_audit_sha256': sha(audit),
            'capture_sha256': sha(REPO / 'runtime/python/pipeline_capture.py'),
            'native_output_sha256': sha(REPO / 'runtime/scenario_pipeline/worker_exchange/native_output.py'),
            'scope': 'source and import viability; no CARLA execution',
            'original_native_observed': False}


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True, indent=2))
