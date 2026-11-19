"""Package the law-required stop CPU draft without changing proved bundles."""
import hashlib
import json
from pathlib import Path

from build_reference_draft import MODULES, ROOT
from native_channels import channels_for


HERE = Path(__file__).resolve().parent
CASE = 'law_required_stop'
CASE_ID = HERE.name + '__' + CASE


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def build():
    safe = json.loads((HERE/'draft-safe_operation_stop-construction.json').read_text())
    plan = json.loads((HERE/'case-plan.json').read_text())
    files = {item['path']: item['content'] for item in safe['files']}
    for name in MODULES:
        files[name] = (HERE/name).read_text()
    config = json.loads(files['config.json'])
    config.update(case_id=CASE_ID, selected_case_id=CASE_ID,
                  case_suffix=CASE, case={'case_id': CASE_ID},
                  comparison_requested_value='roadway_stop_with_source_visible_governing_red_control')
    config['survey_contract']['governing_traffic_light_id_required'] = True
    channels = config['recording_description']['channels']
    channels[:] = [entry for entry in channels if entry['name'] in channels_for(CASE)]
    sample = channels[0].copy()
    sample.update(name='governing_control_readback',
                  method='native_channels.derive from original traffic-light actor and ego association rows',
                  uncertainty='50 ms sampling; governing applicability and compliance require independent review')
    channels.append(sample)
    files['config.json'] = json.dumps(config, indent=2, sort_keys=True)+'\n'
    construction = safe.copy()
    construction.update(case_id=CASE_ID, files=[{'path':k,'content':v} for k,v in files.items()],
                        mechanisms=['surveyed driving lane and shoulder',
                                    'ego and following actor', 'four original RGB cameras',
                                    'source-bound stop finalizer',
                                    'surveyed traffic-light actor with per-frame ego association and state readback'],
                        recording_description=config['recording_description'])
    construction['measurement_plan']['per_case_contracts'][0]['case_id'] = CASE_ID
    path=HERE/'draft-law_required_stop-construction.json'
    write(path,construction)
    manifest={'format':'worker-execution-manifest','assignment_id':HERE.name,
              'runtime_manifest_sha256':sha(ROOT/'runtime/pipeline/SOURCE-MANIFEST.json'),
              'status':'draft_law_primary_offline_only',
              'cases':[{'case_id':CASE_ID,'construction':path.name,
                        'construction_sha256':sha(path)}]}
    write(HERE/'draft-law-required-manifest.json',manifest)
    return {'case_id':CASE_ID,'construction_sha256':sha(path),
            'manifest_sha256':sha(HERE/'draft-law-required-manifest.json')}


if __name__ == '__main__':
    print(json.dumps(build(),sort_keys=True))
