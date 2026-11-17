"""Validate exact acceptance contract and locally bound helper revisions."""
import hashlib
import json
import sys
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parents[1]
sys.path[:0] = [str(repo / 'runtime/pipeline'), str(repo / 'runtime/pipeline/scenario_pipeline')]
from scenario_pipeline.worker_exchange.delivery_handoff import validate_case

manifest = json.loads((folder / 'execution-manifest.json').read_text())
for entry in manifest['cases']:
    receipt = validate_case(folder, entry, ['full-train'])
    for name, expected in receipt['dependencies_sha256'].items():
        actual = hashlib.sha256((folder / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError('Delivery acceptance helper changed: ' + name)
    physical = entry['diagnostic_physical_outcome']
    path = folder / physical['result']
    if hashlib.sha256(path.read_bytes()).hexdigest() != physical['sha256']:
        raise ValueError('Diagnostic physical outcome changed')
    result = json.loads(path.read_text())
    if result['case_id'] != entry['case_id'] or result['physical_checks']['maneuver']['status'] != 'unverified' or result['maneuver_completed']:
        raise ValueError('Diagnostic fixture was promoted as physical completion')
    print(entry['case_id'], 'CPU acceptance contract passed; Native acceptance unverified')
