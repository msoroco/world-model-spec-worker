"""Reject corrupted emergency-business draft audit inputs."""
import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('emergency_audit',
                                            ROOT / 'audit-emergency-business-draft.py')
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def reject(name, manifest=None, packages=None, saved=None):
    try:
        AUDIT.check(manifest=manifest, packages=packages, saved=saved)
    except ValueError as error:
        return {'mutation': name, 'rejected': True, 'reason': str(error)}
    raise AssertionError('Corrupted emergency-business audit input accepted: ' + name)


def prove():
    manifest = json.loads((ROOT / 'execution-manifest-diagnostic-emergency-business-draft.json').read_text())
    saved = json.loads((ROOT / 'update040-emergency-business-saved-matrix.json').read_text())
    AUDIT.check(manifest=manifest, saved=saved)
    outputs = []
    altered = copy.deepcopy(manifest)
    altered['cases'][0]['candidates'][0]['construction_sha256'] = '0' * 64
    outputs.append(reject('candidate_construction_hash', manifest=altered, saved=saved))
    altered = copy.deepcopy(saved)
    altered['candidates'][2]['frames'] = 360
    outputs.append(reject('terminal_saved_frame_count', manifest=manifest, saved=altered))
    path = ROOT / 'selected-fallbacks/emergency_vehicle_unsigned_business/fallback1/construction.json'
    package = json.loads(path.read_text())
    altered = copy.deepcopy(package)
    for row in altered['files']:
        if row['path'] == 'config.json':
            config = json.loads(row['content'])
            config['sign_classes'] = ['emergency_vehicle']
            row['content'] = json.dumps(config)
            break
    outputs.append(reject('unsigned_sign_changed', manifest=manifest,
                          packages={'fallback1': altered}, saved=saved))
    altered = copy.deepcopy(manifest)
    altered['cases'][0]['candidates'][1]['trigger']['failure_condition'] = (
        altered['cases'][0]['candidates'][0]['trigger']['failure_condition'])
    outputs.append(reject('duplicate_physical_trigger', manifest=altered, saved=saved))
    return {'case_id': AUDIT.CASE, 'negative_checks': outputs}


if __name__ == '__main__':
    print(json.dumps(prove(), indent=2))
